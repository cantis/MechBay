from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from sqlalchemy import and_, or_, select

from ..extensions import session_scope
from ..models.miniature import Miniature


def get_next_unique_id(series: str) -> int:
    """Find the first unused unique_id in the given series.

    Returns the first gap in the sequence starting from 1, or max+1 if no gaps exist.
    Examples:
    - Empty series: returns 1
    - [1, 2, 3]: returns 4
    - [1, 2, 4, 5]: returns 3 (fills gap)
    - [2, 3, 4]: returns 1 (fills start)

    Args:
        series: Series identifier (e.g., 'A', 'B', 'C')

    Returns:
        First unused unique_id integer
    """
    with session_scope() as session:
        # Get all existing unique_ids for this series, sorted
        existing_ids = (
            session.query(Miniature.unique_id)
            .filter(Miniature.series == series)
            .order_by(Miniature.unique_id)
            .all()
        )

        # Extract integers from query result tuples
        existing_set = {row[0] for row in existing_ids}

        # Find first gap starting from 1
        candidate = 1
        while candidate in existing_set:
            candidate += 1

        return candidate


def get_all_miniatures(
    search_query: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    series_filter: str | None = None,
    faction_filter: str | None = None,
    page: int | None = None,
    per_page: int = 50,
) -> Sequence[Miniature] | tuple[Sequence[Miniature], int]:
    """Return miniatures matching the given filters.

    When *page* is provided returns a ``(items, total_count)`` tuple suitable
    for pagination.  When *page* is ``None`` (default) the full result set is
    returned as a plain sequence (preserves backward compatibility)."""
    with session_scope() as session:
        stmt = select(Miniature)

        # Series filter
        if series_filter and series_filter != "All":
            stmt = stmt.where(Miniature.series == series_filter)

        # Faction filter
        if faction_filter and faction_filter != "All":
            stmt = stmt.where(Miniature.faction == faction_filter)

        # Search query (case-insensitive)
        if search_query:
            like = f"%{search_query}%"
            conditions = [
                Miniature.prefix.ilike(like),
                Miniature.chassis.ilike(like),
                Miniature.type.ilike(like),
                Miniature.faction.ilike(like),
                Miniature.notes.ilike(like),
            ]
            # If the search query is an integer, match unique_id exactly
            if search_query.isdigit():
                conditions.append(Miniature.unique_id == int(search_query))
            stmt = stmt.where(or_(*conditions))

        # Sorting logic
        valid_sort_columns = {
            "series": Miniature.series,
            "unique_id": Miniature.unique_id,
            "prefix": Miniature.prefix,
            "chassis": Miniature.chassis,
            "type": Miniature.type,
            "faction": Miniature.faction,
            "status": Miniature.status,
            "tray_id": Miniature.tray_id,
        }
        if sort in valid_sort_columns:
            col = valid_sort_columns[sort]
            if direction == "desc":
                stmt = stmt.order_by(col.desc())
            elif direction == "asc":
                stmt = stmt.order_by(col.asc())
        else:
            # Default sort: series ASC, then unique_id ASC
            stmt = stmt.order_by(Miniature.series.asc(), Miniature.unique_id.asc())

        if page is not None:
            from sqlalchemy import func as sa_func

            count_stmt = select(sa_func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar_one()
            offset = (page - 1) * per_page
            items = session.execute(stmt.offset(offset).limit(per_page)).scalars().all()
            return items, total

        return session.execute(stmt).scalars().all()


def get_distinct_factions() -> list[str]:
    """Get list of unique faction values (excluding nulls and empty strings).

    Returns:
        list[str]: Sorted list of faction names
    """
    with session_scope() as session:
        stmt = (
            select(Miniature.faction)
            .distinct()
            .where(Miniature.faction.isnot(None))
            .where(Miniature.faction != "")
            .order_by(Miniature.faction)
        )
        result = session.execute(stmt).scalars().all()
        return list(result)


def add_miniature(data: dict) -> Miniature:
    with session_scope() as session:
        # Ensure series defaults to "A" if not provided
        if "series" not in data or not data["series"]:
            data["series"] = "A"
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


BULK_ALLOWED_FIELDS = {"status", "faction"}


def bulk_update_miniatures(ids: list[int], field: str, value: str) -> int:
    """Update a single field on multiple miniatures.

    Only *status* and *faction* are permitted to prevent unsafe mass-edits.

    Returns:
        int: Number of records updated.
    """
    if field not in BULK_ALLOWED_FIELDS:
        raise ValueError(f"Bulk update not permitted for field '{field}'")
    if not ids:
        return 0
    with session_scope() as session:
        updated = (
            session.query(Miniature)
            .filter(Miniature.id.in_(ids))
            .update({field: value or None}, synchronize_session="fetch")
        )
        return updated


def delete_miniature(id: int) -> bool:  # noqa: A002
    with session_scope() as session:
        mini = session.get(Miniature, id)
        if not mini:
            return False
        session.delete(mini)
        return True


MINIATURE_SCHEMA_VERSION = 1


def export_to_json() -> str:
    """Export all miniatures to JSON string.

    Returns:
        str: JSON string with schema_version and miniatures array
    """
    minis = get_all_miniatures()
    export_data = {
        "schema_version": MINIATURE_SCHEMA_VERSION,
        "miniatures": [m.to_dict() for m in minis],
    }
    return json.dumps(export_data, indent=2)


def _upgrade_miniature_schema(data: list | dict) -> list:
    """Normalise any schema version to a plain list of miniature dicts."""
    if isinstance(data, list):
        # v0: bare array (no schema_version)
        return data
    # v1+: object with schema_version + miniatures key
    return data.get("miniatures", [])


def import_from_json(path: str, merge: bool = False) -> int:
    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    items = _upgrade_miniature_schema(raw)
    if not isinstance(items, Iterable):  # basic sanity
        raise ValueError("JSON must be a list of miniature objects")

    imported = 0
    with session_scope() as session:
        if not merge:
            # Clear existing
            session.query(Miniature).delete()

        for item in items:
            raw_unique_id = item.get("unique_id")
            # Coerce to int; skip if cannot convert
            try:
                unique_id = int(raw_unique_id) if raw_unique_id is not None else None
            except (TypeError, ValueError):
                continue  # skip invalid record

            # Default series to "A" if not in import data
            series = item.get("series", "A")
            if not series:
                series = "A"

            if merge and unique_id is not None:
                # Match on BOTH series and unique_id for merge
                existing = (
                    session.query(Miniature)
                    .filter(and_(Miniature.series == series, Miniature.unique_id == unique_id))
                    .first()
                )
                if existing:
                    for k, v in item.items():
                        if hasattr(existing, k):
                            # Ensure we don't accidentally write string unique_id back
                            if k == "unique_id":
                                continue
                            setattr(existing, k, v)
                    continue
            mini = Miniature(
                series=series,
                unique_id=unique_id,
                prefix=item.get("prefix"),
                chassis=item.get("chassis"),
                type=item.get("type"),
                faction=item.get("faction"),
                status=item.get("status"),
                tray_id=item.get("tray_id"),
                notes=item.get("notes"),
            )
            session.add(mini)
            imported += 1
        session.flush()
    return imported
