"""Aces After-Sortie workflow: accounting, casualties, pilots, report (Prompt 6c)."""

from __future__ import annotations

from datetime import date

import pytest

from app.extensions import session_scope
from app.models.aces_sortie_report import AcesSortieReport
from app.models.campaign_pilot import CampaignPilot
from app.models.campaign_unit import CampaignUnit
from app.models.pilot_advancement_event import PilotAdvancementEvent
from app.models.pilot_injury_event import PilotInjuryEvent
from app.models.sortie import Sortie
from app.services import (
    aces_after_action_service as svc,
)
from app.services import (
    aces_pilot_service,
    aces_recon_service,
    aces_sortie_service,
    after_action_service,
    campaign_service,
    contract_service,
)
from tests.conftest import aces_after_inputs, apply_aces, finalize_aces, finish_aces


def _campaign(force_id, *, warchest=1000, difficulty=None, name="Aces After"):
    campaign = campaign_service.create_campaign_from_force(
        force_id,
        name,
        ruleset="aces",
        difficulty=difficulty,
        opening_warchest=warchest,
        starting_bt_year=3151,
        starting_bt_month=1,
    )
    with session_scope() as session:
        for unit in session.query(CampaignUnit).filter_by(campaign_id=campaign.id):
            unit.point_value = 40
            unit.tonnage = 70
            unit.unit_type_name = "BattleMech"
    pilots = [
        aces_pilot_service.create_aces_pilot(
            campaign.id, callsign, "BM", skill_sp=150, edge_sp=0, ability_sp=0
        )
        for callsign in ("Hawk", "Ghost")
    ]
    return campaign_service.get_campaign_by_id(campaign.id), pilots


def _fought(campaign, crew, *, units=(0,), name="Waypoint", recon=()):
    """Fought Sortie. ``crew`` maps unit index -> pilot (omitted units use generic crew).

    ``recon`` is a list of (name, sp_cost) reconnaissance actions entered in Sortie Setup.
    """
    sortie = campaign_service.create_aces_sortie(campaign.id, name)
    for action_name, cost in recon:
        aces_recon_service.add_recon_action(sortie.id, action_name, sp_cost=cost)
    rows = {i: contract_service.add_unit_to_sortie(sortie.id, campaign.units[i].id) for i in units}
    first = None
    for index, pilot in crew.items():
        contract_service.assign_sortie_pilot(rows[index].id, pilot.id)
        first = first or pilot
    aces_sortie_service.set_force_commander(sortie.id, first.id)
    contract_service.mark_sortie_ready(sortie.id)
    contract_service.mark_sortie_fought(sortie.id)
    return sortie, rows


def _balance(campaign_id):
    return campaign_service.get_campaign_by_id(campaign_id).warchest_balance


def _txs(campaign_id, kind=None):
    txs = campaign_service.get_campaign_by_id(campaign_id).transactions
    return [t for t in txs if kind is None or t.transaction_type == kind]


def _report(sortie_id):
    with session_scope() as session:
        report = session.query(AcesSortieReport).filter_by(sortie_id=sortie_id).one()
        session.expunge(report)
        return report


# --- accounting ----------------------------------------------------------------------------


