"""Aces Sorties: pilot assignment, Force Commander, date played, failure/replay, keywords (6b)."""

from __future__ import annotations

from datetime import date

import pytest

from app.extensions import session_scope
from app.models.campaign_pilot import CampaignPilot
from app.models.campaign_unit import CampaignUnit
from app.models.sortie import Sortie
from app.models.sortie_unit import SortieUnit
from app.models.story_keyword_event import StoryKeywordEvent
from app.services import (
    aces_pilot_service,
    aces_sortie_service,
    campaign_service,
    contract_service,
)


def _setup(force_id, name="Aces Sorties"):
    """Aces campaign with two typed BM units and two BM Named Pilots."""
    campaign = campaign_service.create_campaign_from_force(
        force_id, name, ruleset="aces", starting_bt_year=3151, starting_bt_month=1
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
    campaign = campaign_service.get_campaign_by_id(campaign.id)
    return campaign, pilots


def _sortie_with_units(campaign, name="Waypoint 1"):
    sortie = campaign_service.create_aces_sortie(campaign.id, name)
    rows = [contract_service.add_unit_to_sortie(sortie.id, unit.id) for unit in campaign.units[:2]]
    return sortie, rows


def _ready_sortie(campaign, pilots, name="Waypoint 1"):
    sortie, rows = _sortie_with_units(campaign, name)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    contract_service.assign_sortie_pilot(rows[1].id, pilots[1].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.mark_sortie_ready(sortie.id)
    return sortie, rows


# --- numbering and date played -----------------------------------------------------------


def test_aces_sortie_gets_number_attempt_and_default_date(client, minimal_force):
    campaign, _ = _setup(minimal_force)
    first = campaign_service.create_aces_sortie(campaign.id, "One")
    assert first.sortie_number == 1
    assert first.attempt_number == 1
    assert first.attempt_label == "Sortie 1"
    assert first.date_played == date.today()
    second = campaign_service.create_aces_sortie(campaign.id, "Two", date_played=date(2026, 3, 4))
    assert second.sortie_number == 2
    assert second.date_played == date(2026, 3, 4)


def test_date_played_editable_until_ready(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _sortie_with_units(campaign)
    updated = contract_service.update_sortie(sortie.id, date_played=date(2026, 1, 2))
    assert updated.date_played == date(2026, 1, 2)
    _, rows = _sortie_with_units(campaign, "Other")  # second Sortie, to prove isolation
    ready_sortie, _ = _ready_sortie(campaign, pilots, "Third")
    with pytest.raises(ValueError, match="locked"):
        contract_service.update_sortie(ready_sortie.id, date_played=date(2026, 5, 5))


# --- pilot assignment ---------------------------------------------------------------------


def test_pilot_type_must_match_unit_type(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    with session_scope() as session:
        cv = session.query(CampaignUnit).filter_by(campaign_id=campaign.id).all()[1]
        cv.unit_type_name = "Combat Vehicle"
    campaign = campaign_service.get_campaign_by_id(campaign.id)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)  # BM on BattleMech: ok
    with pytest.raises(ValueError, match="cannot crew"):
        contract_service.assign_sortie_pilot(rows[1].id, pilots[1].id)  # BM on CV


def test_infantry_cannot_have_named_pilot(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    with session_scope() as session:
        unit = session.query(CampaignUnit).filter_by(campaign_id=campaign.id).first()
        unit.unit_type_name = "Conventional Infantry"
    campaign = campaign_service.get_campaign_by_id(campaign.id)
    sortie, rows = _sortie_with_units(campaign)
    with pytest.raises(ValueError, match="cannot crew"):
        contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)


def test_one_unit_per_pilot(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    _, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    with pytest.raises(ValueError, match="only crew one unit"):
        contract_service.assign_sortie_pilot(rows[1].id, pilots[0].id)


def test_preferred_unit_not_applied_in_aces(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilots[0].id)
        pilot.preferred_unit_id = campaign.units[0].id
    sortie = campaign_service.create_aces_sortie(campaign.id, "No Auto")
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    assert row.campaign_pilot_id is None
    assert row.is_generic_crew is True


def test_sortie_unit_snapshots_pilot_and_survives_advancement(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    row = contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    assert row.pilot_name == "Hawk"
    assert row.pilot_callsign == "Hawk"
    assert row.pilot_type == "BM"
    assert row.alpha_strike_skill == 4
    assert row.pilot_edge_tokens == 1

    # The pilot improves later; the stored Sortie snapshot must not change.
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilots[0].id)
        aces_pilot_service.apply_advancement(
            session,
            pilot,
            source_type="sortie",
            sp_received=450,
            skill_sp=400,
            edge_sp=50,
            ability_sp=0,
            new_abilities=[],
        )
    with session_scope() as session:
        stored = session.get(SortieUnit, row.id)
        assert stored.alpha_strike_skill == 4
        assert stored.pilot_edge_tokens == 1
        assert session.get(CampaignPilot, pilots[0].id).alpha_strike_skill == 3


# --- Force Commander ----------------------------------------------------------------------


def test_force_commander_must_participate(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    with pytest.raises(ValueError, match="participating"):
        aces_sortie_service.set_force_commander(sortie.id, pilots[1].id)
    result = aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    assert result.force_commander_pilot_id == pilots[0].id
    assert result.force_commander_callsign == "Hawk"


def test_force_commander_cleared_when_pilot_leaves_sortie(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.assign_sortie_pilot(rows[0].id, None)
    assert contract_service.get_sortie_by_id(sortie.id).force_commander_pilot_id is None

    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.remove_sortie_unit(rows[0].id)
    assert contract_service.get_sortie_by_id(sortie.id).force_commander_pilot_id is None


def test_ready_requires_commander_date_and_two_pilots(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    with pytest.raises(ValueError, match="Force Commander"):
        contract_service.mark_sortie_ready(sortie.id)

    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    with session_scope() as session:
        session.get(Sortie, sortie.id).date_played = None
    with pytest.raises(ValueError, match="Date played"):
        contract_service.mark_sortie_ready(sortie.id)

    contract_service.update_sortie(sortie.id, date_played=date.today())
    aces_pilot_service.retire_aces_pilot(pilots[1].id)
    with pytest.raises(ValueError, match="at least 2"):
        contract_service.mark_sortie_ready(sortie.id)


def test_ready_records_commander_callsign(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    stored = contract_service.get_sortie_by_id(sortie.id)
    assert stored.status == "ready"
    assert stored.force_commander_callsign == "Hawk"


# --- failed Sorties and replays -----------------------------------------------------------


def test_only_ready_or_fought_sortie_can_fail(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _sortie_with_units(campaign)
    with pytest.raises(ValueError, match="Ready or Fought"):
        aces_sortie_service.fail_sortie(sortie.id)


def test_failed_sortie_is_history_and_applies_no_consequences(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _ready_sortie(campaign, pilots)
    contract_service.mark_sortie_fought(sortie.id)
    before = campaign_service.get_campaign_by_id(campaign.id)
    failed = aces_sortie_service.fail_sortie(sortie.id, "Objective lost")
    assert failed.status == "failed"
    assert failed.outcome == "failed"
    assert failed.after_action_notes == "Objective lost"
    assert failed.force_commander_callsign == "Hawk"

    after = campaign_service.get_campaign_by_id(campaign.id)
    assert after.warchest_balance == before.warchest_balance
    assert all(unit.condition == "active" for unit in after.units)
    # Force snapshot and participation preserved.
    stored = contract_service.get_sortie_by_id(sortie.id)
    assert {row.pilot_callsign for row in stored.units} == {"Hawk", "Ghost"}
    # Normal After-Sortie processing is unavailable.
    from app.services import after_action_service

    with pytest.raises(ValueError):
        after_action_service.apply_after_action(sortie.id, [])


def test_failed_sortie_requires_replay_before_new_sortie(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    assert aces_sortie_service.get_replay_required(campaign.id).id == sortie.id
    with pytest.raises(ValueError, match="must be replayed"):
        campaign_service.create_aces_sortie(campaign.id, "Next")

    replay = aces_sortie_service.create_replay(sortie.id)
    assert aces_sortie_service.get_replay_required(campaign.id) is None
    assert replay.replay_of_sortie_id == sortie.id
    campaign_service.create_aces_sortie(campaign.id, "Next")  # no longer blocked


def test_replay_copies_force_pilots_and_commander_and_links(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)

    assert replay.status == "planning"
    assert replay.sortie_number == sortie.sortie_number
    assert replay.attempt_number == 2
    assert replay.attempt_label == "Sortie 1R"
    stored = contract_service.get_sortie_by_id(replay.id)
    assert {row.pilot_callsign for row in stored.units} == {"Hawk", "Ghost"}
    assert stored.force_commander_callsign == "Hawk"

    lineage_failed = aces_sortie_service.get_lineage(sortie.id)
    lineage_replay = aces_sortie_service.get_lineage(replay.id)
    assert lineage_failed["replayed_by"].id == replay.id
    assert lineage_replay["replay_of"].id == sortie.id
    # The failed attempt is still there, unchanged.
    assert contract_service.get_sortie_by_id(sortie.id).status == "failed"


def test_replay_can_be_modified(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)
    stored = contract_service.get_sortie_by_id(replay.id)
    contract_service.remove_sortie_unit(stored.units[1].id)
    assert len(contract_service.get_sortie_by_id(replay.id).units) == 1
    assert len(contract_service.get_sortie_by_id(sortie.id).units) == 2


def test_wounded_pilot_stays_unavailable_on_replay(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    with session_scope() as session:  # wounded pilot sitting out the retry
        pilot = session.get(CampaignPilot, pilots[1].id)
        pilot.wounds = 1
        pilot.wounded = True
    replay = aces_sortie_service.create_replay(sortie.id)
    stored = contract_service.get_sortie_by_id(replay.id)
    callsigns = {row.pilot_callsign for row in stored.units if row.campaign_pilot_id}
    assert callsigns == {"Hawk"}


def test_replay_attempt_labels_and_single_replay(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    second = aces_sortie_service.create_replay(sortie.id)
    with pytest.raises(ValueError, match="already has a replay"):
        aces_sortie_service.create_replay(sortie.id)
    with pytest.raises(ValueError, match="Only a failed"):
        aces_sortie_service.create_replay(second.id)

    contract_service.mark_sortie_ready(second.id)
    aces_sortie_service.fail_sortie(second.id)
    third = aces_sortie_service.create_replay(second.id)
    assert third.attempt_label == "Sortie 1R2"


def test_failed_attempts_listed_in_campaign_history(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    aces_sortie_service.create_replay(sortie.id)
    listing = aces_sortie_service.list_aces_sorties(campaign.id)
    assert [item["label"] for item in listing] == ["Sortie 1", "Sortie 1R"]
    assert [item["status"] for item in listing] == ["failed", "planning"]


# --- Story Keywords -----------------------------------------------------------------------


def _fought_sortie(campaign, pilots, name="Waypoint 1"):
    sortie, _ = _ready_sortie(campaign, pilots, name)
    contract_service.mark_sortie_fought(sortie.id)
    return sortie


def test_keyword_requires_fought_sortie(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, _ = _ready_sortie(campaign, pilots)
    with pytest.raises(ValueError, match="after the Sortie has been fought"):
        aces_sortie_service.record_story_keyword(sortie.id, "Betrayal")


def test_successful_sortie_can_award_keyword(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie = _fought_sortie(campaign, pilots)
    aces_sortie_service.record_story_keyword(sortie.id, "  Betrayal ")
    assert aces_sortie_service.get_current_keywords(campaign.id) == ["Betrayal"]
    assert aces_sortie_service.get_sortie_keywords(sortie.id)["gained"] == ["Betrayal"]


def test_failed_sortie_cannot_award_keyword(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie = _fought_sortie(campaign, pilots)
    aces_sortie_service.fail_sortie(sortie.id)
    with pytest.raises(ValueError, match="Failed Sorties"):
        aces_sortie_service.record_story_keyword(sortie.id, "Betrayal")
    assert aces_sortie_service.get_current_keywords(campaign.id) == []


def test_duplicate_keyword_and_unheld_removal_rejected(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie = _fought_sortie(campaign, pilots)
    aces_sortie_service.record_story_keyword(sortie.id, "Betrayal")
    with pytest.raises(ValueError, match="already held"):
        aces_sortie_service.record_story_keyword(sortie.id, "betrayal")
    with pytest.raises(ValueError, match="not currently held"):
        aces_sortie_service.record_story_keyword(sortie.id, "Sabotage", "removed")
    with pytest.raises(ValueError, match="acquired or removed"):
        aces_sortie_service.record_story_keyword(sortie.id, "X", "lost")


def test_keyword_history_preserved_and_current_set_derived(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    first = _fought_sortie(campaign, pilots, "One")
    aces_sortie_service.record_story_keyword(first.id, "Betrayal")
    aces_sortie_service.record_story_keyword(first.id, "Ally")
    with session_scope() as session:
        session.get(Sortie, first.id).status = "closed"

    second = _fought_sortie(campaign, pilots, "Two")
    aces_sortie_service.record_story_keyword(second.id, "Betrayal", "removed")

    assert aces_sortie_service.get_current_keywords(campaign.id) == ["Ally"]
    # The Sortie that originally granted it still shows the historical event.
    assert aces_sortie_service.get_sortie_keywords(first.id)["gained"] == ["Betrayal", "Ally"]
    assert aces_sortie_service.get_sortie_keywords(second.id)["removed"] == ["Betrayal"]
    with session_scope() as session:
        assert session.query(StoryKeywordEvent).count() == 3


def test_keyword_event_is_immutable(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie = _fought_sortie(campaign, pilots)
    aces_sortie_service.record_story_keyword(sortie.id, "Betrayal")
    with pytest.raises(ValueError, match="immutable"):
        with session_scope() as session:
            session.query(StoryKeywordEvent).first().keyword = "Edited"


def test_chaos_sortie_rejects_keywords(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with session_scope() as session:
        sortie = Sortie(campaign_id=chaos.id, name="C", status="fought")
        session.add(sortie)
        session.flush()
        sortie_id = sortie.id
    with pytest.raises(ValueError, match="only available for Aces"):
        aces_sortie_service.record_story_keyword(sortie_id, "Betrayal")


# --- routes -------------------------------------------------------------------------------


def test_sortie_page_force_commander_fail_replay_and_history_links(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    contract_service.assign_sortie_pilot(rows[1].id, pilots[1].id)

    page = client.get(f"/sorties/{sortie.id}")
    assert page.status_code == 200
    assert b"Force Commander" in page.data
    assert b"Sortie 1" in page.data

    resp = client.post(
        f"/sorties/{sortie.id}/force-commander",
        data={"pilot_id": str(pilots[0].id)},
        follow_redirects=True,
    )
    assert b"Force Commander saved" in resp.data
    assert client.post(f"/sorties/{sortie.id}/ready", follow_redirects=True).status_code == 200

    failed = client.post(
        f"/sorties/{sortie.id}/fail", data={"notes": "lost"}, follow_redirects=True
    )
    assert b"must be replayed" in failed.data
    assert b"Create replay attempt" in failed.data

    campaign_page = client.get(f"/campaigns/{campaign.id}")
    assert b"failed and must be replayed" in campaign_page.data

    replay = client.post(f"/sorties/{sortie.id}/replay", follow_redirects=True)
    assert b"Sortie 1R" in replay.data
    assert b"Replay of" in replay.data

    history = client.get(f"/campaigns/pilots/{pilots[0].id}/history")
    assert history.status_code == 200
    assert b"Sortie 1" in history.data
    assert b"Force Commander" in history.data


def test_keyword_route_and_campaign_summary(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie = _fought_sortie(campaign, pilots)
    resp = client.post(
        f"/sorties/{sortie.id}/keywords",
        data={"keyword": "Betrayal", "action": "acquired"},
        follow_redirects=True,
    )
    assert b"Story Keyword recorded" in resp.data
    assert b"Betrayal" in resp.data
    summary = client.get(f"/campaigns/{campaign.id}")
    assert b"Story Keywords" in summary.data
    assert b"Betrayal" in summary.data


# --- Force Commander dropdown ---------------------------------------------------------------


def _fc_card(html: str) -> str:
    start = html.index("Force Commander</h5>")
    return html[start : html.index("</form>", start)]


def test_force_commander_dropdown_explains_it_needs_assigned_pilots(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    sortie, rows = _sortie_with_units(campaign)
    card = _fc_card(client.get(f"/sorties/{sortie.id}").data.decode())
    assert "No Named Pilot is crewing a unit yet" in card
    assert "disabled" in card
    assert "Hawk" not in card

    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    card = _fc_card(client.get(f"/sorties/{sortie.id}").data.decode())
    assert "No Named Pilot is crewing a unit yet" not in card
    assert "disabled" not in card
    assert "Hawk" in card
    assert "Ghost" not in card  # only pilots crewing a unit in this Sortie


def test_unit_pilot_dropdown_says_why_a_unit_has_no_pilot_choices(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    with session_scope() as session:
        units = session.query(CampaignUnit).filter_by(campaign_id=campaign.id).all()
        units[0].unit_type_name = "Combat Vehicle"
        units[1].unit_type_name = "Conventional Infantry"
    campaign = campaign_service.get_campaign_by_id(campaign.id)
    sortie, _ = _sortie_with_units(campaign)
    html = client.get(f"/sorties/{sortie.id}").data.decode()
    assert "No available CV pilots" in html
    assert "This unit type cannot have a Named Pilot" in html
    assert "this.form.submit()" in html  # choosing a pilot saves immediately


# --- Jeff's BT Tools export of the Sortie force -------------------------------------------

JEFF_RAW = {
    "Id": 7563,
    "Name": "Warhammer WHM-8R",
    "Class": "Warhammer",
    "Variant": "WHM-8R",
    "Tonnage": 70,
    "BFPointValue": 40,
    "BFMove": '8"',
    "BFArmor": 5,
    "BFStructure": 4,
    "BFDamageShort": 4,
    "BFDamageMedium": 4,
    "BFDamageLong": 2,
    "BFAbilities": "IF, SRM",
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _give_mul_data(campaign):
    import json

    with session_scope() as session:
        for unit in session.query(CampaignUnit).filter_by(campaign_id=campaign.id):
            unit.mul_snapshot_json = json.dumps(JEFF_RAW)


def test_sortie_force_exports_to_jeff_with_pilot_skill_and_edge(client, minimal_force):
    import json

    from app.services import jeff_export_service

    campaign, pilots = _setup(minimal_force)
    _give_mul_data(campaign)
    sortie, rows = _sortie_with_units(campaign)  # second unit stays generic crew
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)

    text, filename = jeff_export_service.export_jeff_sortie(sortie.id)
    group = json.loads(text)
    assert filename.startswith("JeffGroup_Sortie 1 Waypoint 1_") and filename.endswith(".json")
    assert group["name"] == "Sortie 1 Waypoint 1"
    assert len(group["members"]) == 2
    hawk, generic = group["members"]
    assert hawk["pilot"]["name"] == "Hawk (BM, Edge 1)"
    assert hawk["currentSkill"] == 4 and hawk["pilot"]["gunnery"] == 4
    assert hawk["customName"].startswith("Hawk · ")
    assert hawk["variant"] == "WHM-8R" and hawk["basePoints"] == 40
    assert generic["pilot"]["name"] == ""
    assert generic["customName"].startswith("Generic crew · ")


def test_sortie_export_uses_the_frozen_pilot_snapshot(client, minimal_force):
    import json

    from app.services import jeff_export_service

    campaign, pilots = _setup(minimal_force)
    _give_mul_data(campaign)
    sortie, rows = _sortie_with_units(campaign)
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    with session_scope() as session:  # Hawk improves after the Sortie was prepared
        aces_pilot_service.apply_advancement(
            session,
            session.get(CampaignPilot, pilots[0].id),
            source_type="sortie",
            sp_received=450,
            skill_sp=400,
            edge_sp=50,
            ability_sp=0,
            new_abilities=[],
        )
    member = json.loads(jeff_export_service.export_jeff_sortie(sortie.id)[0])["members"][0]
    assert member["currentSkill"] == 4  # as fielded when the Sortie was set up
    assert member["pilot"]["name"] == "Hawk (BM, Edge 1)"


def test_sortie_export_route_and_button(client, minimal_force):
    import json

    campaign, pilots = _setup(minimal_force)
    _give_mul_data(campaign)
    sortie, rows = _sortie_with_units(campaign)

    page = client.get(f"/sorties/{sortie.id}").data.decode()
    assert f"/sorties/{sortie.id}/export/jeff" in page
    assert "Export to Jeff" in page

    resp = client.get(f"/sorties/{sortie.id}/export/jeff")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert len(json.loads(resp.data)["members"]) == 2


def test_sortie_export_needs_units_and_alpha_strike_data(client, minimal_force):
    campaign, pilots = _setup(minimal_force)
    empty = campaign_service.create_aces_sortie(campaign.id, "Empty")
    page = client.get(f"/sorties/{empty.id}").data.decode()
    assert "Export to Jeff" not in page  # nothing to export yet
    resp = client.get(f"/sorties/{empty.id}/export/jeff", follow_redirects=True)
    assert b"Add units to the Sortie force before exporting" in resp.data

    contract_service.add_unit_to_sortie(empty.id, campaign.units[0].id)  # no MUL snapshot
    resp = client.get(f"/sorties/{empty.id}/export/jeff", follow_redirects=True)
    assert b"no Alpha Strike data to export" in resp.data
