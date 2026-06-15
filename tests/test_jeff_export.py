from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import patch

import pytest

from app.services import alpha_strike_service, force_service
from app.services.jeff_export_service import (
    JeffExportError,
    build_jeff_member,
    export_jeff_force_zip,
    export_jeff_lance,
    parse_bf_move,
)

SAMPLE_MUL_RAW = {
    "Id": 7563,
    "Name": "Warhammer WHM-8R",
    "Class": "Warhammer",
    "Variant": "WHM-8R",
    "Tonnage": 70,
    "BFPointValue": 40,
    "BFMove": '8"',
    "BFArmor": 5,
    "BFStructure": 4,
    "BFThreshold": 2,
    "BFDamageShort": 4,
    "BFDamageMedium": 4,
    "BFDamageLong": 2,
    "BFDamageExtreme": 0,
    "BFAbilities": "IF, SRM",
    "Type": {"Id": 18, "Name": "BattleMech"},
    "Role": {"Name": "Brawler"},
}


def test_parse_bf_move_walk_and_jump():
    move, jump = parse_bf_move('10"/6"j')
    assert jump == 6
    assert move == [{"move": 10, "currentMove": 10, "type": "Walk"}]


def test_parse_bf_move_walk_only():
    move, jump = parse_bf_move('8"')
    assert jump == 0
    assert move[0]["move"] == 8


def test_build_jeff_member_required_fields():
    member = build_jeff_member(
        assignment_raw=SAMPLE_MUL_RAW,
        lance_name="Alpha Lance",
        miniature_label="WHM Warhammer",
    )
    assert member["class"] == "Warhammer"
    assert member["variant"] == "WHM-8R"
    assert member["name"] == "Warhammer WHM-8R"
    assert member["customName"] == "Alpha Lance · WHM Warhammer"
    assert member["mulID"] == 7563
    assert member["basePoints"] == 40
    assert member["pilot"]["gunnery"] == 4
    assert member["pilot"]["piloting"] == 4
    assert member["damage"]["short"] == 4
    assert member["abilities"] == ["IF", "SRM"]


def _first_fm_id(force_id: int) -> int:
    force = force_service.get_force_by_id(force_id)
    return force.lances[0].miniatures[0].id


def _lance_id(force_id: int) -> int:
    force = force_service.get_force_by_id(force_id)
    return force.lances[0].id


def _assign_all_in_lance(force_id: int):
    alpha_strike_service.enable_alpha_strike(
        force_id,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )
    force = force_service.get_force_by_id(force_id)
    for fm in force.lances[0].miniatures:
        alpha_strike_service.assign_variant(
            force_id,
            fm.id,
            SAMPLE_MUL_RAW["Id"],
            search_name="Warhammer",
        )


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_lance_success(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    _assign_all_in_lance(minimal_force)

    json_string, filename = export_jeff_lance(_lance_id(minimal_force))
    data = json.loads(json_string)

    assert filename.endswith(".json")
    assert data["name"] == "Alpha Lance"
    assert len(data["members"]) == 2
    assert data["members"][0]["pilot"]["gunnery"] == 4


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_lance_blocks_unassigned(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )
    alpha_strike_service.assign_variant(
        minimal_force,
        _first_fm_id(minimal_force),
        SAMPLE_MUL_RAW["Id"],
        search_name="Warhammer",
    )

    with pytest.raises(JeffExportError, match="Assign Alpha Strike variants"):
        export_jeff_lance(_lance_id(minimal_force))


def test_export_jeff_lance_requires_alpha_strike(client, minimal_force):
    with pytest.raises(JeffExportError, match="Enable Alpha Strike"):
        export_jeff_lance(_lance_id(minimal_force))


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_force_zip(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    _assign_all_in_lance(minimal_force)

    zip_bytes, filename = export_jeff_force_zip(minimal_force)
    assert filename.endswith(".zip")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        assert names == ["Alpha Lance.json"]
        group = json.loads(archive.read("Alpha Lance.json"))
        assert group["name"] == "Alpha Lance"
        assert len(group["members"]) == 2


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_route_downloads_zip(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    _assign_all_in_lance(minimal_force)

    resp = client.get(f"/forces/{minimal_force}/export/jeff")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert "attachment" in resp.headers.get("Content-Disposition", "")


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_lance_route_downloads_json(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    _assign_all_in_lance(minimal_force)
    lance_id = _lance_id(minimal_force)

    resp = client.get(f"/forces/{minimal_force}/lances/{lance_id}/export/jeff")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    data = json.loads(resp.data)
    assert data["name"] == "Alpha Lance"


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_export_jeff_route_blocks_unassigned(mock_find, client, minimal_force):
    mock_find.return_value = SAMPLE_MUL_RAW
    alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )

    resp = client.get(f"/forces/{minimal_force}/export/jeff", follow_redirects=True)
    assert resp.status_code == 200
    assert "Assign Alpha Strike variants" in resp.get_data(as_text=True)