def test_income_expenses_earnings_and_ledger(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk}, recon=[("Scout", 6), ("Sweep", 4)])
    apply_aces(
        sortie.id,
        "structure",
        primary_objective_sp=300,
        max_pilot_sp=50,
    )
    report = _report(sortie.id)
    # structure on a Size 3 BM = 120; rearm 20; recon 10.
    assert report.total_income == 300
    assert (report.expense_repairs, report.expense_rearming) == (120, 20)
    assert report.expense_reconnaissance == 10
    assert report.total_expenses == 150
    assert report.earnings == 150
    # Pilot cap 50 (Hawk participant) + 25 (Ghost sat out) = 75; the rest returns to Warchest.
    assert report.pilot_sp_pool == 75
    assert report.warchest_remainder == 75
    assert report.warchest_before == 1000
    assert report.warchest_after_accounting == 1075

    # The Warchest and ledger do not move until the Sortie is finalized.
    assert _balance(campaign.id) == 1000
    assert [t.transaction_type for t in _txs(campaign.id)] == ["opening_balance"]

    finalize_aces(sortie.id)
    assert _balance(campaign.id) == 1000 + 75
    # Ledger is complete and not double-posted.
    assert sum(t.actual_amount for t in _txs(campaign.id, "repair")) == -120
    assert sum(t.actual_amount for t in _txs(campaign.id, "rearm")) == -20
    assert sum(t.actual_amount for t in _txs(campaign.id, "pilot_improvement")) == -75
    assert sum(t.actual_amount for t in _txs(campaign.id, "objective_income")) == 300


def test_difficulty_multiplies_objective_income_only(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force, difficulty="Veteran")
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=300, secondary_objective_sp=100, other_income=50)
    report = _report(sortie.id)
    assert report.objective_percent == 90
    assert report.primary_objective_base == 300
    assert report.primary_objective_adjusted == 270
    assert report.secondary_objective_adjusted == 90
    assert report.other_income == 50  # not multiplied
    assert report.total_income == 270 + 90 + 50


def test_negative_earnings_reduce_warchest_and_skip_pilot_sp(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=100)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "destroyed", primary_objective_sp=50, max_pilot_sp=100)
    report = _report(sortie.id)
    # destroyed = 300 repair + 20 rearm against 50 income.
    assert report.earnings == 50 - 320
    assert report.pilot_sp_pool == 0
    finalize_aces(sortie.id)
    assert _balance(campaign.id) == 100 - 270  # may go negative; campaign is not blocked
    # The expensive repair is still made: the unit is back in service.
    assert campaign_service.get_campaign_by_id(campaign.id).units[0].condition == "active"
    shares = {s["share"].callsign: s["share"] for s in svc.get_sortie_report(sortie.id)["shares"]}
    assert shares["Hawk"].awarded_sp == 0
    assert shares["Ghost"].awarded_sp == 0


def test_pilot_sp_never_draws_from_warchest(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=100000)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=20, max_pilot_sp=500)
    report = _report(sortie.id)
    assert report.earnings == 20 - 20  # rearm eats the income
    assert report.pilot_sp_pool == 0
    assert _balance(campaign.id) == 100000


def test_insufficient_earnings_split_two_to_one(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=50, max_pilot_sp=100)  # earnings 30
    shares = {s["share"].callsign: s["share"] for s in svc.get_sortie_report(sortie.id)["shares"]}
    assert (shares["Hawk"].awarded_sp, shares["Ghost"].awarded_sp) == (20, 10)
    assert shares["Ghost"].state == "non_participant"
    assert _report(sortie.id).warchest_remainder == 0


def test_pilot_allocation_happens_before_warchest_remainder(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=200, max_pilot_sp=40)  # earnings 180
    report = _report(sortie.id)
    assert report.pilot_sp_pool == 60  # 40 + 20
    assert report.warchest_remainder == 120
    assert report.earnings == report.pilot_sp_pool + report.warchest_remainder


# --- MVP -----------------------------------------------------------------------------------


def test_mvp_required_and_must_have_participated_and_survived(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk})
    with pytest.raises(ValueError, match="Select an MVP"):
        svc.apply_aces_after_action(sortie.id, aces_after_inputs(sortie.id, mvp_pilot_id=None))
    with pytest.raises(ValueError, match="participated and survived"):
        svc.apply_aces_after_action(sortie.id, aces_after_inputs(sortie.id, mvp_pilot_id=ghost.id))
    killed = {rows[0].id: {"pilot_killed": True}}
    with pytest.raises(ValueError):
        svc.apply_aces_after_action(
            sortie.id, aces_after_inputs(sortie.id, flags=killed, mvp_pilot_id=hawk.id)
        )
    assert contract_service.get_sortie_by_id(sortie.id).status == "fought"  # nothing applied


