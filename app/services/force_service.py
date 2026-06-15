"""Force management service for MechBay.

Provides CRUD operations for forces, lances, and miniature assignments.
Handles active force management and import/export functionality.

KNOWN LIMITATION - Thread Safety:
The active force invariant (only one Force.is_active=True) is enforced by
application logic and a partial unique index (uix_one_active_force) on SQLite
and PostgreSQL. Concurrent calls to create_force() or switch_active_force() may
still race before commit; the index rejects a second active row at flush time.

Future considerations:
- Add pessimistic row locking with SELECT FOR UPDATE when switching active
- Consider application-level distributed lock for multi-instance deployments
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import and_, func, select

from ..extensions import session_scope
from ..models.alpha_strike_assignment import AlphaStrikeAssignment
from ..models.alpha_strike_force import AlphaStrikeForce
from ..models.force import Force
from ..models.force_miniature import ForceMiniature
from ..models.lance import Lance
from ..models.miniature import Miniature
from . import alpha_strike_service, mul_service
from .lance_colors import pick_lance_header_color

logger = structlog.get_logger()

FORCE_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ForceMiniatureAssignment:
    lance_name: str
    lance_color: str | None


@dataclass
class InventoryCandidate:
    miniature: Miniature
    in_force: bool
    lance_name: str | None
    lance_id: int | None
    lance_color: str | None
    mul_available: bool | None  # None = no MUL filter active


def get_active_force() -> Force | None:
    """Get the currently active force with all lances and miniatures loaded."""
    with session_scope() as session:
        stmt = select(Force).where(Force.is_active == True)  # noqa: E712
        force = session.execute(stmt).scalar_one_or_none()
        if force:
            # Eager load relationships
            for lance in force.lances:
                _ = lance.miniatures
                for fm in lance.miniatures:
                    _ = fm.miniature
            # Expunge to make accessible outside session
            session.expunge(force)
        return force


def get_all_forces() -> list[Force]:
    """Get all forces with summary info."""
    with session_scope() as session:
        stmt = select(Force).order_by(Force.is_active.desc(), Force.created_at.desc())
        forces = list(session.execute(stmt).scalars().all())
        # Make all objects accessible outside session
        for force in forces:
            # Eager load relationships by accessing them within session
            for lance in force.lances:
                _ = lance.miniatures
                for fm in lance.miniatures:
                    _ = fm.miniature
            session.expunge(force)
        return forces


def get_force_by_id(force_id: int) -> Force | None:
    """Get a specific force by ID with all relationships loaded."""
    ensure_lance_header_colors(force_id)
    with session_scope() as session:
        force = session.get(Force, force_id)
        if force:
            # Eager load relationships
            for lance in force.lances:
                _ = lance.miniatures
                for fm in lance.miniatures:
                    _ = fm.miniature
            # Expunge to make accessible outside session
            session.expunge(force)
        return force


def create_force(name: str) -> Force:
    """Create a new force and set it as active, deactivating others."""
    with session_scope() as session:
        # Deactivate all existing forces
        session.query(Force).update({"is_active": False})

        # Create new force as active
        force = Force(name=name, is_active=True)
        session.add(force)
        session.flush()
        logger.info("force_created", force_id=force.id, name=name)

        # Eager load relationships (even if empty) so object is accessible outside session
        _ = force.lances  # Access to load even if empty list

        # Expunge to make accessible outside session
        session.expunge(force)
        return force


def switch_force(force_id: int) -> Force | None:
    """Activate a specific force and deactivate all others."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return None

        # Deactivate all forces
        session.query(Force).update({"is_active": False})

        # Activate selected force
        force.is_active = True
        force.updated_at = datetime.now(UTC)
        session.flush()
        return force


def deactivate_all_forces() -> None:
    """Deactivate all forces (clear active selection)."""
    with session_scope() as session:
        session.query(Force).update({"is_active": False})


