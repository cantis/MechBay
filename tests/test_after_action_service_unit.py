"""Unit tests for after_action_service.py (Prompt 3: After Action and between-sortie)."""

from __future__ import annotations

import json

import pytest

from app.extensions import session_scope
from app.models.campaign_unit import CampaignUnit
from app.services import after_action_service, campaign_service, contract_service
from tests.conftest import validate_expunged_object

OMNI_PRIME = {
    "Id": 12,
    "Name": "Timber Wolf Prime",
    "Class": "Timber Wolf",
    "Variant": "Prime",
    "Tonnage": 75,
    "BFPointValue": 54,
    "BFAbilities": "OMNI",
    "Type": {"Id": 18, "Name": "BattleMech"},
}
OMNI_ALT = {
    "Id": 13,
    "Name": "Timber Wolf A",
    "Class": "Timber Wolf",
    "Variant": "A",
    "Tonnage": 75,
    "BFPointValue": 48,
    "BFAbilities": "OMNI",
    "Type": {"Id": 18, "Name": "BattleMech"},
}
ENE_RAW = {
    "Id": 90,
    "Name": "Griffin GRF-1N",
    "Class": "Griffin",
    "Variant": "GRF-1N",
    "Tonnage": 55,
    "BFPointValue": 30,
    "BFAbilities": "ENE, IF1",
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _campaign(force_id: int, name: str = "Reach"):
    return campaign_service.create_campaign_from_force(
        force_id, name, current_location="Galatea", opening_warchest=200
    )


def _active_contract(campaign, **kwargs):
    contract = contract_service.create_contract(campaign.id, "Garrison", **kwargs)
    return contract_service.activate_contract(contract.id)


def _fought_sortie(campaign, *, name: str = "Fight", unit_ids: list[int] | None = None):
    contract = contract_service.get_active_contract(campaign.id) or _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, name)
    ids = unit_ids or [campaign.units[0].id]
    for unit_id in ids:
        contract_service.add_unit_to_sortie(sortie.id, unit_id)
    contract_service.mark_sortie_ready(sortie.id)
    return contract_service.mark_sortie_fought(sortie.id)


def _results(sortie, damage: str = "none", **kwargs):
    return [
        {
            "sortie_unit_id": row.id,
            "damage_outcome": damage,
            **kwargs,
        }
        for row in sortie.units
    ]


def test_after_action_damage_and_fielding(client, minimal_force):
    """Armour stays fieldable; structure is unavailable until repaired."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    armour = _fought_sortie(campaign, name="Armour", unit_ids=[campaign.units[0].id])
    structure = _fought_sortie(campaign, name="Structure", unit_ids=[campaign.units[1].id])

    # Act
    after_action_service.apply_after_action(armour.id, _results(armour, "armour"))
    after_action_service.apply_after_action(structure.id, _results(structure, "structure"))
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    by_id = {unit.id: unit for unit in loaded.units}

    # Assert
    assert by_id[campaign.units[0].id].condition == "damaged"
    assert by_id[campaign.units[0].id].available is True
    assert by_id[campaign.units[1].id].condition == "damaged"
    assert by_id[campaign.units[1].id].available is False
    assert contract_service.unit_is_available(by_id[campaign.units[0].id])
    assert not contract_service.unit_is_available(by_id[campaign.units[1].id])
    assert [event.damage_category for event in loaded.damage_events] == ["armour", "structure"]


def test_repair_orders_and_support_coverage(client, minimal_force):
    """AAR creates Repair Orders; completing them posts Support-covered WP."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign, support_percent=50)
    sortie = _fought_sortie(campaign)

    # Act
    after_action_service.apply_after_action(sortie.id, _results(sortie, "armour"), combat_pay=0)
    orders = after_action_service.get_repair_orders(campaign.id)
    order = next(row for row in orders if row.damage_category == "armour")
    after_action_service.update_repair_order(order.id, gross_cost=100)
    completed = after_action_service.complete_repair_order(order.id)
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    unit = next(row for row in loaded.units if row.id == campaign.units[0].id)

    # Assert
    assert order.status == "pending"
    assert order.gross_cost == 0
    assert completed.status == "completed"
    assert completed.covered_amount == 50
    assert completed.actual_cost == -50
    assert unit.condition == "active"
    assert unit.available is True
    repair_tx = next(tx for tx in loaded.transactions if tx.transaction_type == "repair")
    assert repair_tx.covered_amount == 50
    assert repair_tx.actual_amount == -50
    validate_expunged_object(completed, "id", "status", "gross_cost")


