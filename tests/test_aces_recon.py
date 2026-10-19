"""Aces reconnaissance: entered in Sortie Setup, settled in the After-Sortie (addendum)."""

from __future__ import annotations

import pytest

from app.extensions import session_scope
from app.models.campaign_unit import CampaignUnit
from app.models.sortie_recon_action import SortieReconAction
from app.services import aces_after_action_service as svc
from app.services import (
    aces_recon_service as recon,
)
from app.services import (
    aces_sortie_service,
    campaign_service,
    contract_service,
)
from tests.conftest import apply_aces, finalize_aces
from tests.test_aces_after_sortie import _campaign, _fought, _txs


def _planning(campaign, name="Scouting"):
    return campaign_service.create_aces_sortie(campaign.id, name)


# --- recording actions ---------------------------------------------------------------------


def test_sortie_may_have_zero_one_or_many_actions(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    assert recon.list_recon_actions(sortie.id) == []
    recon.add_recon_action(sortie.id, "Scout northern approach", sp_cost=20)
    assert len(recon.list_recon_actions(sortie.id)) == 1
    recon.add_recon_action(sortie.id, "Electronic sweep", sp_cost=10)
    recon.add_recon_action(sortie.id, "Probe enemy defenses")
    actions = recon.list_recon_actions(sortie.id)
    assert [a.name for a in actions] == [
        "Scout northern approach",
        "Electronic sweep",
        "Probe enemy defenses",
    ]
    assert [a.position for a in actions] == [0, 1, 2]


def test_action_needs_a_name_and_a_valid_cost(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    for bad_name in ("", "   ", None):
        with pytest.raises(ValueError, match="name is required"):
            recon.add_recon_action(sortie.id, bad_name)
    with pytest.raises(ValueError, match="cannot be negative"):
        recon.add_recon_action(sortie.id, "Scout", sp_cost=-1)
    with pytest.raises(ValueError, match="whole number"):
        recon.add_recon_action(sortie.id, "Scout", sp_cost="lots")
    assert recon.list_recon_actions(sortie.id) == []


def test_zero_cost_and_no_unit_are_fine(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    action = recon.add_recon_action(sortie.id, "Free look", sp_cost=0)
    assert action.sp_cost == 0
    assert action.campaign_unit_id is None and action.unit_label is None


def test_action_may_reference_a_player_force_unit(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    unit = campaign.units[0]
    action = recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=unit.id, sp_cost=5)
    assert action.campaign_unit_id == unit.id
    assert unit.chassis in action.unit_label


def test_unit_from_another_campaign_or_out_of_service_is_rejected(
    client, minimal_force, multiple_forces
):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    other = campaign_service.create_campaign_from_force(
        multiple_forces["Jade Falcon Strikers"], "Elsewhere", ruleset="aces"
    )
    with pytest.raises(ValueError, match="Player Force"):
        recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=other.units[0].id)
    with pytest.raises(ValueError, match="Player Force"):
        recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=99999)
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[1].id).condition = "retired"
    with pytest.raises(ValueError, match="no longer part of the Player Force"):
        recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=campaign.units[1].id)