def rename_force(force_id: int, new_name: str) -> Force | None:
    """Rename a force."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return None

        force.name = new_name.strip()
        force.updated_at = datetime.now(UTC)
        session.flush()
        return force


def delete_force(force_id: int) -> bool:
    """Delete a force and all its lances/assignments."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return False
        session.delete(force)
        logger.info("force_deleted", force_id=force_id)
        return True


def add_miniature_to_lance(
    miniature_id: int, lance_id: int, position: int | None = None
) -> dict[str, Any]:
    """Add a miniature to a lance, validating uniqueness within the force."""
    with session_scope() as session:
        lance = session.get(Lance, lance_id)
        if not lance:
            return {"success": False, "error": "Lance not found"}

        miniature = session.get(Miniature, miniature_id)
        if not miniature:
            return {"success": False, "error": "Miniature not found"}

        # Check if miniature already in this force
        existing = (
            session.query(ForceMiniature)
            .join(Lance)
            .filter(
                and_(Lance.force_id == lance.force_id, ForceMiniature.miniature_id == miniature_id)
            )
            .first()
        )

        if existing:
            logger.warning(
                "miniature_already_in_force", miniature_id=miniature_id, force_id=lance.force_id
            )
            return {
                "success": False,
                "error": f"Miniature already in force (Lance: {existing.lance.name or 'Unnamed'})",
            }

        # Determine position
        if position is None:
            max_order = (
                session.query(func.max(ForceMiniature.order))
                .filter(ForceMiniature.lance_id == lance_id)
                .scalar()
            ) or 0
            position = max_order + 1

        # Add miniature
        fm = ForceMiniature(lance_id=lance_id, miniature_id=miniature_id, order=position)
        session.add(fm)
        session.flush()

        return {"success": True, "force_miniature_id": fm.id}


def remove_miniature_from_force(miniature_id: int, force_id: int) -> bool:
    """Remove a miniature from any lance in the force."""
    with session_scope() as session:
        # First, find the ForceMiniature records to delete
        force_miniatures = (
            session.query(ForceMiniature)
            .join(Lance)
            .filter(and_(Lance.force_id == force_id, ForceMiniature.miniature_id == miniature_id))
            .all()
        )

        # Delete each record
        deleted_count = 0
        for fm in force_miniatures:
            session.delete(fm)
            deleted_count += 1

        return deleted_count > 0


def move_miniature_between_lances(
    miniature_id: int, target_lance_id: int, position: int
) -> dict[str, Any]:
    """Move a miniature to a different lance and position."""
    with session_scope() as session:
        target_lance = session.get(Lance, target_lance_id)
        if not target_lance:
            return {"success": False, "error": "Target lance not found"}

        # Find existing assignment
        fm = (
            session.query(ForceMiniature)
            .join(Lance)
            .filter(
                and_(
                    Lance.force_id == target_lance.force_id,
                    ForceMiniature.miniature_id == miniature_id,
                )
            )
            .first()
        )

        if not fm:
            return {"success": False, "error": "Miniature not in this force"}

        # Update assignment
        fm.lance_id = target_lance_id
        fm.order = position
        session.flush()

        return {"success": True}