def test_truly_destroyed_cancels_repairs_and_blocks_fielding(client, minimal_force):
    """Destroyed hulls can be marked truly destroyed; the miniature stays."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    miniature_id = campaign.units[0].miniature_id
    sortie = _fought_sortie(campaign)
    after_action_service.apply_after_action(sortie.id, _results(sortie, "destroyed"))

    # Act
    unit = after_action_service.mark_unit_truly_destroyed(campaign.units[0].id)
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    orders = after_action_service.get_repair_orders(campaign.id)

    # Assert
    assert unit.condition == "truly-destroyed"
    assert unit.available is False
    assert unit.miniature_id == miniature_id
    assert all(order.status == "cancelled" for order in orders if order.status != "completed")
    with pytest.raises(ValueError, match="not currently available"):
        contract_service.add_unit_to_sortie(
            contract_service.create_sortie(
                contract_service.get_active_contract(campaign.id).id, "Later"
            ).id,
            unit.id,
        )
    assert any(event.damage_category == "truly-destroyed" for event in loaded.damage_events)


def test_pilot_wounds_skip_next_sortie_then_recover(client, minimal_force):
    """Wounded named pilots cannot be assigned, then recover after sitting one Fought Sortie out."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    pilot = campaign_service.add_campaign_pilot(
        campaign.id, "Dana", preferred_unit_id=campaign.units[0].id
    )
    first = _fought_sortie(campaign, name="First", unit_ids=[campaign.units[0].id])

    # Act
    after_action_service.apply_after_action(first.id, _results(first, "none", pilot_wounded=True))
    wounded = campaign_service.get_campaign_by_id(campaign.id).pilots[0]
    assert wounded.wounded is True
    with pytest.raises(ValueError, match="not available"):
        second = contract_service.create_sortie(
            contract_service.get_active_contract(campaign.id).id, "Second"
        )
        row = contract_service.add_unit_to_sortie(second.id, campaign.units[1].id)
        contract_service.assign_sortie_pilot(row.id, pilot.id)

    sit = contract_service.create_sortie(
        contract_service.get_active_contract(campaign.id).id, "Sit out"
    )
    contract_service.add_unit_to_sortie(sit.id, campaign.units[1].id)
    contract_service.mark_sortie_ready(sit.id)
    contract_service.mark_sortie_fought(sit.id)

    # Assert
    recovered = campaign_service.get_campaign_by_id(campaign.id).pilots[0]
    assert recovered.wounded is False
    assert recovered.status == "alive"
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    assert [event.event_type for event in loaded.injury_events] == ["wounded", "recovered"]


def test_dead_pilot_remains_in_history(client, minimal_force):
    """Killed named pilots stay on the campaign and cannot be assigned."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    campaign_service.add_campaign_pilot(campaign.id, "Dana", preferred_unit_id=campaign.units[0].id)
    sortie = _fought_sortie(campaign)

    # Act
    after_action_service.apply_after_action(sortie.id, _results(sortie, "none", pilot_killed=True))
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    pilot = loaded.pilots[0]

    # Assert
    assert pilot.status == "dead"
    assert pilot.wounded is False
    assert [event.event_type for event in loaded.injury_events] == ["died"]
    assert contract_service.eligible_named_pilots(campaign.id) == []


def test_omni_requires_repair_and_preserves_sortie_snapshot(client, minimal_force):
    """Omni reconfiguration is between-sortie, blocked while damaged, and keeps Sortie snapshots."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[0].id)
        unit.is_omni = True
        unit.variant = "Prime"
        unit.mul_unit_id = 12
        unit.mul_snapshot_json = json.dumps(OMNI_PRIME)
    sortie = _fought_sortie(campaign)
    after_action_service.apply_after_action(sortie.id, _results(sortie, "armour"))

    # Act / Assert
    with pytest.raises(ValueError, match="fully repaired"):
        after_action_service.reconfigure_omni_unit(campaign.units[0].id, OMNI_ALT, cost=15)
    with pytest.raises(ValueError, match="Only Omni"):
        after_action_service.reconfigure_omni_unit(campaign.units[1].id, OMNI_ALT)

    order = after_action_service.get_repair_orders(campaign.id)[0]
    after_action_service.complete_repair_order(order.id)
    updated = after_action_service.reconfigure_omni_unit(campaign.units[0].id, OMNI_ALT, cost=15)
    frozen = contract_service.get_sortie_by_id(sortie.id)
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    assert updated.variant == "A"
    assert frozen.units[0].variant == "Prime"
    assert loaded.warchest_balance == 165
    assert loaded.configuration_events[-1].previous_variant == "Prime"
    assert loaded.configuration_events[-1].new_variant == "A"


