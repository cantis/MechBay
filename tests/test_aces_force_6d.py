"""Aces force creation, Sortie PV limits, Omni, purchases and sales (Prompt 6d)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.extensions import session_scope
from app.models.aces_sortie_report import AcesSortieReport
from app.models.alpha_strike_assignment import AlphaStrikeAssignment
from app.models.campaign import Campaign
from app.models.campaign_unit import CampaignUnit
from app.models.unit_configuration_event import UnitConfigurationEvent
from app.services import (
    aces_after_action_service as svc,
)
from app.services import (
    aces_pilot_service,
    aces_sortie_service,
    campaign_rules,
    campaign_service,
    contract_service,
    force_service,
)
from tests.conftest import apply_aces

# --- pure rules ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sp", "modifier"),
    [
        (0, 0),
        (3000, 0),
        (3001, -10),
        (6000, -10),
        (6001, -20),
        (9000, -20),
        (9001, -30),
        (12000, -30),
        (12001, -40),
        (50000, -40),
    ],
)
def test_experienced_force_tiers(sp, modifier):
    assert campaign_rules.experienced_force_modifier_percent(sp) == modifier


def test_difficulty_and_experienced_modifiers_stack_additively():
    assert campaign_rules.aces_pv_allowance_percent("Veteran", 7000) == -10 + -20
    assert campaign_rules.aces_pv_allowance_percent("Rookie", 0) == 20
    assert campaign_rules.aces_allowed_sortie_pv(400, "Standard", 0) == 400
    assert campaign_rules.aces_allowed_sortie_pv(400, "Veteran", 7000) == 280
    assert campaign_rules.aces_allowed_sortie_pv(99, "Legendary", 0) == 69  # floored
    assert campaign_rules.aces_allowed_sortie_pv(0, "Rookie", 0) == 0


def test_experienced_modifier_does_not_touch_objective_sp():
    assert campaign_rules.objective_sp_percent("Standard") == 100
    assert campaign_rules.adjusted_objective_sp(100, "Standard") == 100


def test_omni_cost_rules():
    assert campaign_rules.aces_omni_cost(40, 40, 3) == 15  # equal PV: Size x 5
    assert campaign_rules.aces_omni_cost(40, 30, 3) == 15  # lower PV: Size x 5
    assert campaign_rules.aces_omni_cost(40, 45, 3) == 200  # higher PV: difference x 40
    assert campaign_rules.aces_omni_cost(40, 41, 1) == 40


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("BattleMech", "BM"),
        ("Battle Armor", "BA"),
        ("Combat Vehicle", "CV"),
        ("Conventional Infantry", "CI"),
        ("ProtoMech", None),
        ("Aerospace Fighter", None),
        (None, None),
    ],
)
def test_unit_categories(name, category):
    assert campaign_rules.aces_unit_category(name) == category


def test_sale_value_is_pv_times_twenty():
    assert campaign_rules.sale_value(40) == 800
    assert campaign_rules.sale_value(28) == 560


# --- creation flow -------------------------------------------------------------------------


def _assign_all(force_id, point_value, *, type_name="BattleMech", skip=0, count=None):
    """Give every (or the first ``count``) force miniature an Alpha Strike assignment."""
    force = force_service.get_force_by_id(force_id)
    fm_ids = [fm.id for lance in force.lances for fm in lance.miniatures]
    if count is not None:
        fm_ids = fm_ids[:count]
    with session_scope() as session:
        for index, fm_id in enumerate(fm_ids[skip:]):
            raw = {
                "Id": 1000 + index,
                "Name": f"Unit {index}",
                "Class": "Test",
                "Variant": "T-1",
                "Tonnage": 70,
                "BFPointValue": point_value,
                "Type": {"Id": 18, "Name": type_name},
            }
            session.add(
                AlphaStrikeAssignment(
                    force_miniature_id=fm_id,
                    mul_unit_id=raw["Id"],
                    variant="T-1",
                    class_name="Test",
                    tonnage=70,
                    point_value=point_value,
                    unit_type_id=18,
                    unit_type_name=type_name,
                    display_name=raw["Name"],
                    mul_snapshot_json=json.dumps(raw),
                )
            )


def _create_aces(force_id, **kwargs):
    kwargs.setdefault("starting_bt_year", 3151)
    kwargs.setdefault("starting_bt_month", 1)
    return campaign_service.create_aces_campaign(force_id, "Aces New", **kwargs)


def _opening_tx(campaign_id):
    txs = campaign_service.get_campaign_by_id(campaign_id).transactions
    return [t for t in txs if t.transaction_type == "opening_balance"]


def test_new_force_opening_warchest_is_unused_pv_times_forty(client, realistic_force):
    _assign_all(realistic_force, 24)  # 16 units x 24 = 384 PV
    campaign = _create_aces(realistic_force, difficulty="veteran")
    assert campaign.ruleset == "aces"
    assert campaign.difficulty == "Veteran"
    assert campaign.experienced_force_sp == 0
    assert campaign.warchest_balance == (400 - 384) * 40
    [opening] = _opening_tx(campaign.id)
    assert opening.actual_amount == 640
    assert "16 unused PV" in opening.description


def test_example_395_pv_force_gets_200_sp(client, realistic_force):
    _assign_all(realistic_force, 26)  # 16 units
    with session_scope() as session:
        rows = session.query(AlphaStrikeAssignment).order_by(AlphaStrikeAssignment.id).all()
        rows[-1].point_value = 5  # 15 x 26 + 5 = 395 PV, 5 unused
    campaign = _create_aces(realistic_force)
    assert campaign.warchest_balance == 200


def test_new_force_limits_enforced(client, realistic_force, minimal_force):
    _assign_all(realistic_force, 26)  # 416 PV
    with pytest.raises(ValueError, match="at most 400 PV"):
        _create_aces(realistic_force)
    _assign_all(minimal_force, 30)
    with pytest.raises(ValueError, match="at least 8"):
        _create_aces(minimal_force)
    assert campaign_service.get_all_campaigns() == []


def test_missing_point_value_blocks_creation(client, realistic_force):
    _assign_all(realistic_force, 20, skip=1)  # first miniature has no assignment
    with pytest.raises(ValueError, match="Point Value for every unit"):
        _create_aces(realistic_force)
    with session_scope() as session:  # a 0 PV is also not authoritative
        session.query(AlphaStrikeAssignment).first().point_value = 0
    with pytest.raises(ValueError, match="Point Value"):
        _create_aces(realistic_force)


def test_unsupported_unit_type_rejected(client, realistic_force):
    _assign_all(realistic_force, 20, type_name="ProtoMech")
    with pytest.raises(ValueError, match="Aces supports"):
        _create_aces(realistic_force)


def test_supported_unit_categories_accepted(client, realistic_force):
    _assign_all(realistic_force, 20, type_name="Combat Vehicle")
    assert _create_aces(realistic_force).ruleset == "aces"


def test_experienced_force_is_not_capped_and_modifier_is_fixed(client, realistic_force):
    _assign_all(realistic_force, 30)  # 480 PV, more than a new force may have
    campaign = _create_aces(
        realistic_force, difficulty="Elite", existing_pilot_sp=7000, opening_warchest=1234
    )
    assert campaign.experienced_force_sp == 7000
    assert campaign.warchest_balance == 1234
    allowance = campaign_service.aces_sortie_pv_allowance(campaign.id)
    assert allowance["experienced_percent"] == -20
    assert allowance["difficulty_percent"] == -20
    assert allowance["allowed_pv"] == 480 * 60 // 100
    # Default Warchest for a reused force is 0, not the Chaos 3000 or unused-PV rule.
    other = campaign_service.create_aces_campaign(
        realistic_force, "Second", existing_pilot_sp=100, starting_bt_year=3151, starting_bt_month=1
    )
    assert other.warchest_balance == 0


def test_difficulty_validated_and_defaults_to_standard(client, realistic_force):
    _assign_all(realistic_force, 20)
    with pytest.raises(ValueError, match="Difficulty must be one of"):
        _create_aces(realistic_force, difficulty="Impossible")
    assert _create_aces(realistic_force, difficulty="").difficulty == "Standard"


def test_create_route_uses_aces_flow(client, realistic_force):
    _assign_all(realistic_force, 24)
    resp = client.post(
        "/campaigns/create",
        data={
            "name": "Route Aces",
            "force_id": str(realistic_force),
            "ruleset": "aces",
            "difficulty": "Elite",
            "starting_bt_year": "3151",
            "starting_bt_month": "1",
            "existing_pilot_sp": "0",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"640 SP opening Warchest" in resp.data
    assert b"Max Sortie PV" in resp.data
    assert b"Advance Month" not in resp.data


def test_create_route_rejects_oversized_new_force(client, realistic_force):
    _assign_all(realistic_force, 26)
    resp = client.post(
        "/campaigns/create",
        data={
            "name": "Too Big",
            "force_id": str(realistic_force),
            "ruleset": "aces",
            "starting_bt_year": "3151",
            "starting_bt_month": "1",
        },
        follow_redirects=True,
    )
    assert b"at most 400 PV" in resp.data
    assert campaign_service.get_all_campaigns() == []


def test_chaos_create_and_detail_unchanged(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    assert campaign.experienced_force_sp == 0
    detail = client.get(f"/campaigns/{campaign.id}")
    assert b"Advance Month" in detail.data
    assert b"Max Sortie PV" not in detail.data


# --- Sortie PV validation ------------------------------------------------------------------


def _aces(force_id, **kwargs):
    campaign = campaign_service.create_campaign_from_force(
        force_id,
        "Aces PV",
        ruleset="aces",
        opening_warchest=kwargs.pop("warchest", 5000),
        starting_bt_year=3151,
        starting_bt_month=1,
        **kwargs,
    )
    with session_scope() as session:
        for unit in session.query(CampaignUnit).filter_by(campaign_id=campaign.id):
            unit.point_value = 40
            unit.tonnage = 70
            unit.unit_type_name = "BattleMech"
    pilots = [
        aces_pilot_service.create_aces_pilot(
            campaign.id, name, "BM", skill_sp=150, edge_sp=0, ability_sp=0
        )
        for name in ("Hawk", "Ghost")
    ]
    return campaign_service.get_campaign_by_id(campaign.id), pilots


def _sortie(campaign, pilots, unit_indices):
    sortie = campaign_service.create_aces_sortie(campaign.id, "PV test")
    rows = [
        contract_service.add_unit_to_sortie(sortie.id, campaign.units[i].id) for i in unit_indices
    ]
    contract_service.assign_sortie_pilot(rows[0].id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    return sortie, rows


def test_standard_difficulty_allows_the_whole_force(client, minimal_force):
    campaign, pilots = _aces(minimal_force)
    sortie, _ = _sortie(campaign, pilots, [0, 1])
    assert contract_service.mark_sortie_ready(sortie.id).status == "ready"


def test_difficulty_reduces_allowed_sortie_pv(client, minimal_force):
    campaign, pilots = _aces(minimal_force, difficulty="Legendary")  # -30% of 80 = 56
    sortie, _ = _sortie(campaign, pilots, [0, 1])
    with pytest.raises(ValueError, match="allows 56 PV"):
        contract_service.mark_sortie_ready(sortie.id)
    contract_service.remove_sortie_unit(contract_service.get_sortie_by_id(sortie.id).units[1].id)
    assert contract_service.mark_sortie_ready(sortie.id).status == "ready"


def test_experienced_modifier_stacks_with_difficulty(client, minimal_force):
    campaign, pilots = _aces(minimal_force, difficulty="Veteran", experienced_force_sp=7000)
    allowance = campaign_service.aces_sortie_pv_allowance(campaign.id)
    assert allowance["allowed_pv"] == 56  # 80 x (100 - 10 - 20)%
    sortie, _ = _sortie(campaign, pilots, [0, 1])
    with pytest.raises(ValueError, match="experienced force -20%"):
        contract_service.mark_sortie_ready(sortie.id)


def test_rookie_never_allows_more_than_the_force(client, minimal_force):
    campaign, pilots = _aces(minimal_force, difficulty="Rookie")
    assert campaign_service.aces_sortie_pv_allowance(campaign.id)["allowed_pv"] == 96
    sortie, _ = _sortie(campaign, pilots, [0, 1])
    assert contract_service.mark_sortie_ready(sortie.id).status == "ready"


def test_allowance_counts_only_available_units(client, minimal_force):
    campaign, pilots = _aces(minimal_force, difficulty="Veteran")
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[1].id).condition = "truly-destroyed"
        session.get(CampaignUnit, campaign.units[1].id).available = False
    allowance = campaign_service.aces_sortie_pv_allowance(campaign.id)
    assert allowance["force_pv"] == 40
    assert allowance["allowed_pv"] == 36


def test_sortie_page_shows_allowance_not_scale(client, minimal_force):
    campaign, pilots = _aces(minimal_force, difficulty="Veteran")
    sortie, _ = _sortie(campaign, pilots, [0])
    page = client.get(f"/sorties/{sortie.id}")
    assert b"/ 72 PV" in page.data


# --- Omni reconfiguration ------------------------------------------------------------------

NEW_CONFIG = {
    "Id": 9001,
    "Name": "Timber Wolf B",
    "Class": "Timber Wolf",
    "Variant": "B",
    "Tonnage": 75,
    "BFPointValue": 36,
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _omni_campaign(force_id, **kwargs):
    campaign, pilots = _aces(force_id, **kwargs)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[0].id)
        unit.is_omni = True
        unit.variant = "Prime"
        unit.mul_unit_id = 9000
        session.get(Campaign, campaign.id).mul_faction_id = 29
        session.get(Campaign, campaign.id).mul_era_id = 14
    campaign = campaign_service.get_campaign_by_id(campaign.id)
    sortie = campaign_service.create_aces_sortie(campaign.id, "Omni prep")
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    return campaign, pilots, sortie, row


def _reconfigure(row_id, raw):
    with patch("app.services.aces_sortie_service.mul_service.find_unit_in_search_results") as f:
        f.return_value = raw
        return contract_service.apply_omni_from_search(row_id, raw["Id"])


def test_omni_lower_pv_costs_size_times_five(client, minimal_force):
    campaign, _, sortie, row = _omni_campaign(minimal_force)
    updated = _reconfigure(row.id, NEW_CONFIG)  # 40 -> 36 PV, 70t BattleMech = Size 3
    assert updated.configuration_changed is True
    assert updated.reconfiguration_cost == 15
    assert updated.variant == "B"
    assert updated.point_value == 36

    reloaded = campaign_service.get_campaign_by_id(campaign.id)
    assert reloaded.units[0].variant == "B"
    assert reloaded.units[0].point_value == 36
    assert reloaded.warchest_balance == 5000 - 15
    [tx] = [t for t in reloaded.transactions if t.transaction_type == "omni_reconfigure"]
    assert tx.actual_amount == -15


def test_omni_higher_pv_costs_pv_difference_times_forty(client, minimal_force):
    campaign, _, sortie, row = _omni_campaign(minimal_force)
    updated = _reconfigure(row.id, {**NEW_CONFIG, "BFPointValue": 45})
    assert updated.reconfiguration_cost == 200
    assert campaign_service.get_campaign_by_id(campaign.id).warchest_balance == 5000 - 200


def test_omni_history_preserved_and_second_change_accumulates(client, minimal_force):
    campaign, _, sortie, row = _omni_campaign(minimal_force)
    _reconfigure(row.id, NEW_CONFIG)
    again = _reconfigure(row.id, {**NEW_CONFIG, "Id": 9002, "Variant": "C", "BFPointValue": 36})
    assert again.reconfiguration_cost == 15 + 15
    with session_scope() as session:
        events = session.query(UnitConfigurationEvent).order_by(UnitConfigurationEvent.id).all()
        assert [(e.previous_variant, e.new_variant, e.cost) for e in events] == [
            ("Prime", "B", 15),
            ("B", "C", 15),
        ]


def test_omni_restrictions(client, minimal_force):
    campaign, pilots, sortie, row = _omni_campaign(minimal_force)
    with pytest.raises(ValueError, match="already in that configuration"):
        _reconfigure(row.id, {**NEW_CONFIG, "Id": 9000})
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[0].id).is_omni = False
    with pytest.raises(ValueError, match="Omni-capable"):
        _reconfigure(row.id, NEW_CONFIG)

    # Locked once the Sortie is Ready.
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[0].id).is_omni = True
    contract_service.assign_sortie_pilot(row.id, pilots[0].id)
    aces_sortie_service.set_force_commander(sortie.id, pilots[0].id)
    contract_service.mark_sortie_ready(sortie.id)
    with pytest.raises(ValueError, match="Planning"):
        _reconfigure(row.id, NEW_CONFIG)


def test_omni_blocked_when_warchest_cannot_pay(client, minimal_force):
    campaign, _, sortie, row = _omni_campaign(minimal_force, warchest=10)
    with pytest.raises(ValueError, match="Insufficient Warchest"):
        _reconfigure(row.id, NEW_CONFIG)
    assert campaign_service.get_campaign_by_id(campaign.id).units[0].variant == "Prime"


def test_aces_campaign_page_has_no_manual_omni_form_and_route_is_blocked(client, minimal_force):
    campaign, _, sortie, row = _omni_campaign(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}")
    assert b"Reconfigure Omni" not in page.data
    blocked = client.post(
        f"/campaigns/units/{campaign.units[0].id}/omni",
        data={"campaign_id": str(campaign.id), "mul_unit_id": "9001", "cost": "0"},
        follow_redirects=True,
    )
    assert b"made while preparing a Sortie" in blocked.data
    sortie_page = client.get(f"/sorties/{sortie.id}")
    assert b"Change configuration" in sortie_page.data


# --- purchases and sales -------------------------------------------------------------------


def test_sale_pays_pv_times_twenty_and_retires_unit(client, minimal_force):
    campaign, _ = _aces(minimal_force)
    unit = campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)
    assert unit.condition == "retired"
    assert unit.available is False
    reloaded = campaign_service.get_campaign_by_id(campaign.id)
    assert reloaded.warchest_balance == 5000 + 800
    assert len(reloaded.units) == 2  # kept in history, not deleted
    [tx] = [t for t in reloaded.transactions if t.transaction_type == "unit_sale"]
    assert (tx.actual_amount, tx.related_entity_id) == (800, unit.id)
    with pytest.raises(ValueError, match="active, fully repaired"):
        campaign_service.sell_campaign_unit(campaign.id, unit.id)  # already sold
    summary = campaign_service.get_aces_force_summary(campaign.id)
    assert summary["active_unit_count"] == 1


def test_only_repaired_unplanned_units_can_be_sold(client, minimal_force):
    campaign, pilots = _aces(minimal_force)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[1].id)
        unit.condition = "damaged"
        unit.damage_category = "structure"
        unit.available = False
    with pytest.raises(ValueError, match="active, fully repaired"):
        campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)
    sortie, _ = _sortie(campaign, pilots, [0])
    with pytest.raises(ValueError, match="not been resolved"):
        campaign_service.sell_campaign_unit(campaign.id, campaign.units[0].id)


def test_chaos_cannot_sell(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with pytest.raises(ValueError, match="only available for aces"):
        campaign_service.sell_campaign_unit(chaos.id, chaos.units[0].id)


def test_purchase_and_sale_roll_into_the_open_sortie_report(client, minimal_force):
    campaign, pilots = _aces(minimal_force, warchest=2000)
    with session_scope() as session:
        session.get(Campaign, campaign.id).mul_faction_id = 29
        session.get(Campaign, campaign.id).mul_era_id = 14
    sortie, _ = _sortie(campaign, pilots, [0])
    contract_service.mark_sortie_ready(sortie.id)
    contract_service.mark_sortie_fought(sortie.id)
    apply_aces(sortie.id, primary_objective_sp=500, max_pilot_sp=0)

    bought = {
        "Id": 7563,
        "Name": "Warhammer WHM-8R",
        "Class": "Warhammer",
        "Variant": "WHM-8R",
        "Tonnage": 70,
        "BFPointValue": 30,
        "Type": {"Id": 18, "Name": "BattleMech"},
    }
    with patch("app.services.campaign_service.mul_service.find_unit_in_search_results") as find:
        find.return_value = bought
        purchased = campaign_service.purchase_campaign_unit(
            campaign.id, 7563, search_name="Warhammer"
        )
    assert purchased.miniature_id is None  # no physical Miniature is created
    sold = campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)

    with session_scope() as session:
        report = session.query(AcesSortieReport).filter_by(sortie_id=sortie.id).one()
        assert (report.purchases_total, report.sales_total) == (1200, 800)
        session.expunge(report)

    for item in svc.pending_shares(sortie.id):
        svc.allocate_pilot_share(
            sortie.id,
            item["share"].campaign_pilot_id,
            skill_sp=item["total"],
            edge_sp=0,
            ability_sp=0,
        )
    svc.finalize_aces_sortie(sortie.id, "next")
    final = svc.get_sortie_report(sortie.id)["report"]
    balance = campaign_service.get_campaign_by_id(campaign.id).warchest_balance
    assert final.warchest_after == balance
    assert (final.purchases_total, final.sales_total) == (1200, 800)
    assert sold.id and purchased.id != sold.id

    # Once finalized, later trades no longer touch the frozen report.
    with patch("app.services.campaign_service.mul_service.find_unit_in_search_results") as find:
        find.return_value = bought
        campaign_service.purchase_campaign_unit(campaign.id, 7563, search_name="Warhammer")
    again = svc.get_sortie_report(sortie.id)["report"]
    assert again.purchases_total == 1200


def test_sell_route_and_report_page_shows_trades(client, minimal_force):
    campaign, _ = _aces(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}")
    assert b"Sell (800 SP)" in page.data
    resp = client.post(
        f"/campaigns/{campaign.id}/units/{campaign.units[1].id}/sell", follow_redirects=True
    )
    assert b"Sold" in resp.data
    assert campaign_service.get_campaign_by_id(campaign.id).warchest_balance == 5800


# --- campaign summary ----------------------------------------------------------------------


def test_aces_summary_shows_difficulty_and_hides_chaos_controls(client, minimal_force):
    campaign, _ = _aces(minimal_force, difficulty="Veteran", experienced_force_sp=4000)
    page = client.get(f"/campaigns/{campaign.id}")
    assert b"Veteran" in page.data
    assert b"-20% PV" not in page.data  # difficulty alone shows -10
    assert b"Experienced force (4000 SP)" in page.data
    assert b"Max Sortie PV" in page.data
    assert b"Advance Month" not in page.data
    assert b"Contracts" not in page.data
    redirect = client.get(f"/campaigns/{campaign.id}/advance-month", follow_redirects=True)
    assert b"no monthly pay" in redirect.data


def test_recent_sorties_limited_on_summary(client, minimal_force):
    campaign, pilots = _aces(minimal_force)
    from tests.conftest import finish_aces, prepare_aces_ready

    for index in range(7):
        sortie = campaign_service.create_aces_sortie(campaign.id, f"S{index}")
        contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
        prepare_aces_ready(campaign.id, sortie.id)
        contract_service.mark_sortie_ready(sortie.id)
        contract_service.mark_sortie_fought(sortie.id)
        finish_aces(sortie.id, primary_objective_sp=100)
    page = client.get(f"/campaigns/{campaign.id}")
    assert b"S6" in page.data and b"S2" in page.data
    assert b"S1<" not in page.data and b"S0<" not in page.data
    history = client.get(f"/campaigns/{campaign.id}/sortie-history")
    assert b"S0" in history.data and b"S6" in history.data