def test_total_is_the_sum_of_action_costs(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    for name, cost in (("A", 20), ("B", 10), ("C", 0)):
        recon.add_recon_action(sortie.id, name, sp_cost=cost)
    with session_scope() as session:
        assert recon.recon_total(session, sortie.id) == 30


def test_unit_assignment_does_not_put_the_unit_in_the_sortie_force(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=campaign.units[0].id)
    assert contract_service.get_sortie_by_id(sortie.id).units == []


# --- editing and locking -------------------------------------------------------------------


def test_actions_can_be_edited_and_removed_while_planning(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    first = recon.add_recon_action(sortie.id, "One", sp_cost=5)
    second = recon.add_recon_action(sortie.id, "Two", sp_cost=7)
    third = recon.add_recon_action(sortie.id, "Three", sp_cost=9)

    updated = recon.update_recon_action(
        second.id, "Two (revised)", campaign_unit_id=campaign.units[0].id, sp_cost=12, notes="n"
    )
    assert (updated.name, updated.sp_cost, updated.notes) == ("Two (revised)", 12, "n")
    assert updated.unit_label
    cleared = recon.update_recon_action(second.id, "Two (revised)", sp_cost=12)
    assert cleared.campaign_unit_id is None and cleared.unit_label is None

    recon.delete_recon_action(first.id)
    remaining = recon.list_recon_actions(sortie.id)
    assert [a.id for a in remaining] == [second.id, third.id]
    assert [a.position for a in remaining] == [0, 1]
    with pytest.raises(ValueError, match="name is required"):
        recon.update_recon_action(second.id, "", sp_cost=1)


def test_actions_lock_once_the_sortie_is_played(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 10)])
    [action] = recon.list_recon_actions(sortie.id)
    for attempt in (
        lambda: recon.add_recon_action(sortie.id, "Late"),
        lambda: recon.update_recon_action(action.id, "Changed"),
        lambda: recon.delete_recon_action(action.id),
    ):
        with pytest.raises(ValueError, match="while the Sortie is in Planning"):
            attempt()
    assert [a.name for a in recon.list_recon_actions(sortie.id)] == ["Scout"]


def test_a_ready_sortie_can_be_reopened_to_change_its_recon(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    prepared = _planning(campaign)
    row = contract_service.add_unit_to_sortie(prepared.id, campaign.units[0].id)
    contract_service.assign_sortie_pilot(row.id, hawk.id)
    aces_sortie_service.set_force_commander(prepared.id, hawk.id)
    recon.add_recon_action(prepared.id, "Scout", sp_cost=4)
    contract_service.mark_sortie_ready(prepared.id)
    with pytest.raises(ValueError, match="Planning"):
        recon.add_recon_action(prepared.id, "Late")
    contract_service.reopen_sortie_planning(prepared.id)
    assert recon.add_recon_action(prepared.id, "On time").id
    assert len(recon.list_recon_actions(prepared.id)) == 2


# --- accounting ----------------------------------------------------------------------------


def test_successful_sortie_includes_recon_in_expenses_without_double_posting(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20), ("Sweep", 10)])
    start = campaign_service.get_campaign_by_id(campaign.id).warchest_balance

    # Setup charged nothing.
    assert start == campaign_service.get_campaign_by_id(campaign.id).warchest_balance
    assert _txs(campaign.id, "reconnaissance") == []

    apply_aces(sortie.id, "none", primary_objective_sp=500, max_pilot_sp=0)
    report = svc.get_sortie_report(sortie.id)["report"]
    assert report.expense_reconnaissance == 30
    assert report.total_expenses == 30 + report.expense_rearming
    assert report.earnings == 500 - report.total_expenses
    assert _txs(campaign.id, "reconnaissance") == []  # still nothing until finalized

    finalize_aces(sortie.id)
    [line] = _txs(campaign.id, "reconnaissance")
    assert line.actual_amount == -30
    final = campaign_service.get_campaign_by_id(campaign.id).warchest_balance
    assert final == start + report.earnings  # recon counted exactly once


def test_no_recon_means_no_recon_expense_or_ledger_line(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=100)
    finalize_aces(sortie.id)
    assert svc.get_sortie_report(sortie.id)["report"].expense_reconnaissance == 0
    assert _txs(campaign.id, "reconnaissance") == []


def test_after_sortie_form_shows_recon_read_only(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20), ("Sweep", 10)])
    html = client.get(f"/sorties/{sortie.id}").data.decode()
    assert 'name="reconnaissance"' not in html  # no second place to type the cost
    assert "30 SP (from Sortie Setup)" in html
    assert "Scout" in html and "Sweep" in html


# --- failed sorties and replays ------------------------------------------------------------


def test_failed_sortie_keeps_its_recon_but_charges_nothing(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20)])
    before = campaign_service.get_campaign_by_id(campaign.id).warchest_balance
    aces_sortie_service.fail_sortie(sortie.id)

    assert [a.name for a in recon.list_recon_actions(sortie.id)] == ["Scout"]
    assert _txs(campaign.id, "reconnaissance") == []
    assert campaign_service.get_campaign_by_id(campaign.id).warchest_balance == before
    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "Scout" in page and "was not charged" in page


