"""Service-level tests for miniature_service.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import inventory_project_service
from app.services.miniature_service import (
    _upgrade_miniature_schema,
    add_miniature,
    bulk_update_miniatures,
    get_all_miniatures,
    update_miniature,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add(
    series: str = "A",
    unique_id: int = 1,
    prefix: str = "WHM",
    chassis: str = "Warhammer",
    faction: str | None = None,
    status: str = "New",
) -> None:
    add_miniature(
        {
            "series": series,
            "unique_id": unique_id,
            "prefix": prefix,
            "chassis": chassis,
            "type": "Mech",
            "faction": faction,
            "status": status,
        }
    )


def _write_json(data, tmp_dir: str) -> str:
    """Write *data* to a temporary JSON file and return its path."""
    p = Path(tmp_dir) / "test_import.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


# ===========================================================================
# get_all_miniatures – filter / sort branches
# ===========================================================================


def test_get_all_miniatures_series_filter(client):
    """Series filter limits results to the matching series."""
    _add(series="A", unique_id=1)
    _add(series="B", unique_id=1, chassis="Atlas")

    result = get_all_miniatures(series_filter="A")
    assert all(m.series == "A" for m in result)
    assert len(result) == 1


def test_get_all_miniatures_series_filter_all(client):
    """series_filter='All' returns all series."""
    _add(series="A", unique_id=1)
    _add(series="B", unique_id=1, chassis="Atlas")

    result = get_all_miniatures(series_filter="All")
    assert len(result) == 2


def test_get_all_miniatures_faction_filter(client):
    """Faction filter returns only miniatures with the matching faction."""
    _add(unique_id=1, faction="Clan Wolf")
    _add(unique_id=2, chassis="Atlas", faction="Davion")

    result = get_all_miniatures(faction_filter="Clan Wolf")
    assert len(result) == 1
    assert result[0].faction == "Clan Wolf"


def test_get_all_miniatures_faction_filter_all(client):
    """faction_filter='All' returns all factions."""
    _add(unique_id=1, faction="Clan Wolf")
    _add(unique_id=2, chassis="Atlas", faction="Davion")

    result = get_all_miniatures(faction_filter="All")
    assert len(result) == 2


def test_get_all_miniatures_search_query_text(client):
    """Text search matches chassis name case-insensitively."""
    _add(unique_id=1, chassis="Warhammer")
    _add(unique_id=2, chassis="Atlas")

    result = get_all_miniatures(search_query="warhammer")
    assert len(result) == 1
    assert result[0].chassis == "Warhammer"


def test_get_all_miniatures_search_query_digit(client):
    """Numeric search string also matches unique_id."""
    _add(unique_id=42, chassis="Warhammer")
    _add(unique_id=7, chassis="Atlas")

    result = get_all_miniatures(search_query="42")
    assert any(m.unique_id == 42 for m in result)


def test_get_all_miniatures_search_no_match(client):
    """Search that matches nothing returns an empty list."""
    _add(unique_id=1)
    result = get_all_miniatures(search_query="zzznomatch")
    assert result == []


def test_get_all_miniatures_sort_asc(client):
    """sort + direction='asc' returns results in ascending order."""
    _add(unique_id=2, chassis="Banshee")
    _add(unique_id=1, chassis="Atlas")

    result = get_all_miniatures(sort="chassis", direction="asc")
    chassis_names = [m.chassis for m in result]
    assert chassis_names == sorted(chassis_names)


def test_get_all_miniatures_sort_desc(client):
    """sort + direction='desc' returns results in descending order."""
    _add(unique_id=1, chassis="Atlas")
    _add(unique_id=2, chassis="Warhammer")

    result = get_all_miniatures(sort="chassis", direction="desc")
    chassis_names = [m.chassis for m in result]
    assert chassis_names == sorted(chassis_names, reverse=True)


def test_get_all_miniatures_invalid_sort_falls_back(client):
    """An unrecognised sort column falls back to series/unique_id default."""
    _add(unique_id=2)
    _add(unique_id=1, chassis="Atlas")

    result = get_all_miniatures(sort="nonexistent_col")
    assert result[0].unique_id == 1
    assert result[1].unique_id == 2


# ===========================================================================
# update_miniature – not-found branch
# ===========================================================================


def test_update_miniature_not_found(client):
    """update_miniature returns None when the id does not exist."""
    result = update_miniature(99999, {"chassis": "Atlas"})
    assert result is None


# ===========================================================================
# bulk_update_miniatures
# ===========================================================================


def test_bulk_update_disallowed_field_raises(client):
    """bulk_update_miniatures raises ValueError for fields not in BULK_ALLOWED_FIELDS."""
    _add(unique_id=1)
    minis = get_all_miniatures()
    ids = [m.id for m in minis]

    with pytest.raises(ValueError, match="Bulk update not permitted"):
        bulk_update_miniatures(ids, "notes", "anything")


def test_bulk_update_empty_ids_returns_zero(client):
    """bulk_update_miniatures with an empty id list returns 0 without touching the DB."""
    count = bulk_update_miniatures([], "status", "Painted")
    assert count == 0


def test_bulk_update_status(client):
    """bulk_update_miniatures updates status for all given ids."""
    _add(unique_id=1, status="New")
    _add(unique_id=2, chassis="Atlas", status="New")
    minis = get_all_miniatures()
    ids = [m.id for m in minis]

    updated = bulk_update_miniatures(ids, "status", "Painted")
    assert updated == 2
    refreshed = get_all_miniatures()
    assert all(m.status == "Painted" for m in refreshed)


def test_bulk_update_faction(client):
    """bulk_update_miniatures updates faction for all given ids."""
    _add(unique_id=1, faction="Clan Wolf")
    _add(unique_id=2, chassis="Atlas", faction="Davion")
    minis = get_all_miniatures()
    ids = [m.id for m in minis]

    bulk_update_miniatures(ids, "faction", "Free Rasalhague")
    refreshed = get_all_miniatures()
    assert all(m.faction == "Free Rasalhague" for m in refreshed)


def test_bulk_update_clears_field_on_empty_value(client):
    """Passing an empty string as value should null out the field."""
    _add(unique_id=1, faction="Clan Wolf")
    minis = get_all_miniatures()
    ids = [m.id for m in minis]

    bulk_update_miniatures(ids, "faction", "")
    refreshed = get_all_miniatures()
    assert refreshed[0].faction is None


# ===========================================================================
# _upgrade_miniature_schema / inventory load
# ===========================================================================


def test_upgrade_schema_v1_dict(client):
    """_upgrade_miniature_schema extracts the list from a v1 envelope dict."""
    payload = {"schema_version": 1, "miniatures": [{"chassis": "Warhammer"}]}
    result = _upgrade_miniature_schema(payload)
    assert result == [{"chassis": "Warhammer"}]


def test_upgrade_schema_v0_list(client):
    """_upgrade_miniature_schema passes a bare list through unchanged."""
    payload = [{"chassis": "Atlas"}]
    result = _upgrade_miniature_schema(payload)
    assert result == payload


def test_load_legacy_miniatures_via_project_service(client, tmp_path):
    """Legacy miniature list JSON loads through inventory_project_service."""
    _add(unique_id=1)
    _add(unique_id=2, chassis="Atlas")

    new_data = [
        {"series": "A", "unique_id": 99, "chassis": "Timber Wolf", "prefix": "TBR", "type": "Mech"}
    ]
    path = _write_json(new_data, tmp_path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result = inventory_project_service.load_project_from_data(payload)
    assert result["miniatures"] == 1
    minis = get_all_miniatures()
    assert len(minis) == 1
    assert minis[0].chassis == "Timber Wolf"


def test_load_legacy_skips_invalid_unique_id(client):
    """Invalid unique_id records are skipped when loading inventory."""
    payload = [
        {"series": "A", "unique_id": "bad-id", "chassis": "Warhammer", "type": "Mech"},
        {"series": "A", "unique_id": 5, "chassis": "Atlas", "type": "Mech"},
    ]
    result = inventory_project_service.load_project_from_data(payload)
    assert result["miniatures"] == 1
    assert get_all_miniatures()[0].chassis == "Atlas"


def test_load_legacy_v1_envelope(client):
    envelope = {
        "schema_version": 1,
        "miniatures": [
            {"series": "A", "unique_id": 7, "chassis": "Marauder", "prefix": "MAD", "type": "Mech"}
        ],
    }
    result = inventory_project_service.load_project_from_data(envelope)
    assert result["miniatures"] == 1
    assert get_all_miniatures()[0].chassis == "Marauder"


def test_load_legacy_rejects_invalid_root(client):
    with pytest.raises(ValueError, match="Invalid project file format"):
        inventory_project_service.load_project_from_data("not-a-list")


def test_load_legacy_defaults_series_to_a(client):
    payload = [{"unique_id": 3, "chassis": "Vulture", "prefix": "VT", "type": "Mech"}]
    inventory_project_service.load_project_from_data(payload)
    assert get_all_miniatures()[0].series == "A"


# ===========================================================================
# add_miniature – series default branch
# ===========================================================================


def test_add_miniature_defaults_series_when_missing(client):
    """add_miniature assigns series 'A' when the key is absent."""
    add_miniature({"unique_id": 1, "chassis": "Shadow Hawk", "prefix": "SHD", "type": "Mech"})
    minis = get_all_miniatures()
    assert minis[0].series == "A"


def test_add_miniature_defaults_series_when_empty(client):
    """add_miniature assigns series 'A' when series is an empty string."""
    add_miniature(
        {"series": "", "unique_id": 2, "chassis": "Griffin", "prefix": "GRF", "type": "Mech"}
    )
    minis = get_all_miniatures()
    assert minis[0].series == "A"


# ===========================================================================
# delete_miniature – not-found branch
# ===========================================================================


def test_delete_miniature_not_found_returns_false(client):
    """delete_miniature returns False when the id does not exist."""
    from app.services.miniature_service import delete_miniature

    result = delete_miniature(99999)
    assert result is False
