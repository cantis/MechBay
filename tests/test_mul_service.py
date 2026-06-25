from __future__ import annotations

from unittest.mock import patch

from app.services.mul_service import (
    card_from_raw,
    get_eras,
    get_factions,
    map_miniature_type_to_mul,
    parse_mul_unit,
    search_variants,
    tmm_from_move,
)


def test_reference_data_loads():
    factions = get_factions()
    eras = get_eras()
    assert any(f["name"] == "Federated Suns" for f in factions)
    assert any(f["name"] == "Mercenary" for f in factions)
    assert any(e["name"] == "Jihad" for e in eras)
    assert all(f["name"] for f in factions)


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
        "BFMove": '8"',
        "BFArmor": 5,
        "Type": {"Id": 18, "Name": "BattleMech"},
        "Role": {"Name": "Brawler"},
    }
    unit = parse_mul_unit(raw)
    assert unit.variant == "WHM-8R"
    assert unit.point_value == 40
    assert unit.unit_type_name == "BattleMech"

    card = card_from_raw(raw)
    assert card["bf_move"] == '8"'
    assert card["bf_armor"] == 5
    assert card["bf_tmm"] == 1
    assert "Unit/Details/1" in card["mul_url"]


def test_tmm_from_move():
    assert tmm_from_move('4"') == 0
    assert tmm_from_move('8"') == 1
    assert tmm_from_move('10"/6"j') == 2
    assert tmm_from_move('16"j') == 3
    assert tmm_from_move('20"') == 4
    assert tmm_from_move(None) is None


def test_card_from_raw_derives_tmm_when_mul_omits_it():
    raw = {
        "Id": 7495,
        "BFMove": '16"j',
        "BFTMM": 0,
    }
    card = card_from_raw(raw)
    assert card["bf_tmm"] == 3


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
                "BFMove": '8"',
                "Type": {"Id": 18, "Name": "BattleMech"},
                "Role": {"Name": "Brawler"},
            }
        ]
    }
    units = search_variants("Warhammer", faction_id=29, era_id=14, unit_type_id=18)
    assert len(units) == 1
    assert units[0]["point_value"] == 40
    assert units[0]["card"]["bf_move"] == '8"'
    mock_fetch.assert_called_once()
