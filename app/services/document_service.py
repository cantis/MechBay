"""Track linked file paths and dirty state for inventory and force documents."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

INVENTORY_EXTENSION = ".mechbay"
FORCE_EXTENSION = ".mbforce"
STATE_FILENAME = "documents.json"

_suppress_dirty = False


def get_app_data_dir() -> Path:
    docker = Path("/data")
    if docker.exists():
        return docker
    path = Path.home() / "AppData" / "Roaming" / "MechBay"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return get_app_data_dir() / STATE_FILENAME


@dataclass
class DocumentState:
    inventory_path: str | None = None
    inventory_dirty: bool = False
    force_paths: dict[str, str] = field(default_factory=dict)  # force_id str -> path
    dirty_force_ids: list[int] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DocumentState:
        if not data:
            return cls()
        return cls(
            inventory_path=data.get("inventory_path"),
            inventory_dirty=bool(data.get("inventory_dirty")),
            force_paths=dict(data.get("force_paths") or {}),
            dirty_force_ids=[int(x) for x in data.get("dirty_force_ids") or []],
            settings=dict(data.get("settings") or {}),
        )


def load_state() -> DocumentState:
    path = _state_path()
    if not path.exists():
        return DocumentState()
    try:
        return DocumentState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        logger.warning("document_state_load_failed", path=str(path))
        return DocumentState()


def save_state(state: DocumentState) -> None:
    path = _state_path()
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def get_status() -> dict[str, Any]:
    state = load_state()
    inventory_label = "Untitled"
    if state.inventory_path:
        inventory_label = Path(state.inventory_path).name
    if state.inventory_dirty:
        inventory_label = f"{inventory_label} *"

    dirty_forces = set(state.dirty_force_ids)
    force_files = []
    for force_id_str, file_path in state.force_paths.items():
        label = Path(file_path).name
        if int(force_id_str) in dirty_forces:
            label = f"{label} *"
        force_files.append(
            {"force_id": int(force_id_str), "path": file_path, "label": label}
        )

    return {
        "inventory_path": state.inventory_path,
        "inventory_label": inventory_label,
        "inventory_dirty": state.inventory_dirty,
        "force_paths": state.force_paths,
        "dirty_force_ids": state.dirty_force_ids,
        "settings": state.settings,
        "force_files": force_files,
    }


def mark_inventory_dirty() -> None:
    if _suppress_dirty:
        return
    state = load_state()
    if not state.inventory_dirty:
        state.inventory_dirty = True
        save_state(state)


def clear_inventory_dirty() -> None:
    state = load_state()
    state.inventory_dirty = False
    save_state(state)


def set_inventory_path(path: str | None) -> None:
    state = load_state()
    state.inventory_path = path
    save_state(state)


def mark_force_dirty(force_id: int) -> None:
    if _suppress_dirty:
        return
    state = load_state()
    if force_id not in state.dirty_force_ids:
        state.dirty_force_ids.append(force_id)
        save_state(state)


def clear_force_dirty(force_id: int) -> None:
    state = load_state()
    if force_id in state.dirty_force_ids:
        state.dirty_force_ids = [fid for fid in state.dirty_force_ids if fid != force_id]
        save_state(state)


def set_force_path(force_id: int, path: str | None) -> None:
    state = load_state()
    key = str(force_id)
    if path:
        state.force_paths[key] = path
    else:
        state.force_paths.pop(key, None)
    save_state(state)


def remove_force_document(force_id: int) -> None:
    state = load_state()
    state.force_paths.pop(str(force_id), None)
    state.dirty_force_ids = [fid for fid in state.dirty_force_ids if fid != force_id]
    save_state(state)


def clear_all_force_documents() -> None:
    state = load_state()
    state.force_paths = {}
    state.dirty_force_ids = []
    save_state(state)


def update_settings(settings: dict[str, Any]) -> None:
    state = load_state()
    state.settings.update(settings)
    save_state(state)


def get_setting(key: str, default: Any = None) -> Any:
    return load_state().settings.get(key, default)


def inventory_display_name() -> str:
    return get_status()["inventory_label"]


@contextmanager
def suppress_dirty_tracking() -> Iterator[None]:
    """Prevent dirty flags while loading or seeding data."""
    global _suppress_dirty
    previous = _suppress_dirty
    _suppress_dirty = True
    try:
        yield
    finally:
        _suppress_dirty = previous