def test_mvp_bonus_costs_nothing_and_counts(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=0, max_pilot_sp=0)
    report = _report(sortie.id)
    # Earnings are the rearm cost only (negative), the MVP bonus does not change them.
    assert report.earnings == -20
    assert _balance(campaign.id) == 1000  # nothing posts until finalized
    pending = svc.pending_shares(sortie.id)
    assert [(p["share"].callsign, p["total"]) for p in pending] == [("Hawk", 20)]
    with session_scope() as session:
        assert session.get(CampaignPilot, hawk.id).mvp_count == 1

    svc.allocate_pilot_share(sortie.id, hawk.id, skill_sp=0, edge_sp=20, ability_sp=0)
    with session_scope() as session:
        event = (
            session.query(PilotAdvancementEvent)
            .filter_by(campaign_pilot_id=hawk.id, source_type="sortie")
            .one()
        )
        assert (event.sp_received, event.mvp_bonus) == (0, 20)
        assert event.participation_state == "participant"
        assert session.get(CampaignPilot, hawk.id).total_sp_earned == 170


# --- casualties ----------------------------------------------------------------------------


def test_killed_pilot_gets_no_sp_and_stays_in_history(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk}, units=(0, 1))
    flags = {rows[0].id: {"pilot_killed": True}}
    # MVP cannot be the dead pilot; with only Hawk participating, no MVP is eligible.
    apply_aces(
        sortie.id, "destroyed", flags, mvp_pilot_id=None, primary_objective_sp=500, max_pilot_sp=100
    )
    with session_scope() as session:
        assert session.get(CampaignPilot, hawk.id).status == "dead"
        assert (
            session.query(PilotInjuryEvent)
            .filter_by(campaign_pilot_id=hawk.id, event_type="died")
            .count()
            == 1
        )
    shares = {s["share"].callsign: s["share"] for s in svc.get_sortie_report(sortie.id)["shares"]}
    assert shares["Hawk"].state == "killed"
    assert shares["Hawk"].awarded_sp == 0
    assert aces_pilot_service.get_pilot_service_history(hawk.id) is not None


def test_truly_destroyed_unit_not_repaired_or_rearmed(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "truly-destroyed")
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert unit.condition == "truly-destroyed"
    assert unit.available is False
    assert after_action_service.get_repair_orders(campaign.id) == []
    assert _txs(campaign.id, "rearm") == []
    # The campaign unit row survives; no Miniature was touched.
    assert unit.id == campaign.units[0].id


def test_aces_repairs_are_mandatory_and_complete_at_finalize(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "crippled", primary_objective_sp=1000)
    [order] = after_action_service.get_repair_orders(campaign.id)
    assert (order.ruleset, order.gross_cost, order.actual_cost) == ("aces", 180, -180)
    assert order.status == "pending"
    # Required repair is part of this Sortie's expenses.
    assert _report(sortie.id).expense_repairs == 180
    # Until finalize the unit stays sidelined.
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert (unit.condition, unit.available) == ("damaged", False)

    for action in (
        lambda: after_action_service.update_repair_order(order.id, gross_cost=10),
        lambda: after_action_service.complete_repair_order(order.id),
        lambda: after_action_service.cancel_repair_order(order.id),
    ):
        with pytest.raises(ValueError, match="Aces repair"):
            action()

    finalize_aces(sortie.id)
    [done] = after_action_service.get_repair_orders(campaign.id)
    assert done.status == "completed" and done.completed_at is not None
    assert len(_txs(campaign.id, "repair")) == 1  # paid once, at finalize
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert (unit.condition, unit.damage_category, unit.available) == ("active", "none", True)


