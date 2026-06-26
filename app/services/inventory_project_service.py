"""Save and load .mechbay inventory project files."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from ..extensions import session_scope
from ..models.lance_template import LanceTemplate
from ..models.lance_template_miniature import LanceTemplateMiniature
from ..models.miniature import Miniature
from . import document_service, force_service
from .miniature_service import _upgrade_miniature_schema, get_all_miniatures

logger = structlog.get_logger()

INVENTORY_PROJECT_SCHEMA_VERSION = 2
PROJECT_TYPE = "inventory"

_EXPORT_MINIATURE_KEYS = (
    "series",
    "unique_id",
    "prefix",
    "chassis",
    "type",
    "faction",
    "status",
    "tray_id",
    "notes",
)


def _normalize_inventory_payload(data: Any) -> dict[str, Any]:
    """Accept .mechbay and legacy miniature or template JSON exports.

    Legacy shapes: bare miniature list, v1 ``{miniatures: [...]}``, or template-only exports.
    """
    if isinstance(data, list):
        return {
            "schema_version": INVENTORY_PROJECT_SCHEMA_VERSION,
            "type": PROJECT_TYPE,
            "miniatures": data,
            "templates": [],
        }

    if not isinstance(data, dict):
        raise ValueError("Invalid project file format")

    if data.get("force_name") or "lances" in data:
        raise ValueError("This is a force file. Use File → Open force instead.")

    if data.get("type") == PROJECT_TYPE:
        return data

    templates = data.get("templates")
    if "miniatures" in data:
        miniatures = _upgrade_miniature_schema(data)
    elif templates is not None:
        miniatures = []
    else:
        raise ValueError("Invalid project file: missing miniatures")

    if templates is None:
        templates = []
    if not isinstance(templates, list):
        raise ValueError("Invalid templates section in project file")

    settings = data.get("settings")
    if settings is not None and not isinstance(settings, dict):
        raise ValueError("Invalid settings section in project file")

    return {
        "schema_version": data.get("schema_version", INVENTORY_PROJECT_SCHEMA_VERSION),
        "type": PROJECT_TYPE,
        "miniatures": miniatures,
        "templates": templates,
        "settings": settings or {},
    }


def build_project_data() -> dict[str, Any]:
    """Build the in-memory project document from the current database."""
    minis = get_all_miniatures()
    miniatures = [{k: getattr(m, k) for k in _EXPORT_MINIATURE_KEYS} for m in minis]

    from .lance_template_service import get_all_templates

    templates = []
    for template in get_all_templates():
        templates.append(
            {
                "name": template.name,
                "description": template.description,
                "chassis_patterns": [tm.chassis_pattern for tm in template.miniatures],
            }
        )

    state = document_service.load_state()
    name = "Untitled"
    if state.inventory_path:
        name = Path(state.inventory_path).stem

    return {
        "schema_version": INVENTORY_PROJECT_SCHEMA_VERSION,
        "type": PROJECT_TYPE,
        "name": name,
        "saved_at": datetime.now(UTC).isoformat(),
        "settings": dict(state.settings),
        "miniatures": miniatures,
        "templates": templates,
    }


def save_project_to_path(path: str | Path) -> None:
    """Write the current inventory project to a .mechbay file."""
    file_path = Path(path)
    if file_path.suffix.lower() != document_service.INVENTORY_EXTENSION:
        file_path = file_path.with_suffix(document_service.INVENTORY_EXTENSION)

    payload = build_project_data()
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    document_service.set_inventory_path(str(file_path.resolve()))
    document_service.clear_inventory_dirty()
    logger.info("inventory_project_saved", path=str(file_path))


def _replace_miniatures(items: list[dict[str, Any]]) -> int:
    with session_scope() as session:
        session.query(Miniature).delete()
        count = 0
        for item in items:
            try:
                unique_id = int(item["unique_id"])
            except (KeyError, TypeError, ValueError):
                continue
            series = item.get("series") or "A"
            mini = Miniature(
                series=series,
                unique_id=unique_id,
                prefix=item.get("prefix") or "",
                chassis=item.get("chassis") or "",
                type=item.get("type") or "Mech",
                faction=item.get("faction"),
                status=item.get("status"),
                tray_id=item.get("tray_id"),
                notes=item.get("notes"),
            )
            session.add(mini)
            count += 1
        return count


def _replace_templates(templates: list[dict[str, Any]]) -> int:
    with session_scope() as session:
        session.query(LanceTemplateMiniature).delete()
        session.query(LanceTemplate).delete()
        count = 0
        for template_data in templates:
            name = template_data.get("name")
            patterns = template_data.get("chassis_patterns") or []
            if not name or not patterns:
                continue
            template = LanceTemplate(
                name=name,
                description=template_data.get("description"),
            )
            session.add(template)
            session.flush()
            for idx, pattern in enumerate(patterns):
                session.add(
                    LanceTemplateMiniature(
                        template_id=template.id,
                        chassis_pattern=pattern,
                        order=idx,
                    )
                )
            count += 1
        return count


def load_project_from_path(path: str | Path) -> dict[str, Any]:
    """Replace inventory from a .mechbay file and clear all forces."""
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"File not found: {path}")

    data = json.loads(file_path.read_text(encoding="utf-8"))
    return load_project_from_data(data, source_path=str(file_path.resolve()))


def load_project_from_data(
    data: dict[str, Any], *, source_path: str | None = None
) -> dict[str, Any]:
    """Replace inventory from project data and clear all forces."""
    data = _normalize_inventory_payload(data)

    miniatures = data.get("miniatures")
    if not isinstance(miniatures, list):
        raise ValueError("Invalid miniatures section in project file")

    templates = data.get("templates")
    if templates is None:
        templates = []
    if not isinstance(templates, list):
        raise ValueError("Invalid templates section in project file")

    settings = data.get("settings")
    if settings is not None and not isinstance(settings, dict):
        raise ValueError("Invalid settings section in project file")

    with document_service.suppress_dirty_tracking():
        force_service.delete_all_forces()
        document_service.clear_all_force_documents()

        mini_count = _replace_miniatures(miniatures)
        template_count = _replace_templates(templates)

    if settings:
        document_service.update_settings(settings)

    if source_path:
        document_service.set_inventory_path(source_path)
    document_service.clear_inventory_dirty()

    logger.info(
        "inventory_project_loaded",
        path=source_path,
        miniatures=mini_count,
        templates=template_count,
    )
    return {
        "miniatures": mini_count,
        "templates": template_count,
        "settings": settings or {},
    }


def new_inventory_project() -> None:
    """Clear inventory, templates, and forces for a new untitled project."""
    with document_service.suppress_dirty_tracking():
        force_service.delete_all_forces()
        document_service.clear_all_force_documents()
        with session_scope() as session:
            session.query(LanceTemplateMiniature).delete()
            session.query(LanceTemplate).delete()
            session.query(Miniature).delete()

    document_service.set_inventory_path(None)
    document_service.clear_inventory_dirty()
    logger.info("inventory_project_new")
