from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..extensions import session_scope
from ..models.lance_template import LanceTemplate
from ..models.lance_template_miniature import LanceTemplateMiniature
from ..models.miniature import Miniature


def get_all_templates() -> list[LanceTemplate]:
    """Get all available lance templates."""
    with session_scope() as session:
        stmt = select(LanceTemplate).order_by(LanceTemplate.name)
        templates = list(session.execute(stmt).scalars().all())
        # Eager load miniatures and expunge to detach from session
        for template in templates:
            _ = template.miniatures
            session.expunge(template)
        return templates


def get_template_details(template_id: int) -> LanceTemplate | None:
    """Get template with all miniature patterns."""
    with session_scope() as session:
        template = session.get(LanceTemplate, template_id)
        if template:
            _ = template.miniatures
            session.expunge(template)
        return template


def create_template(
    name: str, chassis_patterns: list[str], description: str | None = None
) -> LanceTemplate:
    """Create a new lance template with chassis patterns."""
    with session_scope() as session:
        template = LanceTemplate(name=name, description=description)
        session.add(template)
        session.flush()

        for idx, pattern in enumerate(chassis_patterns):
            mini = LanceTemplateMiniature(
                template_id=template.id, chassis_pattern=pattern, order=idx
            )
            session.add(mini)

        session.flush()
        session.expunge(template)
        return template


def update_template(
    template_id: int, name: str, chassis_patterns: list[str], description: str | None = None
) -> LanceTemplate | None:
    """Update an existing lance template."""
    with session_scope() as session:
        template = session.get(LanceTemplate, template_id)
        if not template:
            return None

        template.name = name
        template.description = description

        # Delete existing patterns
        session.query(LanceTemplateMiniature).filter(
            LanceTemplateMiniature.template_id == template_id
        ).delete()

        # Add new patterns
        for idx, pattern in enumerate(chassis_patterns):
            mini = LanceTemplateMiniature(
                template_id=template.id, chassis_pattern=pattern, order=idx
            )
            session.add(mini)

        session.flush()
        session.expunge(template)
        return template


def delete_template(template_id: int) -> bool:
    """Delete a lance template."""
    with session_scope() as session:
        template = session.get(LanceTemplate, template_id)
        if not template:
            return False
        session.delete(template)
        return True


def find_matching_miniature(
    chassis_pattern: str, exclude_ids: set[int] | None = None
) -> Miniature | None:
    """Find first available miniature matching chassis pattern (partial match)."""
    if exclude_ids is None:
        exclude_ids = set()

    with session_scope() as session:
        stmt = select(Miniature).where(Miniature.chassis.like(f"%{chassis_pattern}%"))

        if exclude_ids:
            stmt = stmt.where(Miniature.id.not_in(exclude_ids))

        return session.execute(stmt).scalars().first()


def match_template_miniatures(
    template_id: int, exclude_ids: set[int] | None = None
) -> dict[str, Any]:
    """Match template patterns to available miniatures.

    Returns dict with:
    - matched: list of (chassis_pattern, miniature_id) tuples
    - missing: list of chassis_pattern strings
    """
    if exclude_ids is None:
        exclude_ids = set()

    template = get_template_details(template_id)
    if not template:
        return {"matched": [], "missing": []}

    matched = []
    missing = []
    used_ids = set(exclude_ids)

    for tm in template.miniatures:
        miniature = find_matching_miniature(tm.chassis_pattern, used_ids)
        if miniature:
            matched.append((tm.chassis_pattern, miniature.id, miniature))
            used_ids.add(miniature.id)
        else:
            missing.append(tm.chassis_pattern)

    return {"matched": matched, "missing": missing, "template_name": template.name}


def export_templates_to_json(directory: str = "lance_templates/") -> Path:
    """Export all lance templates to a JSON file."""
    templates = get_all_templates()

    # Create export directory if it doesn't exist
    export_dir = Path(directory)
    export_dir.mkdir(parents=True, exist_ok=True)

    # Build export data
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "template_count": len(templates),
        "templates": [],
    }

    for template in templates:
        template_data = {
            "name": template.name,
            "description": template.description,
            "chassis_patterns": [tm.chassis_pattern for tm in template.miniatures],
        }
        export_data["templates"].append(template_data)

    # Generate filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"LanceTemplates_{timestamp}.json"
    filepath = export_dir / filename

    # Write to file
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    return filepath


def import_templates_from_json(file_path: str) -> dict[str, Any]:
    """Import lance templates from a JSON file."""
    filepath = Path(file_path)

    if not filepath.exists():
        raise ValueError(f"File not found: {file_path}")

    # Read JSON file
    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "templates" not in data:
        raise ValueError("Invalid lance templates file format")

    imported_count = 0
    skipped_count = 0

    with session_scope() as session:
        for template_data in data["templates"]:
            name = template_data.get("name")
            description = template_data.get("description")
            chassis_patterns = template_data.get("chassis_patterns", [])

            if not name or not chassis_patterns:
                skipped_count += 1
                continue

            # Check if template with this name already exists
            existing = session.execute(
                select(LanceTemplate).where(LanceTemplate.name == name)
            ).scalar_one_or_none()

            if existing:
                # Update existing template
                existing.description = description

                # Delete existing patterns
                session.query(LanceTemplateMiniature).filter(
                    LanceTemplateMiniature.template_id == existing.id
                ).delete()

                # Add new patterns
                for idx, pattern in enumerate(chassis_patterns):
                    mini = LanceTemplateMiniature(
                        template_id=existing.id, chassis_pattern=pattern, order=idx
                    )
                    session.add(mini)
            else:
                # Create new template
                template = LanceTemplate(name=name, description=description)
                session.add(template)
                session.flush()

                for idx, pattern in enumerate(chassis_patterns):
                    mini = LanceTemplateMiniature(
                        template_id=template.id, chassis_pattern=pattern, order=idx
                    )
                    session.add(mini)

            imported_count += 1

    return {
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "total_in_file": len(data["templates"]),
    }
