from __future__ import annotations

from unittest.mock import patch

from app.services.mul_service import (
    get_eras,
    get_factions,
    map_miniature_type_to_mul,
    parse_mul_unit,
    search_variants,
)


def test_reference_data_loads():
    factions = get_factions()
    eras = get_eras()
    assert any(f["name"] == "Federated Suns" for f in factions)
    assert any(e["name"] == "Jihad" for e in eras)


def test_map_miniature_type_to_mul():
    assert map_miniature_type_to_mul("Mech") == 18
    assert map_miniature_type_to_mul("Vehicle") == 19
    assert map_miniature_type_to_mul("Unknown Type") is None


def test_parse_mul_unit():
    raw = {
        "Id": 1,
        "Name": "Warhammer WHM-8R",
        "Class": "Warhammer",
        "Variant": "WHM-8R",
        "Tonnage": 70,
        "BFPointValue": 40,
        "Type": {"Id": 18, "Name": "BattleMech"},
        "Role": {"Name": "Brawler"},
    }
    unit = parse_mul_unit(raw)
    assert unit.variant == "WHM-8R"
    assert unit.point_value == 40
    assert unit.unit_type_name == "BattleMech"


@patch("app.services.mul_service._fetch_quicklist")
def test_search_variants_uses_cache_layer(mock_fetch, client):
    mock_fetch.return_value = {
        "Units": [
            {
                "Id": 99,
                "Name": "Warhammer WHM-8R",
                "Class": "Warhammer",
                "Variant": "WHM-8R",
                "Tonnage": 70,
                "BFPointValue": 40,
                "Type": {"Id": 18, "Name": "BattleMech"},
                "Role": {"Name": "Brawler"},
            }
        ]
    }
    units = search_variants("Warhammer", faction_id=29, era_id=14, unit_type_id=18)
    assert len(units) == 1
    assert units[0].point_value == 40
    mock_fetch.assert_called_once()