def create_empty_lance(force_id: int, name: str | None = None) -> Lance | None:
    """Create an empty lance in a force."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return None

        # Get next order number
        max_order = (
            session.query(func.max(Lance.order)).filter(Lance.force_id == force_id).scalar()
        ) or 0

        used_colors = {
            c
            for c in session.execute(
                select(Lance.header_color).where(Lance.force_id == force_id)
            ).scalars()
            if c
        }
        lance = Lance(
            force_id=force_id,
            name=name,
            order=max_order + 1,
            header_color=pick_lance_header_color(used_colors),
        )
        session.add(lance)
        session.flush()

        # Eager load relationships (even if empty list) so object is accessible outside session
        _ = lance.miniatures

        # Expunge to make accessible outside session
        session.expunge(lance)
        return lance


def delete_lance(lance_id: int) -> bool:
    """Delete a lance and unassign all miniatures."""
    with session_scope() as session:
        lance = session.get(Lance, lance_id)
        if not lance:
            return False
        session.delete(lance)
        logger.info("lance_deleted", lance_id=lance_id)
        return True


def get_force_miniature_assignments(force_id: int) -> dict[int, ForceMiniatureAssignment]:
    """Map miniature IDs to their lance assignment in a force."""
    with session_scope() as session:
        rows = session.execute(
            select(
                ForceMiniature.miniature_id,
                Lance.name,
                Lance.header_color,
                Lance.order,
            )
            .join(Lance, ForceMiniature.lance_id == Lance.id)
            .where(Lance.force_id == force_id)
        ).all()
        return {
            mini_id: ForceMiniatureAssignment(
                lance_name=name or f"Lance {order}",
                lance_color=header_color,
            )
            for mini_id, name, header_color, order in rows
        }


def get_miniatures_in_force(force_id: int) -> set[int]:
    """Get set of miniature IDs currently in the force."""
    return set(get_force_miniature_assignments(force_id).keys())


def ensure_lance_header_colors(force_id: int) -> None:
    """Assign header colors to lances that do not have one yet."""
    with session_scope() as session:
        lances = list(
            session.execute(select(Lance).where(Lance.force_id == force_id)).scalars().all()
        )
        used_colors = {l.header_color for l in lances if l.header_color}
        updated = False
        for lance in lances:
            if lance.header_color:
                continue
            lance.header_color = pick_lance_header_color(used_colors)
            used_colors.add(lance.header_color)
            updated = True
        if updated:
            session.flush()


def set_inventory_faction(force_id: int, faction: str | None) -> Force | None:
    """Set or clear the inventory faction tag for force building."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return None

        cleaned: str | None
        if faction is None:
            cleaned = None
        else:
            stripped = faction.strip()
            cleaned = None if not stripped or stripped.lower() == "none" else stripped

        force.inventory_faction = cleaned
        force.updated_at = datetime.now(UTC)
        session.flush()
        session.expunge(force)
        return force


def get_inventory_candidates(force_id: int) -> list[InventoryCandidate]:
    """Miniatures matching the force inventory faction with availability flags."""
    force = get_force_by_id(force_id)
    if not force or not force.inventory_faction:
        return []

    mul_filters = alpha_strike_service.get_mul_filters_for_force(force_id)
    mul_lookup: dict[tuple[str, int | None], bool] | None = None

    with session_scope() as session:
        miniatures = list(
            session.execute(
                select(Miniature)
                .where(Miniature.faction == force.inventory_faction)
                .order_by(Miniature.series, Miniature.unique_id)
            )
            .scalars()
            .all()
        )

        assignment_rows = session.execute(
            select(
                ForceMiniature.miniature_id,
                Lance.name,
                Lance.id,
                Lance.header_color,
            )
            .join(Lance, ForceMiniature.lance_id == Lance.id)
            .where(Lance.force_id == force_id)
        ).all()
        lance_by_mini_id = {
            row[0]: {"name": row[1], "id": row[2], "color": row[3]} for row in assignment_rows
        }

        for mini in miniatures:
            session.expunge(mini)

    if mul_filters and miniatures:
        keys = {
            (m.chassis, mul_service.map_miniature_type_to_mul(m.type)) for m in miniatures
        }
        mul_lookup = mul_service.batch_chassis_availability(
            keys,
            faction_id=mul_filters[0],
            era_id=mul_filters[1],
        )

    candidates: list[InventoryCandidate] = []
    for mini in miniatures:
        lance_info = lance_by_mini_id.get(mini.id)
        in_force = lance_info is not None
        mul_available: bool | None = None
        if not in_force and mul_lookup is not None:
            key = (mini.chassis, mul_service.map_miniature_type_to_mul(mini.type))
            mul_available = mul_lookup.get(key, False)

        candidates.append(
            InventoryCandidate(
                miniature=mini,
                in_force=in_force,
                lance_name=lance_info["name"] if lance_info else None,
                lance_id=lance_info["id"] if lance_info else None,
                lance_color=lance_info["color"] if lance_info else None,
                mul_available=mul_available,
            )
        )

    return candidates


