"""Master Unit List (MUL) client with local caching.

Uses the community-documented QuickList JSON endpoint. Responses are cached in
the database so variant lookups work offline after the first fetch.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from ..extensions import session_scope
from ..models.mul_cache import MulCache

logger = structlog.get_logger()

MUL_QUICKLIST_URL = "https://masterunitlist.azurewebsites.net/Unit/QuickList"
CACHE_TTL_DAYS = 7
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class MulUnit:
    id: int
    name: str
    class_name: str
    variant: str
    tonnage: int
    point_value: int
    unit_type_id: int | None
    unit_type_name: str | None
    role: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "class_name": self.class_name,
            "variant": self.variant,
            "tonnage": self.tonnage,
            "point_value": self.point_value,
            "unit_type_id": self.unit_type_id,
            "unit_type_name": self.unit_type_name,
            "role": self.role,
        }


def _load_json(filename: str) -> list[dict] | dict:
    return json.loads((_DATA_DIR / filename).read_text(encoding="utf-8"))


def get_factions() -> list[dict]:
    return _load_json("mul_factions.json")  # type: ignore[return-value]


def get_eras() -> list[dict]:
    return _load_json("mul_eras.json")  # type: ignore[return-value]


def get_faction_by_id(faction_id: int) -> dict | None:
    return next((f for f in get_factions() if f["id"] == faction_id), None)


def get_era_by_id(era_id: int) -> dict | None:
    return next((e for e in get_eras() if e["id"] == era_id), None)


def map_miniature_type_to_mul(miniature_type: str | None) -> int | None:
    if not miniature_type:
        return None
    mapping = _load_json("mul_unit_types.json")
    entry = mapping.get(miniature_type.strip())
    if entry:
        return entry["id"]
    normalized = miniature_type.strip().lower()
    for key, value in mapping.items():
        if key.lower() == normalized:
            return value["id"]
    return None


def _build_cache_key(params: dict[str, str | int]) -> str:
    ordered = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha256(ordered.encode()).hexdigest()


def parse_mul_unit(raw: dict[str, Any]) -> MulUnit:
    unit_type = raw.get("Type") or {}
    role = raw.get("Role") or {}
    return MulUnit(
        id=raw["Id"],
        name=raw.get("Name", ""),
        class_name=raw.get("Class", ""),
        variant=raw.get("Variant", ""),
        tonnage=int(raw.get("Tonnage") or 0),
        point_value=int(raw.get("BFPointValue") or 0),
        unit_type_id=unit_type.get("Id"),
        unit_type_name=unit_type.get("Name"),
        role=role.get("Name") if role.get("Name") != "None" else None,
    )


def _get_cached_response(cache_key: str) -> dict | None:
    with session_scope() as session:
        row = session.get(MulCache, cache_key)
        if not row:
            return None
        age = datetime.now(UTC) - row.fetched_at.replace(tzinfo=UTC)
        if age > timedelta(days=CACHE_TTL_DAYS):
            return None
        return json.loads(row.response_json)


def _store_cached_response(cache_key: str, payload: dict) -> None:
    with session_scope() as session:
        row = session.get(MulCache, cache_key)
        if row:
            row.response_json = json.dumps(payload)
            row.fetched_at = datetime.now(UTC)
        else:
            session.add(
                MulCache(
                    cache_key=cache_key,
                    response_json=json.dumps(payload),
                    fetched_at=datetime.now(UTC),
                )
            )


def _fetch_quicklist(params: dict[str, str | int]) -> dict:
    cache_key = _build_cache_key(params)
    cached = _get_cached_response(cache_key)
    if cached is not None:
        logger.debug("mul_cache_hit", cache_key=cache_key[:12])
        return cached

    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{MUL_QUICKLIST_URL}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("mul_fetch_failed", url=url, error=str(exc))
        raise RuntimeError("Master Unit List is unavailable") from exc

    _store_cached_response(cache_key, payload)
    return payload


def search_variants(
    name: str,
    *,
    faction_id: int,
    era_id: int,
    unit_type_id: int | None = None,
) -> list[MulUnit]:
    """Search MUL for variants matching chassis name, faction, and era."""
    params: dict[str, str | int] = {
        "Name": name.strip(),
        "Factions": faction_id,
        "AvailableEras": era_id,
    }
    if unit_type_id is not None:
        params["Types"] = unit_type_id

    payload = _fetch_quicklist(params)
    units = [parse_mul_unit(u) for u in payload.get("Units", [])]
    # Prefer entries with Alpha Strike point values
    return sorted(units, key=lambda u: (-(u.point_value > 0), u.variant))


def get_unit_snapshot(mul_unit_id: int) -> dict[str, Any]:
    """Fetch a single unit by MUL id (used when assigning a variant)."""
    payload = _fetch_quicklist({"Name": str(mul_unit_id)})
    for raw in payload.get("Units", []):
        if raw.get("Id") == mul_unit_id:
            return raw
    raise ValueError(f"MUL unit {mul_unit_id} not found")


def find_unit_in_search_results(
    name: str,
    mul_unit_id: int,
    *,
    faction_id: int,
    era_id: int,
    unit_type_id: int | None = None,
) -> dict[str, Any]:
    """Return raw MUL JSON for a unit id from a filtered search."""
    params: dict[str, str | int] = {
        "Name": name.strip(),
        "Factions": faction_id,
        "AvailableEras": era_id,
    }
    if unit_type_id is not None:
        params["Types"] = unit_type_id
    payload = _fetch_quicklist(params)
    for raw in payload.get("Units", []):
        if raw.get("Id") == mul_unit_id:
            return raw
    raise ValueError(f"Variant id {mul_unit_id} not found for {name!r}")