def test_replay_starts_empty_and_has_its_own_actions(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20)])
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)

    assert recon.list_recon_actions(replay.id) == []  # nothing copied automatically
    recon.add_recon_action(replay.id, "Different approach", sp_cost=5)
    assert [a.name for a in recon.list_recon_actions(replay.id)] == ["Different approach"]
    assert [a.name for a in recon.list_recon_actions(sortie.id)] == ["Scout"]  # untouched


def test_replay_can_copy_the_previous_attempt_when_it_has_none(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20), ("Sweep", 10)])
    unit_id = campaign.units[0].id
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)

    page = client.get(f"/sorties/{replay.id}").data.decode()
    assert "Copy reconnaissance from the previous attempt" in page
    copies = recon.copy_from_previous_attempt(replay.id)
    assert [(c.name, c.sp_cost) for c in copies] == [("Scout", 20), ("Sweep", 10)]
    assert {c.sortie_id for c in copies} == {replay.id}

    # Once the replay has a setup, copying is no longer offered or allowed.
    with pytest.raises(ValueError, match="already has reconnaissance"):
        recon.copy_from_previous_attempt(replay.id)
    page = client.get(f"/sorties/{replay.id}").data.decode()
    assert "Copy reconnaissance from the previous attempt" not in page

    # ... and the copy is freely adjustable, independent of the original.
    first = recon.list_recon_actions(replay.id)[0]
    recon.update_recon_action(first.id, "Scout (revised)", sp_cost=3)
    assert recon.list_recon_actions(sortie.id)[0].name == "Scout"
    assert unit_id  # keep the campaign unit referenced in this scenario


