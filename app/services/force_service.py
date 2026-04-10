"""Force management service for MechBay.

Provides CRUD operations for forces, lances, and miniature assignments.
Handles active force management and import/export functionality.

KNOWN LIMITATION - Thread Safety:
The active force invariant (only one Force.is_active=True) is enforced by
application logic without database-level constraints. Concurrent calls to
create_force() or switch_active_force() in a multi-threaded or multi-process
environment may result in multiple active forces due to race conditions.

Future considerations:
- SQLite limitation: Cannot enforce single-row constraint across table
- PostgreSQL solution: CREATE UNIQUE INDEX idx_one_active ON forces (is_active) WHERE is_active=true
- Add pessimistic row locking with SELECT FOR UPDATE when switching active
- Consider application-level distributed lock for multi-instance deployments
- Add database migration to create partial unique index when migrating to PostgreSQL
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, select

from ..extensions import session_scope
from ..models.force import Force
from ..models.force_miniature import ForceMiniature
from ..models.lance import Lance
from ..models.miniature import Miniature


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
        force.updated_at = datetime.utcnow()
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
        force.updated_at = datetime.utcnow()
        session.flush()
        return force


def delete_force(force_id: int) -> bool:
    """Delete a force and all its lances/assignments."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return False
        session.delete(force)
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

        lance = Lance(force_id=force_id, name=name, order=max_order + 1)
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
        return True


def get_miniatures_in_force(force_id: int) -> set[int]:
    """Get set of miniature IDs currently in the force."""
    with session_scope() as session:
        stmt = select(ForceMiniature.miniature_id).join(Lance).where(Lance.force_id == force_id)
        return set(session.execute(stmt).scalars().all())


def export_force_to_json(force_id: int) -> tuple[str, str]:
    """Export force to JSON string with generated filename.

    Returns:
        tuple: (json_string, filename)
    """
    force = get_force_by_id(force_id)
    if not force:
        raise ValueError("Force not found")

    FORCE_SCHEMA_VERSION = 1

    # Build export structure
    export_data = {
        "schema_version": FORCE_SCHEMA_VERSION,
        "force_name": force.name,
        "export_timestamp": datetime.utcnow().isoformat(),
        "lances": [],
    }

    for lance in force.lances:
        lance_data = {"name": lance.name, "order": lance.order, "miniatures": []}

        for fm in lance.miniatures:
            mini = fm.miniature
            lance_data["miniatures"].append(
                {
                    "series": mini.series,
                    "unique_id": mini.unique_id,
                    "prefix": mini.prefix,
                    "chassis": mini.chassis,
                    "type": mini.type,
                    "faction": mini.faction,
                    "tray_id": mini.tray_id,
                    "order": fm.order,
                }
            )

        export_data["lances"].append(lance_data)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in force.name)
    filename = f"Force_{safe_name}_{timestamp}.json"

    # Return JSON string and filename
    json_string = json.dumps(export_data, indent=2)
    return json_string, filename


def import_force_from_json(file_path: str) -> dict[str, Any]:
    """Import force from JSON file, matching miniatures by series+unique_id."""
    filepath = Path(file_path)

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise ValueError(f"File not found: {file_path}") from err

    force_name = data.get("force_name", "Imported Force")

    with session_scope() as session:
        # Create force
        force = Force(name=force_name, is_active=False)
        session.add(force)
        session.flush()

        missing_miniatures = []
        imported_count = 0

        for lance_data in data.get("lances", []):
            lance = Lance(
                force_id=force.id, name=lance_data.get("name"), order=lance_data.get("order", 0)
            )
            session.add(lance)
            session.flush()

            for mini_data in lance_data.get("miniatures", []):
                # Find miniature by series + unique_id
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
                    imported_count += 1
                else:
                    missing_miniatures.append((mini_data["series"], mini_data["unique_id"]))

        session.flush()

        return {
            "success": True,
            "force_id": force.id,
            "force_name": force.name,
            "imported_miniatures": imported_count,
            "missing_miniatures": missing_miniatures,
        }