def test_generic_crew_and_wound_personnel_expenses(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk}, units=(0, 1))
    flags = {
        rows[0].id: {"pilot_wounded": True},
        rows[1].id: {"generic_crew_lost": True},
    }
    apply_aces(sortie.id, "none", flags, primary_objective_sp=1000)
    report = _report(sortie.id)
    assert report.expense_personnel == 100 + 100
    finalize_aces(sortie.id)
    assert sum(t.actual_amount for t in _txs(campaign.id, "personnel")) == -200


def test_hiring_a_pilot_costs_150_sp(client, minimal_force):
    campaign, _ = _campaign(minimal_force, warchest=200)
    free = aces_pilot_service.create_aces_pilot(
        campaign.id, "Free", "BM", skill_sp=150, edge_sp=0, ability_sp=0
    )
    assert free.id and _balance(campaign.id) == 200
    aces_pilot_service.create_aces_pilot(
        campaign.id, "Hired", "BM", skill_sp=150, edge_sp=0, ability_sp=0, hired=True
    )
    assert _balance(campaign.id) == 50
    assert sum(t.actual_amount for t in _txs(campaign.id, "personnel")) == -150
    with pytest.raises(ValueError, match="Insufficient Warchest"):
        aces_pilot_service.create_aces_pilot(
            campaign.id, "Broke", "BM", skill_sp=150, edge_sp=0, ability_sp=0, hired=True
        )


# --- wounds and recovery -------------------------------------------------------------------


def _wound_hawk_in_sortie_one(campaign, hawk, ghost):
    sortie, rows = _fought(campaign, {0: hawk}, name="One")
    flags = {rows[0].id: {"pilot_wounded": True}}
    finish_aces(sortie.id, "none", flags, primary_objective_sp=1000, max_pilot_sp=100)
    return sortie