def summarize_inventory_candidates(candidates: list[InventoryCandidate]) -> dict[str, int]:
    """Counts for the inventory pool summary line."""
    total = len(candidates)
    in_force = sum(1 for c in candidates if c.in_force)
    mul_available = sum(1 for c in candidates if c.mul_available is True and not c.in_force)
    not_in_mul = sum(1 for c in candidates if c.mul_available is False and not c.in_force)
    available = sum(1 for c in candidates if not c.in_force and c.mul_available is not False)
    return {
        "total": total,
        "in_force": in_force,
        "mul_available": mul_available,
        "not_in_mul": not_in_mul,
        "available": available,
    }


def _assignment_to_export_dict(assignment: AlphaStrikeAssignment) -> dict[str, Any]:
    snapshot = json.loads(assignment.mul_snapshot_json)
    return {
        "mul_unit_id": assignment.mul_unit_id,
        "variant": assignment.variant,
        "class_name": assignment.class_name,
        "tonnage": assignment.tonnage,
        "point_value": assignment.point_value,
        "unit_type_id": assignment.unit_type_id,
        "unit_type_name": assignment.unit_type_name,
        "display_name": assignment.display_name,
        "mul_snapshot": snapshot,
    }


def export_force_to_json(force_id: int) -> tuple[str, str]:
    """Export force to JSON string with generated filename.

    Returns:
        tuple: (json_string, filename)
    """
    force = get_force_by_id(force_id)
    if not force:
        raise ValueError("Force not found")

    as_config = alpha_strike_service.get_alpha_strike_force(force_id)
    assignments = alpha_strike_service.get_assignments_for_force(force_id)

    export_data: dict[str, Any] = {
        "schema_version": FORCE_SCHEMA_VERSION,
        "force_name": force.name,
        "inventory_faction": force.inventory_faction,
        "export_timestamp": datetime.now(UTC).isoformat(),
        "lances": [],
    }

    if as_config:
        export_data["alpha_strike"] = {
            "mul_faction_id": as_config.mul_faction_id,
            "mul_era_id": as_config.mul_era_id,
            "faction_name": as_config.faction_name,
            "era_name": as_config.era_name,
            "point_budget": as_config.point_budget,
            "fudge_percent": as_config.fudge_percent,
        }

    for lance in force.lances:
        lance_data: dict[str, Any] = {
            "name": lance.name,
            "order": lance.order,
            "header_color": lance.header_color,
            "miniatures": [],
        }

        for fm in lance.miniatures:
            mini = fm.miniature
            mini_data: dict[str, Any] = {
                "series": mini.series,
                "unique_id": mini.unique_id,
                "prefix": mini.prefix,
                "chassis": mini.chassis,
                "type": mini.type,
                "faction": mini.faction,
                "tray_id": mini.tray_id,
                "order": fm.order,
            }
            assignment = assignments.get(fm.id)
            if assignment:
                mini_data["alpha_strike"] = _assignment_to_export_dict(assignment)
            lance_data["miniatures"].append(mini_data)

        export_data["lances"].append(lance_data)

    logger.info("force_exported", force_id=force_id, force_name=force.name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in force.name)
    filename = f"Force_{safe_name}_{timestamp}.json"

    json_string = json.dumps(export_data, indent=2)
    return json_string, filename


def _resolve_lance_header_color(lance_data: dict[str, Any], used_colors: set[str]) -> str:
    exported = lance_data.get("header_color")
    if exported and exported not in used_colors:
        return exported
    return pick_lance_header_color(used_colors)