def test_rearm_posts_ledger_except_ene(client, minimal_force):
    """Every Sortie unit rearms at 20 WP except MUL ENE units."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign, support_percent=50)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[1].id)
        unit.mul_snapshot_json = json.dumps(ENE_RAW)
    sortie = _fought_sortie(campaign, unit_ids=[campaign.units[0].id, campaign.units[1].id])

    # Act
    after_action_service.apply_after_action(sortie.id, _results(sortie, "none"))
    loaded = campaign_service.get_campaign_by_id(campaign.id)
    rearm_txs = [tx for tx in loaded.transactions if tx.transaction_type == "rearm"]

    # Assert
    assert len(rearm_txs) == 1
    assert rearm_txs[0].gross_amount == -20
    assert rearm_txs[0].covered_amount == 10
    assert rearm_txs[0].actual_amount == -10
    assert loaded.warchest_balance == 190
    assert loaded.rearm_orders[0].campaign_unit_id == campaign.units[0].id


def test_explicit_month_advance_posts_typed_wp_and_arrives_travel(client, minimal_force):
    """Month advance is explicit, posts typed Base Pay/maintenance, and auto-arrives travel."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    campaign_service.create_travel_event(
        campaign.id,
        "Galatea",
        "Outreach",
        arrival_campaign_month=2,
        jump_count=2,
    )
    preview = after_action_service.preview_month_advance(campaign.id)

    # Act
    advanced = after_action_service.advance_campaign_month(campaign.id, base_pay=40, maintenance=15)
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert preview["new_month"] == 2
    assert preview["arriving"]
    assert advanced.current_campaign_month == 2
    assert loaded.current_location == "Outreach"
    assert loaded.travel_events[0].status == "arrived"
    types = [tx.transaction_type for tx in loaded.transactions]
    assert "base_pay" in types
    assert "maintenance" in types
    assert loaded.warchest_balance == 225


def test_multiple_sorties_same_month_and_close_does_not_advance(client, minimal_force):
    """Several Sorties can share a month; closing After Action does not advance it."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    first = _fought_sortie(campaign, name="One", unit_ids=[campaign.units[0].id])
    after_action_service.apply_after_action(first.id, _results(first, "none"))
    closed = after_action_service.close_sortie(first.id)
    second = _fought_sortie(campaign, name="Two", unit_ids=[campaign.units[1].id])

    # Act
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert closed.status == "closed"
    assert first.campaign_month == second.campaign_month == 1
    assert loaded.current_campaign_month == 1
    assert {sortie.name for sortie in loaded.sorties} == {"One", "Two"}


def test_after_action_route_and_combat_pay(client, minimal_force):
    """HTTP After Action records combat pay and notes without closing the Sortie."""
    # Arrange
    campaign = _campaign(minimal_force)
    _active_contract(campaign)
    sortie = _fought_sortie(campaign)
    row = sortie.units[0]

    # Act
    response = client.post(
        f"/sorties/{sortie.id}/after-action",
        data={
            f"damage_outcome_{row.id}": "crippled",
            "combat_pay": "25",
            "salvage_wp": "5",
            "objectives_summary": "Held the ridge",
            "after_action_notes": "Dust and fire",
            "outcome": "victory",
        },
        follow_redirects=True,
    )
    loaded = contract_service.get_sortie_by_id(sortie.id)
    campaign_loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert response.status_code == 200
    assert loaded.status == "after_action"
    assert loaded.outcome == "victory"
    assert loaded.combat_pay == 25
    assert loaded.after_action_notes == "Dust and fire"
    assert campaign_loaded.units[0].available is False
    assert campaign_loaded.warchest_balance == 210
