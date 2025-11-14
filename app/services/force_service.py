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
        deleted = (
            session.query(ForceMiniature)
            .join(Lance)
            .filter(and_(Lance.force_id == force_id, ForceMiniature.miniature_id == miniature_id))
            .delete(synchronize_session=False)
        )
        return deleted > 0


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


def export_force_to_json(force_id: int, directory: str = "forces/") -> Path:
    """Export force to JSON file with structure."""
    force = get_force_by_id(force_id)
    if not force:
        raise ValueError(f"Force {force_id} not found")

    # Build export structure
    export_data = {
        "force_name": force.name,
        "exported_at": datetime.utcnow().isoformat(),
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
                    "tray_id": mini.tray_id,
                    "order": fm.order,
                }
            )

        export_data["lances"].append(lance_data)

    # Create directory if needed
    Path(directory).mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in force.name)
    filename = f"force-{safe_name}-{timestamp}.json"
    filepath = Path(directory) / filename

    # Write file
    filepath.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
    return filepath


def import_force_from_json(file_path: str) -> dict[str, Any]:
    """Import force from JSON file, matching miniatures by series+unique_id."""
    filepath = Path(file_path)
    data = json.loads(filepath.read_text(encoding="utf-8"))

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
                    missing_miniatures.append(
                        f"{mini_data['series']}-{mini_data['unique_id']} ({mini_data['chassis']})"
                    )

        session.flush()

        return {
            "success": True,
            "force_id": force.id,
            "force_name": force.name,
            "imported_count": imported_count,
            "missing_miniatures": missing_miniatures,
        }
