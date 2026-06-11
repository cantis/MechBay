from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services import alpha_strike_service, force_service
from app.services.alpha_strike_service import compute_budget_status


def test_compute_budget_status_none():
    status = compute_budget_status(0, 0, 0, None)
    assert status.status == "none"


def test_compute_budget_status_within():
    status = compute_budget_status(380, 10, 2, 400, fudge_percent=2)
    assert status.status == "within"
    assert status.effective_budget == 408


def test_compute_budget_status_over_fudge():
    status = compute_budget_status(405, 10, 0, 400, fudge_percent=2)
    assert status.status == "over_fudge"


def test_compute_budget_status_over_hard():
    status = compute_budget_status(420, 10, 0, 400, fudge_percent=2)
    assert status.status == "over_hard"


def test_enable_alpha_strike(client, minimal_force):
    as_force = alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )
    assert as_force.faction_name == "Federated Suns"
    assert as_force.era_name == "Jihad"
    assert as_force.point_budget == 400


def test_enable_alpha_strike_invalid_faction(client, minimal_force):
    with pytest.raises(ValueError, match="Invalid faction"):
        alpha_strike_service.enable_alpha_strike(
            minimal_force,
            mul_faction_id=99999,
            mul_era_id=14,
        )


def _first_fm_id(force_id: int) -> int:
    force = force_service.get_force_by_id(force_id)
    return force.lances[0].miniatures[0].id


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_assign_variant(mock_find, client, minimal_force):
    alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )
    fm_id = _first_fm_id(minimal_force)
    mock_find.return_value = {
        "Id": 7563,
        "Name": "Warhammer WHM-8R",
        "Class": "Warhammer",
        "Variant": "WHM-8R",
        "Tonnage": 70,
        "BFPointValue": 40,
        "Type": {"Id": 18, "Name": "BattleMech"},
        "Role": {"Name": "Brawler"},
    }

    assignment = alpha_strike_service.assign_variant(
        minimal_force,
        fm_id,
        7563,
        search_name="Warhammer",
    )
    assert assignment.variant == "WHM-8R"
    assert assignment.point_value == 40
    assert json.loads(assignment.mul_snapshot_json)["Id"] == 7563

    summary = alpha_strike_service.get_force_summary(minimal_force)
    assert summary.total_pv == 40
    assert summary.configured_count == 1
    assert summary.unconfigured_count == 1


def test_enable_route(client, minimal_force):
    resp = client.post(
        f"/forces/{minimal_force}/alpha-strike/enable",
        data={
            "mul_faction_id": 29,
            "mul_era_id": 14,
            "point_budget": 400,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Alpha Strike configuration saved" in resp.get_data(as_text=True)


@patch("app.services.alpha_strike_service.mul_service.find_unit_in_search_results")
def test_assign_route(mock_find, client, minimal_force):
    alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
    )
    fm_id = _first_fm_id(minimal_force)
    mock_find.return_value = {
        "Id": 1,
        "Name": "Test Mech TM-1",
        "Class": "Test",
        "Variant": "TM-1",
        "Tonnage": 50,
        "BFPointValue": 25,
        "Type": {"Id": 18, "Name": "BattleMech"},
        "Role": {"Name": "Brawler"},
    }

    resp = client.post(
        f"/forces/{minimal_force}/alpha-strike/assign",
        json={
            "force_miniature_id": fm_id,
            "mul_unit_id": 1,
            "search_name": "Test",
        },
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["assignment"]["point_value"] == 25


def test_report_shows_alpha_strike_data(client, minimal_force):
    alpha_strike_service.enable_alpha_strike(
        minimal_force,
        mul_faction_id=29,
        mul_era_id=14,
        point_budget=400,
    )
    resp = client.get(f"/forces/{minimal_force}/report")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Federated Suns" in body
    assert "Jihad" in body
