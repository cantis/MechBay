"""Aces Sortie Maximum PV: entered at setup, enforced on add, authoritative afterwards."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.extensions import session_scope
from app.models.campaign import Campaign
from app.models.campaign_pilot import CampaignPilot
from app.models.campaign_unit import CampaignUnit
from app.services import (
    aces_after_action_service as svc,
)
from app.services import (
    aces_sortie_service,
    campaign_service,
    contract_service,
)
from tests.conftest import apply_aces, finalize_aces
from tests.test_aces_after_sortie import _campaign

pytestmark = pytest.mark.no_default_pv


def _set_pv(campaign, *values):
    """Give the campaign units these Point Values (in order)."""
    with session_scope() as session:
        units = (
            session.query(CampaignUnit)
            .filter_by(campaign_id=campaign.id)
            .order_by(CampaignUnit.order, CampaignUnit.id)
            .all()
        )
        for unit, pv in zip(units, values, strict=True):
            unit.point_value = pv
    return campaign_service.get_campaign_by_id(campaign.id)


def _sortie(campaign, **kwargs):
    return campaign_service.create_aces_sortie(campaign.id, kwargs.pop("name", "Strike"), **kwargs)


def _ready(campaign, pilots, sortie):
    """Assign a pilot and commander so the only thing left to check is the PV."""
    rows = contract_service.get_sortie_by_id(sortie.id).units
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    return contract_service.mark_sortie_ready(sortie.id)


# --- entering the maximum ------------------------------------------------------------------


def test_sortie_cannot_be_ready_without_a_maximum_pv(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    sortie = _sortie(campaign)  # no scenario PV given
    assert sortie.max_sortie_pv is None
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    with pytest.raises(ValueError, match="Set the Sortie's Maximum PV"):
        _ready(campaign, pilots, sortie)
    aces_sortie_service.set_sortie_pv(sortie.id, max_pv=100)
    assert _ready(campaign, pilots, sortie).status == "ready"


def test_maximum_must_be_positive(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _sortie(campaign)
    for bad in (0, -5, "0"):
        with pytest.raises(ValueError, match="greater than zero"):
            aces_sortie_service.set_sortie_pv(sortie.id, max_pv=bad)
        with pytest.raises(ValueError, match="greater than zero"):
            aces_sortie_service.set_sortie_pv(sortie.id, scenario_pv=bad)
    with pytest.raises(ValueError, match="whole number"):
        aces_sortie_service.set_sortie_pv(sortie.id, max_pv="lots")
    with pytest.raises(ValueError, match="Enter the scenario PV"):
        aces_sortie_service.set_sortie_pv(sortie.id)
    assert contract_service.get_sortie_by_id(sortie.id).max_sortie_pv is None


def test_scenario_pv_is_adjusted_by_difficulty(client, minimal_force):
    campaign, _ = _campaign(minimal_force, difficulty="Veteran")  # -10%
    sortie = _sortie(campaign, scenario_pv=300)
    assert sortie.scenario_pv == 300
    assert sortie.pv_modifier_percent == -10
    assert sortie.max_sortie_pv == 270


def test_experienced_force_modifier_also_applies(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Vets", ruleset="aces", difficulty="Veteran", experienced_force_sp=7000
    )
    sortie = _sortie(campaign, scenario_pv=100)
    assert (sortie.pv_modifier_percent, sortie.max_sortie_pv) == (-30, 70)


def test_player_may_enter_more_than_the_adjusted_value_with_a_caution(client, minimal_force):
    campaign, _ = _campaign(minimal_force, difficulty="Veteran")
    sortie = _sortie(campaign, scenario_pv=300)  # adjusted 270
    result = aces_sortie_service.set_sortie_pv(sortie.id, scenario_pv=300, max_pv=300)
    assert result["max_sortie_pv"] == 300
    assert result["adjusted_pv"] == 270 and result["above_adjusted"] is True
    below = aces_sortie_service.set_sortie_pv(sortie.id, scenario_pv=300, max_pv=250)
    assert below["above_adjusted"] is False
    exact = aces_sortie_service.set_sortie_pv(sortie.id, scenario_pv=300)
    assert exact["max_sortie_pv"] == 270 and exact["above_adjusted"] is False


def test_route_shows_the_caution_and_the_page_shows_the_bar(client, minimal_force):
    campaign, _ = _campaign(minimal_force, difficulty="Veteran")
    sortie = _sortie(campaign, scenario_pv=300)
    resp = client.post(
        f"/sorties/{sortie.id}/pv",
        data={"scenario_pv": "300", "max_pv": "320"},
        follow_redirects=True,
    )
    assert b"Maximum PV set to 320" in resp.data
    assert b"Caution: this is above the difficulty-adjusted 270 PV" in resp.data
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert "<strong>Selected:</strong> 0 PV" in page
    assert "<strong>Maximum:</strong> 320 PV" in page
    assert "<strong>Remaining:</strong> 320 PV" in page
    assert 'id="pvForm"' in page and 'name="scenario_pv"' in page


def test_create_sortie_form_asks_for_the_scenario_pv(client, minimal_force):
    campaign, _ = _campaign(minimal_force, difficulty="Veteran")
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert 'name="scenario_pv"' in page
    resp = client.post(
        f"/campaigns/{campaign.id}/sorties",
        data={"name": "Strike", "scenario_pv": "300"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    [created] = aces_sortie_service.list_aces_sorties(campaign.id)
    assert created["max_pv"] == 270


def test_maximum_cannot_drop_below_the_selected_force_and_locks_when_ready(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    campaign = _set_pv(campaign, 150, 120)
    sortie = _sortie(campaign, scenario_pv=300)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)  # 270 selected
    with pytest.raises(ValueError, match=r"below the selected force \(270 PV\)"):
        aces_sortie_service.set_sortie_pv(sortie.id, max_pv=200)
    assert contract_service.get_sortie_by_id(sortie.id).max_sortie_pv == 300

    _ready(campaign, pilots, sortie)
    with pytest.raises(ValueError, match="locked once the Sortie is Ready"):
        aces_sortie_service.set_sortie_pv(sortie.id, max_pv=400)
    contract_service.reopen_sortie_planning(sortie.id)
    assert aces_sortie_service.set_sortie_pv(sortie.id, max_pv=400)["max_sortie_pv"] == 400


# --- enforcement ---------------------------------------------------------------------------


def test_adding_a_unit_over_the_maximum_is_rejected_with_a_clear_message(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign = _set_pv(campaign, 284, 28)
    sortie = _sortie(campaign, max_pv=300)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)  # 284 / 300
    first = campaign.units[1]
    with session_scope() as session:
        session.get(CampaignUnit, first.id).point_value = 28  # 284 + 28 = 312
    with pytest.raises(ValueError) as caught:
        contract_service.add_unit_to_sortie(sortie.id, first.id)
    message = str(caught.value)
    assert message.startswith("Cannot add ")
    assert "Sortie force would be 312 / 300 PV." in message
    assert len(contract_service.get_sortie_by_id(sortie.id).units) == 1  # nothing was added


def test_selected_force_may_equal_the_maximum(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    campaign = _set_pv(campaign, 150, 150)
    sortie = _sortie(campaign, max_pv=300)
    for unit in campaign.units:
        contract_service.add_unit_to_sortie(sortie.id, unit.id)
    assert _ready(campaign, pilots, sortie).status == "ready"
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert "<strong>Remaining:</strong> 0 PV" in page


def test_units_without_a_valid_pv_are_rejected_never_counted_as_zero(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _sortie(campaign, max_pv=500)
    for bad_pv in (None, 0):
        with session_scope() as session:
            session.get(CampaignUnit, campaign.units[0].id).point_value = bad_pv
        with pytest.raises(ValueError, match="no Alpha Strike Point Value"):
            contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    assert contract_service.get_sortie_by_id(sortie.id).units == []


def test_ready_is_checked_again_against_the_maximum(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    campaign = _set_pv(campaign, 150, 150)
    sortie = _sortie(campaign, max_pv=300)
    for unit in campaign.units:
        contract_service.add_unit_to_sortie(sortie.id, unit.id)
    with session_scope() as session:  # a unit's PV goes up behind the Sortie's back
        from app.models.sortie import Sortie as SortieRow
        from app.models.sortie_unit import SortieUnit

        session.query(SortieUnit).filter_by(sortie_id=sortie.id).first().point_value = 170
        assert session.get(SortieRow, sortie.id).max_sortie_pv == 300
    with pytest.raises(ValueError, match=r"Sortie force is 320 / 300 PV"):
        _ready(campaign, pilots, sortie)


def test_add_lance_adds_what_fits_then_stops(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign = _set_pv(campaign, 100, 100)
    lance_id = campaign.lances[0].id
    sortie = _sortie(campaign, max_pv=150)
    added, notice = contract_service.add_lance_to_sortie_with_notice(sortie.id, lance_id)
    assert len(added) == 1  # the first unit fits, the second would make 200 / 150
    assert "Cannot add" in notice and "200 / 150 PV" in notice
    assert "Stopped adding the lance" in notice and "not added:" in notice
    assert len(contract_service.get_sortie_by_id(sortie.id).units) == 1


def test_add_lance_stops_instead_of_skipping_ahead_to_a_smaller_unit(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    # order: 100, 100 - then a unit of 10 that would fit after the stop point
    campaign = _set_pv(campaign, 100, 100)
    sortie = _sortie(campaign, max_pv=150)
    with session_scope() as session:  # make the second unit the oversized one, a third tiny one
        extra = CampaignUnit(
            campaign_id=campaign.id,
            campaign_lance_id=campaign.lances[0].id,
            chassis="Locust",
            point_value=10,
            order=99,
            unit_type_name="BattleMech",
        )
        session.add(extra)
    added, notice = contract_service.add_lance_to_sortie_with_notice(
        sortie.id, campaign.lances[0].id
    )
    names = [row.chassis for row in added]
    assert "Locust" not in names  # it would fit, but adding stops at the first unit that does not
    assert "Locust" in notice  # and it is listed as not added


def test_route_reports_the_stop_to_the_player(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign = _set_pv(campaign, 100, 100)
    sortie = _sortie(campaign, max_pv=150)
    resp = client.post(
        f"/sorties/{sortie.id}/units",
        data={"lance_id": str(campaign.lances[0].id)},
        follow_redirects=True,
    )
    assert b"Added 1 unit(s)" in resp.data
    assert b"Stopped adding the lance" in resp.data


# --- Omni and pilots -----------------------------------------------------------------------

NEW_CONFIG = {
    "Id": 9001,
    "Name": "Timber Wolf B",
    "Class": "Timber Wolf",
    "Variant": "B",
    "Tonnage": 75,
    "BFPointValue": 60,
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def test_omni_reconfiguration_recalculates_selected_pv_and_blocks_ready(client, minimal_force):
    campaign, pilots = _campaign(minimal_force, warchest=5000)
    campaign = _set_pv(campaign, 40, 40)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[0].id)
        unit.is_omni = True
        unit.mul_unit_id = 9000
        owner = session.get(Campaign, campaign.id)
        owner.mul_faction_id, owner.mul_era_id = 29, 14
    sortie = _sortie(campaign, max_pv=80)
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)  # 80 / 80

    with patch("app.services.aces_sortie_service.mul_service.find_unit_in_search_results") as f:
        f.return_value = NEW_CONFIG
        updated = contract_service.apply_omni_from_search(row.id, 9001)
    assert updated.point_value == 60  # the selected configuration's PV
    assert sum(r.point_value for r in contract_service.get_sortie_by_id(sortie.id).units) == 100
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert "<strong>Selected:</strong> 100 PV" in page
    assert "<strong>Remaining:</strong> -20 PV" in page
    assert "Over the limit" in page
    with pytest.raises(ValueError, match=r"Sortie force is 100 / 80 PV"):
        _ready(campaign, pilots, sortie)


def test_named_pilot_skill_does_not_change_unit_pv(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    campaign = _set_pv(campaign, 40, 40)
    sortie = _sortie(campaign, max_pv=80)
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    before = row.point_value
    with session_scope() as session:
        session.get(CampaignPilot, pilots[0].id).alpha_strike_skill = 1  # an ace
    assigned = contract_service.assign_sortie_pilot(row.id, pilots[0].id)
    assert assigned.alpha_strike_skill == 1
    assert assigned.point_value == before == 40  # standard MUL PV, not skill-adjusted
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)
    assert sum(r.point_value for r in contract_service.get_sortie_by_id(sortie.id).units) == 80


# --- history -------------------------------------------------------------------------------


def test_report_preserves_maximum_pv_and_fielded_pv(client, minimal_force):
    campaign, pilots = _campaign(minimal_force, difficulty="Veteran")
    campaign = _set_pv(campaign, 40, 40)
    sortie = _sortie(campaign, scenario_pv=300)  # 270
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.assign_sortie_pilot(row.id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.mark_sortie_ready(sortie.id)
    contract_service.mark_sortie_fought(sortie.id)
    apply_aces(sortie.id)
    finalize_aces(sortie.id)

    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "40 / 270 PV" in page
    assert "Scenario 300 PV" in page and "-10% difficulty adjustment" in page

    # Later campaign changes never rewrite the stored limit.
    with session_scope() as session:
        session.get(Campaign, campaign.id).difficulty = "Legendary"
        session.get(CampaignPilot, pilots[0].id).total_sp_earned = 99999
    stored = contract_service.get_sortie_by_id(sortie.id)
    assert (stored.scenario_pv, stored.pv_modifier_percent, stored.max_sortie_pv) == (300, -10, 270)
    again = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "40 / 270 PV" in again
    history = client.get(f"/campaigns/{campaign.id}/sortie-history").data.decode()
    assert "40 / 270" in history
    assert svc.get_sortie_report(sortie.id)["report"].force_pv == 40


def test_sorties_from_before_the_limit_existed_show_it_as_not_recorded(client, minimal_force):
    campaign, pilots = _campaign(minimal_force)
    sortie = _sortie(campaign)  # no maximum
    aces_sortie_service.list_aces_sorties(campaign.id)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    with session_scope() as session:
        from app.models.sortie import Sortie as SortieRow

        session.get(SortieRow, sortie.id).status = "failed"
    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "Maximum PV not recorded" in page


def test_replay_starts_with_the_failed_attempts_maximum(client, minimal_force):
    campaign, pilots = _campaign(minimal_force, difficulty="Veteran")
    sortie = _sortie(campaign, scenario_pv=300)
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.assign_sortie_pilot(row.id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.mark_sortie_ready(sortie.id)
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)
    assert (replay.scenario_pv, replay.pv_modifier_percent, replay.max_sortie_pv) == (300, -10, 270)
    # ... and it can be changed independently.
    aces_sortie_service.set_sortie_pv(replay.id, max_pv=260)
    assert contract_service.get_sortie_by_id(sortie.id).max_sortie_pv == 270


# --- Chaos is untouched --------------------------------------------------------------------


def test_chaos_sorties_ignore_the_aces_maximum(client, minimal_force):
    from app.models.sortie import Sortie

    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with session_scope() as session:
        sortie = Sortie(campaign_id=chaos.id, name="C", status="planning", campaign_month=1)
        session.add(sortie)
        session.flush()
        sortie_id = sortie.id
    page = client.get(f"/sorties/{sortie_id}").data.decode()
    assert 'id="pvBar"' not in page and 'id="pvForm"' not in page
    with pytest.raises(ValueError, match="only available for Aces"):
        aces_sortie_service.set_sortie_pv(sortie_id, max_pv=100)


def test_add_lists_show_point_values(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign = _set_pv(campaign, 36, 44)
    sortie = _sortie(campaign, max_pv=500)
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    lance_name = campaign.lances[0].name
    assert f"{lance_name} — 2 units, 80 PV" in page
    assert "— 36 PV" in page and "— 44 PV" in page  # each unit in the unit picker

    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert f"{lance_name} — 1 unit, 44 PV" in page  # only what is still left to add
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert f"{lance_name} — no units available" in page
