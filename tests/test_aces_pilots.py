"""Aces Named Pilots: threshold rules, creation, advancement, history (Prompt 6a)."""

from __future__ import annotations

import pytest

from app.extensions import session_scope
from app.models.campaign_pilot import CampaignPilot
from app.models.pilot_advancement_event import PilotAdvancementEvent
from app.services import aces_pilot_rules as rules
from app.services import aces_pilot_service, campaign_service


def _aces_campaign(force_id, name="Aces Pilots"):
    return campaign_service.create_campaign_from_force(
        force_id, name, ruleset="aces", starting_bt_year=3151, starting_bt_month=1
    )


def _pilot(
    campaign_id, callsign="Hawk", pilot_type="BM", skill=150, edge=0, ability=0, abilities=None
):
    return aces_pilot_service.create_aces_pilot(
        campaign_id,
        callsign,
        pilot_type,
        skill_sp=skill,
        edge_sp=edge,
        ability_sp=ability,
        abilities=abilities,
    )


# --- threshold rules -------------------------------------------------------------------


@pytest.mark.parametrize(
    "sp,skill",
    [(0, 4), (399, 4), (400, 3), (899, 3), (900, 2), (1900, 1), (3399, 1), (3400, 0), (9999, 0)],
)
def test_skill_thresholds(sp, skill):
    assert rules.skill_for_sp(sp) == skill


@pytest.mark.parametrize(
    "sp,tokens",
    [(0, 1), (59, 1), (60, 2), (120, 3), (299, 4), (300, 5), (1099, 9), (1100, 10), (5000, 10)],
)
def test_edge_token_thresholds(sp, tokens):
    assert rules.edge_tokens_for_sp(sp) == tokens


@pytest.mark.parametrize(
    "sp,count", [(0, 0), (59, 0), (60, 1), (179, 1), (180, 2), (360, 3), (600, 4), (900, 5)]
)
def test_edge_ability_thresholds(sp, count):
    assert rules.ability_count_for_sp(sp) == count


def test_allocation_must_total_exactly():
    rules.validate_allocation(150, 100, 30, 20)
    with pytest.raises(ValueError, match="must be allocated"):
        rules.validate_allocation(150, 100, 30, 10)
    with pytest.raises(ValueError, match="must be allocated"):
        rules.validate_allocation(150, 100, 30, 30)
    with pytest.raises(ValueError, match="negative"):
        rules.validate_allocation(150, 200, -50, 0)


def test_catalogue_contains_current_abilities():
    assert len(rules.EDGE_ABILITIES) == 12
    assert "Marksman" in rules.EDGE_ABILITIES
    assert "Forward Observer" in rules.EDGE_ABILITIES


# --- creation --------------------------------------------------------------------------


def test_create_pilot_requires_callsign_not_personal_name(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, callsign="  Ghost  ")
    assert pilot.callsign == "Ghost"
    assert pilot.display_name == "Ghost"
    with pytest.raises(ValueError, match="Callsign is required"):
        _pilot(campaign.id, callsign="   ")


def test_pilot_uses_skill_only_and_starting_values(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=150)
    assert pilot.alpha_strike_skill == 4
    assert pilot.edge_tokens == 1
    assert pilot.edge_abilities is None
    assert pilot.total_sp_earned == 150
    assert (pilot.skill_sp, pilot.edge_sp, pilot.ability_sp) == (150, 0, 0)


