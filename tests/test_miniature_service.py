"""Service-level tests for miniature_service.py.

Covers branches not exercised by the route-level tests in test_miniatures.py:
- Filter / sort parameters on get_all_miniatures
- update_miniature with a missing record
- bulk_update_miniatures (invalid field, empty list, valid update)
- export_to_json / _upgrade_miniature_schema (v1 envelope)
- import_from_json (overwrite, merge, invalid-uid skip)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.miniature_service import (
    _upgrade_miniature_schema,
    add_miniature,
    bulk_update_miniatures,
    export_to_json,
    get_all_miniatures,
    import_from_json,
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
# export_to_json / _upgrade_miniature_schema
# ===========================================================================


def test_export_to_json_returns_schema_v1_envelope(client):
    """export_to_json wraps miniatures in a schema_version:1 envelope."""
    _add(unique_id=1)
    raw = export_to_json()
    data = json.loads(raw)
    assert data["schema_version"] == 1
    assert isinstance(data["miniatures"], list)
    assert len(data["miniatures"]) == 1


def test_export_to_json_empty_db(client):
    """export_to_json returns an empty miniatures list when the DB is empty."""
    raw = export_to_json()
    data = json.loads(raw)
    assert data["miniatures"] == []


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


# ===========================================================================
# import_from_json
# ===========================================================================


def test_import_from_json_overwrite(client, tmp_path):
    """import_from_json in overwrite mode replaces all existing miniatures."""
    _add(unique_id=1)
    _add(unique_id=2, chassis="Atlas")

    new_data = [
        {"series": "A", "unique_id": 99, "chassis": "Timber Wolf", "prefix": "TBR", "type": "Mech"}
    ]
    path = _write_json(new_data, tmp_path)

    count = import_from_json(path, merge=False)
    assert count == 1
    minis = get_all_miniatures()
    assert len(minis) == 1
    assert minis[0].chassis == "Timber Wolf"


def test_import_from_json_skips_invalid_unique_id(client, tmp_path):
    """import_from_json silently skips records with a non-integer unique_id."""
    items = [
        {
            "series": "A",
            "unique_id": "bad-id",
            "chassis": "Warhammer",
            "prefix": "WHM",
            "type": "Mech",
        },
        {"series": "A", "unique_id": 5, "chassis": "Atlas", "prefix": "AS7", "type": "Mech"},
    ]
    path = _write_json(items, tmp_path)

    count = import_from_json(path, merge=False)
    assert count == 1
    minis = get_all_miniatures()
    assert minis[0].chassis == "Atlas"


def test_import_from_json_merge_updates_existing(client, tmp_path):
    """import_from_json in merge mode updates a matching (series, unique_id) record."""
    _add(series="A", unique_id=1, chassis="Warhammer", status="New")

    updated_items = [
        {
            "series": "A",
            "unique_id": 1,
            "chassis": "Warhammer",
            "prefix": "WHM",
            "type": "Mech",
            "status": "Painted",
        }
    ]
    path = _write_json(updated_items, tmp_path)

    count = import_from_json(path, merge=True)
    # Merge-update of existing records returns 0 (no new inserts)
    assert count == 0
    minis = get_all_miniatures()
    assert len(minis) == 1
    assert minis[0].status == "Painted"


def test_import_from_json_merge_inserts_new(client, tmp_path):
    """import_from_json in merge mode inserts records that don't already exist."""
    _add(series="A", unique_id=1, chassis="Warhammer")

    new_items = [
        {"series": "A", "unique_id": 2, "chassis": "Atlas", "prefix": "AS7", "type": "Mech"}
    ]
    path = _write_json(new_items, tmp_path)

    count = import_from_json(path, merge=True)
    assert count == 1
    minis = get_all_miniatures()
    assert len(minis) == 2


def test_import_from_json_v1_envelope(client, tmp_path):
    """import_from_json accepts a schema v1 envelope (dict with schema_version)."""
    envelope = {
        "schema_version": 1,
        "miniatures": [
            {"series": "A", "unique_id": 7, "chassis": "Marauder", "prefix": "MAD", "type": "Mech"}
        ],
    }
    path = _write_json(envelope, tmp_path)

    count = import_from_json(path, merge=False)
    assert count == 1
    minis = get_all_miniatures()
    assert minis[0].chassis == "Marauder"


def test_import_from_json_rejects_invalid_root(client, tmp_path):
    """import_from_json raises ValueError when the JSON root is not a list or object."""
    path = Path(tmp_path) / "invalid.json"
    path.write_text(json.dumps("not-a-list"), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON must be a list or object"):
        import_from_json(str(path), merge=False)


def test_import_from_json_defaults_series_to_a(client, tmp_path):
    """Records without a 'series' key default to series 'A'."""
    items = [{"unique_id": 3, "chassis": "Vulture", "prefix": "VT", "type": "Mech"}]
    path = _write_json(items, tmp_path)

    import_from_json(path, merge=False)
    minis = get_all_miniatures()
    assert minis[0].series == "A"


def test_import_from_json_empty_series_defaults_to_a(client, tmp_path):
    """Records with series='' default to series 'A'."""
    items = [{"series": "", "unique_id": 5, "chassis": "Vulture", "prefix": "VT", "type": "Mech"}]
    path = _write_json(items, tmp_path)

    import_from_json(path, merge=False)
    minis = get_all_miniatures()
    assert minis[0].series == "A"


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