def _restore_alpha_strike_config(
    session, force_id: int, config: dict[str, Any]
) -> None:
    session.add(
        AlphaStrikeForce(
            force_id=force_id,
            mul_faction_id=int(config["mul_faction_id"]),
            mul_era_id=int(config["mul_era_id"]),
            faction_name=config.get("faction_name") or "",
            era_name=config.get("era_name") or "",
            point_budget=config.get("point_budget"),
            fudge_percent=int(config.get("fudge_percent", alpha_strike_service.DEFAULT_FUDGE_PERCENT)),
        )
    )


def _restore_alpha_strike_assignment(
    session, force_miniature_id: int, assignment_data: dict[str, Any]
) -> None:
    snapshot = assignment_data.get("mul_snapshot")
    if snapshot is None and assignment_data.get("mul_snapshot_json"):
        snapshot = json.loads(assignment_data["mul_snapshot_json"])
    if not isinstance(snapshot, dict):
        raise ValueError("Alpha Strike assignment is missing mul_snapshot")

    session.add(
        AlphaStrikeAssignment(
            force_miniature_id=force_miniature_id,
            mul_unit_id=int(assignment_data["mul_unit_id"]),
            variant=assignment_data["variant"],
            class_name=assignment_data["class_name"],
            tonnage=int(assignment_data["tonnage"]),
            point_value=int(assignment_data["point_value"]),
            unit_type_id=assignment_data.get("unit_type_id"),
            unit_type_name=assignment_data.get("unit_type_name"),
            display_name=assignment_data["display_name"],
            mul_snapshot_json=json.dumps(snapshot),
        )
    )


def import_force_from_json(file_path: str) -> dict[str, Any]:
    """Import force from JSON file, matching miniatures by series+unique_id."""
    filepath = Path(file_path)

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise ValueError(f"File not found: {file_path}") from err

    force_name = data.get("force_name", "Imported Force")
    schema_version = int(data.get("schema_version") or 1)

    with session_scope() as session:
        force = Force(
            name=force_name,
            inventory_faction=data.get("inventory_faction") if schema_version >= 2 else None,
            is_active=False,
        )
        session.add(force)
        session.flush()

        missing_miniatures = []
        imported_count = 0
        used_lance_colors: set[str] = set()
        pending_assignments: list[tuple[int, dict[str, Any]]] = []

        for lance_data in data.get("lances", []):
            header_color = (
                _resolve_lance_header_color(lance_data, used_lance_colors)
                if schema_version >= 2
                else pick_lance_header_color(used_lance_colors)
            )
            used_lance_colors.add(header_color)
            lance = Lance(
                force_id=force.id,
                name=lance_data.get("name"),
                order=lance_data.get("order", 0),
                header_color=header_color,
            )
            session.add(lance)
            session.flush()

            for mini_data in lance_data.get("miniatures", []):
                miniature = (
                    session.query(Miniature)
                    .filter(
                        and_(
                            Miniature.series == mini_data["series"],
                            Miniature.unique_id == mini_data["unique_id"],
                        )
                    )
                    .first()
                )

                if miniature:
                    fm = ForceMiniature(
                        lance_id=lance.id,
                        miniature_id=miniature.id,
                        order=mini_data.get("order", 0),
                    )
                    session.add(fm)
                    session.flush()
                    imported_count += 1

                    assignment_data = mini_data.get("alpha_strike")
                    if schema_version >= 2 and assignment_data:
                        pending_assignments.append((fm.id, assignment_data))
                else:
                    missing_miniatures.append((mini_data["series"], mini_data["unique_id"]))

        as_config = data.get("alpha_strike")
        if schema_version >= 2 and as_config:
            _restore_alpha_strike_config(session, force.id, as_config)

        for fm_id, assignment_data in pending_assignments:
            _restore_alpha_strike_assignment(session, fm_id, assignment_data)

        session.flush()
        logger.info(
            "force_imported",
            force_name=force.name,
            lance_count=imported_count,
            missing_count=len(missing_miniatures),
        )

        return {
            "success": True,
            "force_id": force.id,
            "force_name": force.name,
            "imported_miniatures": imported_count,
            "missing_miniatures": missing_miniatures,
        }