def test_pilot_type_required_and_valid(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    for bad in ("", "CI", "bm", "XX"):
        with pytest.raises(ValueError, match="Pilot Type"):
            _pilot(campaign.id, pilot_type=bad)
    for code in ("BM", "CV", "BA"):
        assert _pilot(campaign.id, callsign=f"P-{code}", pilot_type=code).pilot_type == code


def test_starting_sp_must_be_fully_allocated(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    with pytest.raises(ValueError, match="must be allocated"):
        _pilot(campaign.id, skill=100)
    with pytest.raises(ValueError, match="must be allocated"):
        _pilot(campaign.id, skill=151)


def test_starting_allocation_derives_edge_and_requires_ability_pick(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    # 60 edge SP => 2 tokens; 60 ability SP => 1 ability that must be chosen now.
    with pytest.raises(ValueError, match="Select exactly 1"):
        _pilot(campaign.id, skill=30, edge=60, ability=60)
    pilot = _pilot(campaign.id, skill=30, edge=60, ability=60, abilities=["Marksman"])
    assert pilot.edge_tokens == 2
    assert pilot.edge_abilities == "Marksman"
    assert pilot.alpha_strike_skill == 4


def test_pilot_limit_is_six_living_pilots(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilots = [_pilot(campaign.id, callsign=f"P{i}") for i in range(rules.MAX_NAMED_PILOTS)]
    with pytest.raises(ValueError, match="at most 6"):
        _pilot(campaign.id, callsign="Seventh")
    # Retiring frees a slot, and the retired pilot stays in history.
    aces_pilot_service.retire_aces_pilot(pilots[0].id)
    _pilot(campaign.id, callsign="Seventh")
    assert aces_pilot_service.get_pilot_service_history(pilots[0].id) is not None


def test_callsign_unique_per_campaign(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    _pilot(campaign.id, callsign="Razor")
    with pytest.raises(ValueError, match="already used"):
        _pilot(campaign.id, callsign="razor")


def test_chaos_campaign_rejects_aces_pilot(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with pytest.raises(ValueError, match="only available for Aces"):
        _pilot(chaos.id)


# --- advancement -----------------------------------------------------------------------


def _advance(pilot_id, **kwargs):
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        event = aces_pilot_service.apply_advancement(session, pilot, **kwargs)
        return event.id


def test_creation_writes_initial_event(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=90, edge=60)
    with session_scope() as session:
        events = session.query(PilotAdvancementEvent).filter_by(campaign_pilot_id=pilot.id).all()
        assert len(events) == 1
        event = events[0]
        assert event.source_type == "initial"
        assert event.sequence == 1
        assert event.sp_received == 150
        assert (event.skill_sp_allocated, event.edge_sp_allocated) == (90, 60)
        assert event.edge_tokens_after == 2
        assert event.total_sp_after == 150


def test_sp_can_be_invested_without_crossing_threshold(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=120, ability=30)
    _advance(
        pilot.id,
        source_type="sortie",
        sp_received=20,
        skill_sp=0,
        edge_sp=0,
        ability_sp=20,
        new_abilities=[],
    )
    with session_scope() as session:
        stored = session.get(CampaignPilot, pilot.id)
        assert stored.ability_sp == 50
        assert rules.ability_count_for_sp(stored.ability_sp) == 0
        assert stored.edge_abilities is None


def test_spec_example_150_to_390_requires_two_new_abilities(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=0, ability=150, abilities=["Marksman"])
    # 150 -> 390 crosses 180 (2nd) and 360 (3rd): two new picks are required.
    common = {
        "source_type": "sortie",
        "sp_received": 240,
        "skill_sp": 0,
        "edge_sp": 0,
        "ability_sp": 240,
    }
    with pytest.raises(ValueError, match="Select exactly 2"):
        _advance(pilot.id, new_abilities=["Patient"], **common)
    _advance(pilot.id, new_abilities=["Bulwark", "Patient"], **common)
    with session_scope() as session:
        stored = session.get(CampaignPilot, pilot.id)
        assert stored.edge_abilities == "Marksman, Bulwark, Patient"
        assert stored.ability_sp == 390


def test_two_thresholds_in_one_advancement_need_two_picks(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=120, ability=30)  # 30 ability SP: 0 abilities
    common = {
        "source_type": "sortie",
        "sp_received": 330,
        "skill_sp": 0,
        "edge_sp": 0,
        "ability_sp": 330,
    }
    # 30 + 330 = 360 => 3 abilities
    with pytest.raises(ValueError, match="Select exactly 3"):
        _advance(pilot.id, new_abilities=["Marksman"], **common)
    _advance(pilot.id, new_abilities=["Marksman", "Bulwark", "Patient"], **common)


def test_duplicate_and_unknown_abilities_rejected(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=90, ability=60, abilities=["Nimble"])
    common = {
        "source_type": "sortie",
        "sp_received": 120,
        "skill_sp": 0,
        "edge_sp": 0,
        "ability_sp": 120,
    }
    with pytest.raises(ValueError, match="already has"):
        _advance(pilot.id, new_abilities=["Nimble"], **common)
    with pytest.raises(ValueError, match="Unknown Edge Ability"):
        _advance(pilot.id, new_abilities=["Teleport"], **common)
    two = dict(common, sp_received=300, ability_sp=300)  # 180 + 300 = 480 => 3 abilities total
    with pytest.raises(ValueError, match="selected twice"):
        _advance(pilot.id, new_abilities=["Assassin", "Assassin"], **two)


def test_mvp_bonus_adds_20_sp_and_must_be_allocated(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id)
    with pytest.raises(ValueError, match="must be allocated"):
        _advance(
            pilot.id,
            source_type="sortie",
            sp_received=100,
            mvp_bonus=20,
            skill_sp=100,
            edge_sp=0,
            ability_sp=0,
            new_abilities=[],
        )
    _advance(
        pilot.id,
        source_type="sortie",
        sp_received=100,
        mvp_bonus=20,
        skill_sp=100,
        edge_sp=20,
        ability_sp=0,
        new_abilities=[],
    )
    with session_scope() as session:
        stored = session.get(CampaignPilot, pilot.id)
        assert stored.total_sp_earned == 270
        assert stored.total_sp_earned == stored.skill_sp + stored.edge_sp + stored.ability_sp


def test_total_sp_invariant_after_many_advancements(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, skill=100, edge=50)
    for _ in range(3):
        _advance(
            pilot.id,
            source_type="sortie",
            sp_received=100,
            skill_sp=60,
            edge_sp=40,
            ability_sp=0,
            new_abilities=[],
        )
    with session_scope() as session:
        stored = session.get(CampaignPilot, pilot.id)
        assert stored.total_sp_earned == 450
        assert stored.skill_sp + stored.edge_sp + stored.ability_sp == 450
        assert stored.alpha_strike_skill == rules.skill_for_sp(stored.skill_sp)
        assert stored.edge_tokens == rules.edge_tokens_for_sp(stored.edge_sp)


def test_advancement_event_is_immutable(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id)
    with pytest.raises(ValueError, match="immutable"):
        with session_scope() as session:
            event = session.query(PilotAdvancementEvent).filter_by(campaign_pilot_id=pilot.id).one()
            event.sp_received = 999


def test_aces_pilot_cannot_be_deleted_or_directly_edited(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id)
    with pytest.raises(ValueError, match="cannot be deleted"):
        campaign_service.delete_campaign_pilot(pilot.id)
    with pytest.raises(ValueError, match="derived"):
        campaign_service.update_campaign_pilot(pilot.id, alpha_strike_skill=1)


def test_campaign_delete_removes_advancement_events(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    _pilot(campaign.id)
    assert campaign_service.delete_campaign(campaign.id)
    with session_scope() as session:
        assert session.query(PilotAdvancementEvent).count() == 0


# --- service history -------------------------------------------------------------------


def test_service_history_is_chronological_and_complete(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    pilot = _pilot(campaign.id, callsign="Warden", skill=90, ability=60, abilities=["Cautious"])
    _advance(
        pilot.id,
        source_type="sortie",
        sp_received=40,
        mvp_bonus=20,
        skill_sp=60,
        edge_sp=0,
        ability_sp=0,
        new_abilities=[],
        participation_state="participant",
    )
    history = aces_pilot_service.get_pilot_service_history(pilot.id)
    assert history["type_label"] == "BattleMech"
    assert history["abilities"] == ["Cautious"]
    kinds = [(item["kind"], item["event"].source_type) for item in history["timeline"]]
    assert kinds == [("advancement", "initial"), ("advancement", "sortie")]
    assert history["timeline"][0]["new_abilities"] == ["Cautious"]
    assert history["timeline"][1]["event"].mvp_bonus == 20


# --- routes ----------------------------------------------------------------------------


def test_aces_detail_renders_pilot_card_and_history_page(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    resp = client.get(f"/campaigns/{campaign.id}")
    assert resp.status_code == 200
    assert b"New Named Pilot" in resp.data
    assert b"acesPilotForm" in resp.data

    post = client.post(
        f"/campaigns/{campaign.id}/aces-pilots",
        data={
            "callsign": "Hawk",
            "pilot_type": "BM",
            "skill_sp": "90",
            "edge_sp": "0",
            "ability_sp": "60",
            "abilities": ["Marksman"],
        },
        follow_redirects=True,
    )
    assert post.status_code == 200
    assert b"Hawk" in post.data

    with session_scope() as session:
        pilot = session.query(CampaignPilot).filter_by(campaign_id=campaign.id).one()
        pilot_id = pilot.id
    history = client.get(f"/campaigns/pilots/{pilot_id}/history")
    assert history.status_code == 200
    assert b"Pilot Service History" in history.data
    assert b"Marksman" in history.data


def test_route_rejects_unallocated_sp(client, minimal_force):
    campaign = _aces_campaign(minimal_force)
    resp = client.post(
        f"/campaigns/{campaign.id}/aces-pilots",
        data={"callsign": "Hawk", "pilot_type": "BM", "skill_sp": "100"},
        follow_redirects=True,
    )
    assert b"must be allocated" in resp.data
    with session_scope() as session:
        assert session.query(CampaignPilot).filter_by(campaign_id=campaign.id).count() == 0


def test_chaos_detail_still_shows_legacy_pilot_form(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos UI", starting_bt_year=3151, starting_bt_month=1
    )
    resp = client.get(f"/campaigns/{campaign.id}")
    assert b"Pilot name" in resp.data
    assert b"acesPilotForm" not in resp.data
