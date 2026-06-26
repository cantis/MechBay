"""Restore linked documents and reconcile dirty state on application startup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from . import document_service, force_service, inventory_project_service
from .lance_template_service import get_all_templates
from .miniature_service import get_all_miniatures

logger = structlog.get_logger()

_startup_messages: list[tuple[str, str]] = []


def consume_startup_messages() -> list[tuple[str, str]]:
    """Return and clear one-shot startup flash messages."""
    global _startup_messages
    messages = list(_startup_messages)
    _startup_messages = []
    return messages


def inventory_has_data() -> bool:
    """Return True when the database has any inventory, template, or force data."""
    if get_all_miniatures():
        return True
    if get_all_templates():
        return True
    if force_service.get_all_forces():
        return True
    return False


def _resolve_existing_path(path_str: str) -> Path | None:
    path = Path(path_str)
    if path.is_file():
        return path.resolve()
    return None


def _json_equal(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _inventory_content_key(data: dict[str, Any]) -> dict[str, Any]:
    normalized = inventory_project_service.normalize_inventory_payload(data)
    templates = []
    for template in normalized.get("templates") or []:
        templates.append(
            {
                "name": template.get("name"),
                "description": template.get("description"),
                "chassis_patterns": list(template.get("chassis_patterns") or []),
            }
        )
    miniatures = normalized.get("miniatures") or []
    return {
        "miniatures": sorted(
            miniatures,
            key=lambda item: (item.get("series"), item.get("unique_id")),
        ),
        "templates": sorted(templates, key=lambda item: item.get("name") or ""),
        "settings": dict(normalized.get("settings") or {}),
    }


def inventory_matches_file(path: Path) -> bool:
    """Return True when the database inventory matches the linked file content."""
    try:
        file_data = json.loads(path.read_text(encoding="utf-8"))
        db_data = inventory_project_service.build_project_data()
        return _json_equal(_inventory_content_key(file_data), _inventory_content_key(db_data))
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return False


def _force_content_key(data: dict[str, Any]) -> dict[str, Any]:
    filtered = dict(data)
    filtered.pop("export_timestamp", None)
    return filtered


def force_matches_file(force_id: int, path: Path) -> bool:
    """Return True when the database force matches the linked file content."""
    try:
        file_data = json.loads(path.read_text(encoding="utf-8"))
        export_json, _ = force_service.export_force_to_json(force_id)
        export_data = json.loads(export_json)
        return _json_equal(_force_content_key(file_data), _force_content_key(export_data))
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return False


def _queue_startup_messages(result: dict[str, Any]) -> None:
    for message in result.get("info") or []:
        _startup_messages.append(("info", message))
    for message in result.get("warnings") or []:
        _startup_messages.append(("warning", message))


def restore_session() -> dict[str, Any]:
    """Validate linked files, restore empty databases, and reconcile dirty flags."""
    result: dict[str, Any] = {
        "inventory_restored": False,
        "inventory_path": None,
        "dirty_cleared_inventory": False,
        "dirty_cleared_force_ids": [],
        "forces_pruned": 0,
        "paths_pruned": 0,
        "warnings": [],
        "info": [],
    }

    state = document_service.load_state()
    db_empty = not inventory_has_data()

    if db_empty and state.inventory_path:
        inv_path = _resolve_existing_path(state.inventory_path)
        if inv_path:
            try:
                with document_service.suppress_dirty_tracking():
                    inventory_project_service.load_project_from_path(inv_path)
                result["inventory_restored"] = True
                result["inventory_path"] = str(inv_path)
                result["info"].append(f"Restored inventory from {inv_path.name}")
                state = document_service.load_state()
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(
                    "session_restore_inventory_failed",
                    path=state.inventory_path,
                    exc_info=True,
                )
                result["warnings"].append(f"Could not restore inventory: {exc}")
                document_service.set_inventory_path(None)
                state = document_service.load_state()
        else:
            result["warnings"].append(
                f"Linked inventory file not found: {Path(state.inventory_path).name}"
            )
            document_service.set_inventory_path(None)
            state = document_service.load_state()

    if state.inventory_path and not result["inventory_restored"]:
        inv_path = _resolve_existing_path(state.inventory_path)
        if inv_path is None:
            result["warnings"].append(
                f"Linked inventory file not found: {Path(state.inventory_path).name}"
            )
            document_service.set_inventory_path(None)
            state = document_service.load_state()
        elif state.inventory_dirty and inventory_matches_file(inv_path):
            document_service.clear_inventory_dirty()
            result["dirty_cleared_inventory"] = True

    state = document_service.load_state()
    valid_force_paths: dict[str, str] = {}
    dirty_force_ids = list(state.dirty_force_ids)

    for force_id_str, file_path in state.force_paths.items():
        force_id = int(force_id_str)
        force = force_service.get_force_by_id(force_id)
        resolved = _resolve_existing_path(file_path)

        if force is None:
            result["forces_pruned"] += 1
            if force_id in dirty_force_ids:
                dirty_force_ids.remove(force_id)
            continue

        if resolved is None:
            result["paths_pruned"] += 1
            result["warnings"].append(f"Force file not found: {Path(file_path).name}")
            if force_id in dirty_force_ids:
                dirty_force_ids.remove(force_id)
            continue

        valid_force_paths[force_id_str] = file_path
        if force_id in dirty_force_ids and force_matches_file(force_id, resolved):
            dirty_force_ids.remove(force_id)
            result["dirty_cleared_force_ids"].append(force_id)

    if valid_force_paths != state.force_paths or dirty_force_ids != state.dirty_force_ids:
        state.force_paths = valid_force_paths
        state.dirty_force_ids = dirty_force_ids
        document_service.save_state(state)

    log_payload = {k: v for k, v in result.items() if k not in ("warnings", "info")}
    logger.info("session_restored", **log_payload)
    _queue_startup_messages(result)
    return result
