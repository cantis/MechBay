from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from sqlalchemy import or_, select

from ..extensions import session_scope
from ..models.miniature import Miniature


def get_all_miniatures(
    search_query: str | None = None, sort: str | None = None, direction: str | None = None
) -> Sequence[Miniature]:
    with session_scope() as session:
        stmt = select(Miniature)
        if search_query:
            like = f"%{search_query}%"
            stmt = stmt.where(
                or_(
                    Miniature.unique_id.like(like),
                    Miniature.prefix.like(like),
                    Miniature.chassis.like(like),
                    Miniature.type.like(like),
                )
            )
        # Sorting logic
        valid_sort_columns = {
            "unique_id": Miniature.unique_id,
            "prefix": Miniature.prefix,
            "chassis": Miniature.chassis,
            "type": Miniature.type,
            "status": Miniature.status,
            "tray_id": Miniature.tray_id,
        }
        if sort in valid_sort_columns:
            col = valid_sort_columns[sort]
            if direction == "desc":
                stmt = stmt.order_by(col.desc())
            elif direction == "asc":
                stmt = stmt.order_by(col.asc())
        return session.execute(stmt).scalars().all()


def add_miniature(data: dict) -> Miniature:
    with session_scope() as session:
        mini = Miniature(**data)
        session.add(mini)
        session.flush()  # populate PK
        return mini


def update_miniature(id: int, data: dict) -> Miniature | None:  # noqa: A002
    with session_scope() as session:
        mini = session.get(Miniature, id)
        if not mini:
            return None
        for k, v in data.items():
            if hasattr(mini, k):
                setattr(mini, k, v)
        session.flush()
        return mini


def delete_miniature(id: int) -> bool:  # noqa: A002
    with session_scope() as session:
        mini = session.get(Miniature, id)
        if not mini:
            return False
        session.delete(mini)
        return True


def export_to_json(path: str) -> Path:
    minis = get_all_miniatures()
    data = [m.to_dict() for m in minis]
    target = Path(path)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target


def import_from_json(path: str, merge: bool = False) -> int:
    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Iterable):  # basic sanity
        raise ValueError("JSON must be a list of miniature objects")

    imported = 0
    with session_scope() as session:
        if not merge:
            # Clear existing
            session.query(Miniature).delete()

        for item in raw:
            unique_id = item.get("unique_id")
            if merge and unique_id:
                existing = session.query(Miniature).filter(Miniature.unique_id == unique_id).first()
                if existing:
                    for k, v in item.items():
                        if hasattr(existing, k):
                            setattr(existing, k, v)
                    continue
            mini = Miniature(
                unique_id=item.get("unique_id"),
                prefix=item.get("prefix"),
                chassis=item.get("chassis"),
                type=item.get("type"),
                status=item.get("status"),
                tray_id=item.get("tray_id"),
                notes=item.get("notes"),
            )
            session.add(mini)
            imported += 1
        session.flush()
    return imported