def test_wound_costs_100_and_makes_pilot_unavailable(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie = _wound_hawk_in_sortie_one(campaign, hawk, ghost)
    assert _report(sortie.id).expense_personnel == 100
    with session_scope() as session:
        assert session.get(CampaignPilot, hawk.id).wounds == 1
    # Wounded participants still got the full participating share.
    shares = {s["share"].callsign: s["share"] for s in svc.get_sortie_report(sortie.id)["shares"]}
    assert shares["Hawk"].state == "participant"
    assert shares["Hawk"].awarded_sp == 100

    nxt = campaign_service.create_aces_sortie(campaign.id, "Two")
    row = contract_service.add_unit_to_sortie(nxt.id, campaign.units[0].id)
    with pytest.raises(ValueError, match="not available"):
        contract_service.assign_sortie_pilot(row.id, hawk.id)


def test_wounded_pilot_recovers_after_sitting_out_next_successful_sortie(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    _wound_hawk_in_sortie_one(campaign, hawk, ghost)

    second, _ = _fought(campaign, {0: ghost}, name="Two")
    apply_aces(second.id, primary_objective_sp=1000, max_pilot_sp=100)
    with session_scope() as session:
        pilot = session.get(CampaignPilot, hawk.id)
        assert pilot.wounds == 0
        assert (
            session.query(PilotInjuryEvent)
            .filter_by(campaign_pilot_id=hawk.id, event_type="recovered")
            .count()
            == 1
        )
    # Sitting out still earned the non-participant half-share.
    shares = {s["share"].callsign: s["share"] for s in svc.get_sortie_report(second.id)["shares"]}
    assert shares["Hawk"].state == "non_participant"
    assert shares["Hawk"].awarded_sp == 50


def test_failed_sortie_does_not_advance_recovery(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    _wound_hawk_in_sortie_one(campaign, hawk, ghost)
    second, _ = _fought(campaign, {0: ghost}, name="Two")
    aces_sortie_service.fail_sortie(second.id)
    with session_scope() as session:
        assert session.get(CampaignPilot, hawk.id).wounds == 1
    # ... and the pilot is still unavailable on the replay.
    replay = aces_sortie_service.create_replay(second.id)
    stored = contract_service.get_sortie_by_id(replay.id)
    assert hawk.id not in {r.campaign_pilot_id for r in stored.units}


# --- keywords, atomicity, legacy paths -----------------------------------------------------


def test_keywords_applied_with_the_after_sortie(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, keywords_gained=["Betrayal", "Ally"])
    assert aces_sortie_service.get_current_keywords(campaign.id) == ["Betrayal", "Ally"]
    assert aces_sortie_service.get_sortie_keywords(sortie.id)["gained"] == ["Betrayal", "Ally"]


def test_failed_apply_changes_nothing(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    with pytest.raises(ValueError, match="not currently held"):
        apply_aces(
            sortie.id, "structure", primary_objective_sp=500, keywords_removed=["Never held"]
        )
    assert _balance(campaign.id) == 1000
    assert contract_service.get_sortie_by_id(sortie.id).status == "fought"
    assert after_action_service.get_repair_orders(campaign.id) == []
    with session_scope() as session:
        assert session.query(AcesSortieReport).count() == 0


def test_legacy_after_action_and_close_blocked_for_aces(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    with pytest.raises(ValueError, match="Aces After-Sortie workflow"):
        after_action_service.apply_after_action(sortie.id, [])
    apply_aces(sortie.id)
    with pytest.raises(ValueError, match="Finalize Aces Sorties"):
        after_action_service.close_sortie(sortie.id)


def test_cannot_apply_twice_or_to_failed_sortie(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id)
    with pytest.raises(ValueError, match="Fought Sortie"):
        apply_aces(sortie.id)
    finalize_aces(sortie.id)
    failed, _ = _fought(campaign, {0: hawk}, name="Other")
    aces_sortie_service.fail_sortie(failed.id)
    with pytest.raises(ValueError, match="Fought Sortie"):
        apply_aces(failed.id)


# --- allocation and finalize ---------------------------------------------------------------


def test_allocation_must_be_complete_and_abilities_chosen(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=1000, max_pilot_sp=200)
    shares = {p["share"].campaign_pilot_id: p["total"] for p in svc.pending_shares(sortie.id)}
    assert shares == {hawk.id: 220, ghost.id: 100}

    with pytest.raises(ValueError, match="must be allocated"):
        svc.allocate_pilot_share(sortie.id, hawk.id, skill_sp=100, edge_sp=0, ability_sp=0)
    # 220 to abilities: 0 -> 220 crosses 60 and 180 => two picks required.
    with pytest.raises(ValueError, match="Select exactly 2"):
        svc.allocate_pilot_share(sortie.id, hawk.id, skill_sp=0, edge_sp=0, ability_sp=220)
    svc.allocate_pilot_share(
        sortie.id,
        hawk.id,
        skill_sp=0,
        edge_sp=0,
        ability_sp=220,
        abilities=["Marksman", "Nimble"],
    )
    with pytest.raises(ValueError, match="already been allocated"):
        svc.allocate_pilot_share(sortie.id, hawk.id, skill_sp=220, edge_sp=0, ability_sp=0)
    with pytest.raises(ValueError, match="Ghost"):
        svc.finalize_aces_sortie(sortie.id)


def test_finalize_freezes_the_report_and_snapshots_history(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(
        sortie.id,
        "armour",
        primary_objective_sp=1000,
        max_pilot_sp=450,
        story_notes="They knew.",
    )
    for item in svc.pending_shares(sortie.id):
        svc.allocate_pilot_share(
            sortie.id,
            item["share"].campaign_pilot_id,
            skill_sp=item["total"],
            edge_sp=0,
            ability_sp=0,
        )
    svc.finalize_aces_sortie(sortie.id, "Proceed to Sortie 2")

    report = _report(sortie.id)
    assert report.finalized and report.next_steps == "Proceed to Sortie 2"
    assert report.warchest_after_accounting == _balance(campaign.id)
    assert contract_service.get_sortie_by_id(sortie.id).status == "closed"
    with pytest.raises(ValueError, match="immutable"):
        with session_scope() as session:
            session.query(AcesSortieReport).filter_by(sortie_id=sortie.id).one().earnings = 1
    with pytest.raises(ValueError, match="open After-Sortie"):
        svc.finalize_aces_sortie(sortie.id)

    # Hawk (participant + MVP = 470 SP) is Skill 3 now; the report still shows Skill 4.
    with session_scope() as session:
        assert session.get(CampaignPilot, hawk.id).alpha_strike_skill == 3
    data = svc.get_sortie_report(sortie.id)
    assert data["units"][0].alpha_strike_skill == 4
    assert data["mvp_callsign"] == "Hawk"


# --- routes and report pages ---------------------------------------------------------------


def test_preview_matches_applied_numbers(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk}, recon=[("Scout", 10)])
    form = {
        f"damage_outcome_{rows[0].id}": "structure",
        "primary_objective_sp": "300",
        "max_pilot_sp": "50",
        "mvp_pilot_id": str(hawk.id),
    }
    resp = client.post(f"/sorties/{sortie.id}/aces-preview", data=form)
    payload = resp.get_json()
    assert payload["success"] is True
    preview = payload["data"]
    assert contract_service.get_sortie_by_id(sortie.id).status == "fought"  # nothing written
    assert _balance(campaign.id) == 1000

    client.post(f"/sorties/{sortie.id}/aces-after-action", data=form, follow_redirects=True)
    report = _report(sortie.id)
    assert preview["earnings"] == report.earnings == 150
    assert preview["pilot"]["pool"] == report.pilot_sp_pool
    assert preview["warchest"]["after"] == report.warchest_after_accounting

    bad = client.post(f"/sorties/{sortie.id}/aces-preview", data=form)
    assert bad.status_code == 400  # already applied
    assert bad.get_json()["success"] is False


def test_full_route_flow_report_history_and_links(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, rows = _fought(campaign, {0: hawk})
    detail = client.get(f"/sorties/{sortie.id}")
    assert b"After-Sortie" in detail.data
    assert b"acesPreviewBtn" in detail.data

    applied = client.post(
        f"/sorties/{sortie.id}/aces-after-action",
        data={
            f"damage_outcome_{rows[0].id}": "none",
            "primary_objective_sp": "400",
            "max_pilot_sp": "60",
            "mvp_pilot_id": str(hawk.id),
            "keywords_gained": "Betrayal\nAlly",
            "story_notes": "A story",
            "after_action_notes": "Went fine",
        },
        follow_redirects=True,
    )
    assert b"After-Sortie applied" in applied.data
    assert b"Named Pilot Improvement" in applied.data

    for pilot, total in ((hawk, 80), (ghost, 30)):
        resp = client.post(
            f"/sorties/{sortie.id}/pilot-share/{pilot.id}",
            data={"skill_sp": str(total), "edge_sp": "0", "ability_sp": "0"},
            follow_redirects=True,
        )
        assert b"Pilot improvement recorded" in resp.data

    final = client.post(
        f"/sorties/{sortie.id}/finalize",
        data={"next_steps": "Go to Sortie 2"},
        follow_redirects=True,
    )
    assert final.status_code == 200
    assert b"Sortie Report finalized" in final.data
    for text in (
        b"Income",
        b"Expenses",
        b"Earnings",
        b"Named Pilot Improvement",
        b"Warchest",
        b"Narrative",
        b"Go to Sortie 2",
        b"A story",
        b"Betrayal",
        b"Hawk",
    ):
        assert text in final.data
    assert f"/campaigns/pilots/{hawk.id}/history".encode() in final.data

    history = client.get(f"/campaigns/{campaign.id}/sortie-history")
    assert history.status_code == 200
    assert f"/sorties/{sortie.id}/report".encode() in history.data
    assert b"Hawk" in history.data

    pilot_page = client.get(f"/campaigns/pilots/{hawk.id}/history")
    assert f"/sorties/{sortie.id}/report".encode() in pilot_page.data

    summary = client.get(f"/campaigns/{campaign.id}")
    assert b"Go to Sortie 2" in summary.data


def test_failed_report_and_history_row_stay_visible(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    aces_sortie_service.fail_sortie(sortie.id, "Lost the objective")
    page = client.get(f"/sorties/{sortie.id}/report")
    assert page.status_code == 200
    assert b"This attempt failed" in page.data
    assert b"Lost the objective" in page.data
    history = client.get(f"/campaigns/{campaign.id}/sortie-history")
    assert b"failed" in history.data
    listing = aces_sortie_service.list_aces_sorties(campaign.id)
    assert listing[0]["net_sp"] is None


def test_report_and_history_unavailable_for_chaos(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    assert (
        client.get(f"/campaigns/{chaos.id}/sortie-history", follow_redirects=True).status_code
        == 200
    )
    with session_scope() as session:
        sortie = Sortie(campaign_id=chaos.id, name="C", status="closed")
        session.add(sortie)
        session.flush()
        sortie_id = sortie.id
    assert svc.get_sortie_report(sortie_id) is None


def test_sortie_history_net_sp_and_mvp(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, primary_objective_sp=500, max_pilot_sp=0)
    [row] = aces_sortie_service.list_aces_sorties(campaign.id)
    assert row["mvp"] == "Hawk"
    assert row["net_sp"] == 500 - 20  # income minus rearm, no pilot pool
    assert row["force_pv"] == 40
    assert row["date_played"] == date.today()
    assert row["label"] == "Sortie 1"


def test_result_picker_explains_each_outcome(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    html = client.get(f"/sorties/{sortie.id}").data.decode()
    for key, entry in svc.DAMAGE_HELP.items():
        assert f'value="{key}"' in html
        assert entry["label"] in html
    assert svc.DAMAGE_HELP_NOTE.split(".")[0] in html  # the crippled vs destroyed note
    assert 'id="damageHelpIcon"' in html
    assert "Size × 60 SP" in html and "Size × 100 SP" in html
    assert set(svc.DAMAGE_HELP) == set(svc.ACES_DAMAGE_OUTCOMES)


def test_result_help_costs_match_the_repair_rules(client):
    from app.services import campaign_rules

    for key, multiplier in campaign_rules.ACES_REPAIR_MULTIPLIERS.items():
        assert f"Size × {multiplier} SP" in svc.DAMAGE_HELP[key]["cost"]


def test_improvement_form_shows_invested_sp_and_next_threshold(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=1000, max_pilot_sp=200)
    html = client.get(f"/sorties/{sortie.id}").data.decode()
    for track in ("skill", "edge", "ability"):
        assert f'data-info="{track}"' in html
    # The form carries what the pilot has already invested, plus the threshold tables the
    # script uses to show the next bump (Hawk: 150 Skill SP, nothing else yet).
    assert 'data-skill="150" data-edge="0"' in html
    assert 'data-ability="0"' in html
    assert "next at " in html and "to go" in html and "maxed out" in html


def test_improvement_boxes_cannot_exceed_the_sp_to_allocate(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=1000, max_pilot_sp=45)
    html = client.get(f"/sorties/{sortie.id}").data.decode()
    assert "function clampToTotal" in html
    assert "inputs[k].max = Math.max(0, total - (sum - raw(k)))" in html
    # The server still refuses an over- or under-allocation.
    with pytest.raises(ValueError, match="must be allocated"):
        svc.allocate_pilot_share(sortie.id, hawk.id, skill_sp=30, edge_sp=25, ability_sp=0)