def test_copy_rules(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    plain = _planning(campaign, "Plain")
    with pytest.raises(ValueError, match="Only a replay"):
        recon.copy_from_previous_attempt(plain.id)
    assert recon.previous_attempt_has_recon(plain.id) is False

    played, _ = _fought(campaign, {0: hawk}, name="Quiet")  # no recon at all
    aces_sortie_service.fail_sortie(played.id)
    replay = aces_sortie_service.create_replay(played.id)
    assert recon.previous_attempt_has_recon(replay.id) is False
    with pytest.raises(ValueError, match="no reconnaissance to copy"):
        recon.copy_from_previous_attempt(replay.id)
    assert "Copy reconnaissance" not in client.get(f"/sorties/{replay.id}").data.decode()


def test_copy_drops_a_unit_that_left_the_player_force(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie = _planning(campaign, "Scouts")
    recon.add_recon_action(sortie.id, "Scout", campaign_unit_id=campaign.units[1].id)
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.assign_sortie_pilot(row.id, hawk.id)
    aces_sortie_service.set_force_commander(sortie.id, hawk.id)
    contract_service.mark_sortie_ready(sortie.id)
    aces_sortie_service.fail_sortie(sortie.id)
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[1].id).condition = "retired"
    replay = aces_sortie_service.create_replay(sortie.id)
    [copy] = recon.copy_from_previous_attempt(replay.id)
    assert copy.name == "Scout" and copy.campaign_unit_id is None and copy.unit_label is None
    # The failed attempt still names the unit it used.
    [original] = recon.list_recon_actions(sortie.id)
    assert original.unit_label and original.unit_label.strip()


# --- history -------------------------------------------------------------------------------


def test_unit_identity_survives_the_unit_leaving_the_force(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    played = _planning(campaign, "Recon run")
    scout = campaign.units[1]
    recon.add_recon_action(played.id, "Scout", campaign_unit_id=scout.id, sp_cost=10)
    [action] = recon.list_recon_actions(played.id)
    expected_label = action.unit_label
    assert expected_label

    campaign_service.delete_campaign_unit(scout.id)
    [after] = recon.list_recon_actions(played.id)
    assert after.campaign_unit_id is None  # the live link is gone ...
    assert after.unit_label == expected_label  # ... the historical identity is not


def test_sortie_report_shows_recon_details_and_total(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout northern approach", 20)])
    with session_scope() as session:  # a second action naming a unit
        session.add(
            SortieReconAction(
                sortie_id=sortie.id,
                position=1,
                name="Electronic sweep",
                sp_cost=10,
                unit_label="Pegasus Scout Hover",
            )
        )
    apply_aces(sortie.id, primary_objective_sp=300)
    finalize_aces(sortie.id)
    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "Reconnaissance</h5>" in page
    assert "Scout northern approach" in page
    assert "Electronic sweep" in page and "Pegasus Scout Hover" in page
    assert "Total Reconnaissance: <strong>30 SP</strong>" in page
    assert '<td>Reconnaissance</td><td class="text-end">30</td>' in page.replace("\n", "").replace(
        "  ", ""
    )
    # The Reconnaissance section comes before the accounting sections.
    assert page.index("Total Reconnaissance") < page.index("Total Income")


def test_report_without_recon_says_so(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id)
    finalize_aces(sortie.id)
    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "No reconnaissance was recorded for this Sortie" in page


def test_deleting_the_campaign_removes_its_recon_actions(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    recon.add_recon_action(sortie.id, "Scout", sp_cost=5)
    assert campaign_service.delete_campaign(campaign.id)
    with session_scope() as session:
        assert session.query(SortieReconAction).count() == 0


# --- routes and page -----------------------------------------------------------------------


def test_planning_page_manages_recon_through_the_routes(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    sortie = _planning(campaign)
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert 'id="recon"' in page and "Add action" in page and "0 SP" in page

    added = client.post(
        f"/sorties/{sortie.id}/recon",
        data={
            "name": "Scout",
            "campaign_unit_id": str(campaign.units[0].id),
            "sp_cost": "15",
            "notes": "north",
        },
        follow_redirects=True,
    )
    assert b"Reconnaissance action added" in added.data
    assert b"15 SP" in added.data
    [action] = recon.list_recon_actions(sortie.id)

    saved = client.post(
        f"/sorties/{sortie.id}/recon/{action.id}/update",
        data={"name": "Scout 2", "sp_cost": "8", "notes": ""},
        follow_redirects=True,
    )
    assert b"Reconnaissance action saved" in saved.data
    assert recon.list_recon_actions(sortie.id)[0].campaign_unit_id is None

    bad = client.post(
        f"/sorties/{sortie.id}/recon", data={"name": "", "sp_cost": "1"}, follow_redirects=True
    )
    assert b"name is required" in bad.data
    negative = client.post(
        f"/sorties/{sortie.id}/recon", data={"name": "X", "sp_cost": "-4"}, follow_redirects=True
    )
    assert b"cannot be negative" in negative.data

    removed = client.post(f"/sorties/{sortie.id}/recon/{action.id}/delete", follow_redirects=True)
    assert b"Reconnaissance action removed" in removed.data
    assert recon.list_recon_actions(sortie.id) == []


def test_recon_is_read_only_on_a_locked_sortie_page(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, recon=[("Scout", 20)])
    page = client.get(f"/sorties/{sortie.id}").data.decode()
    card = page[page.index('id="recon"') : page.index("Force Commander</h5>")]
    assert "Scout" in card
    assert "Add action" not in card and "Remove" not in card
    blocked = client.post(
        f"/sorties/{sortie.id}/recon", data={"name": "Late", "sp_cost": "1"}, follow_redirects=True
    )
    assert b"while the Sortie is in Planning" in blocked.data


# --- Chaos is untouched --------------------------------------------------------------------


def test_chaos_sorties_have_no_reconnaissance(client, minimal_force):
    from app.models.sortie import Sortie

    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with session_scope() as session:
        sortie = Sortie(campaign_id=chaos.id, name="C", status="planning", campaign_month=1)
        session.add(sortie)
        session.flush()
        sortie_id = sortie.id
    with pytest.raises(ValueError, match="only available for Aces"):
        recon.add_recon_action(sortie_id, "Scout")
    page = client.get(f"/sorties/{sortie_id}").data.decode()
    assert 'id="recon"' not in page
