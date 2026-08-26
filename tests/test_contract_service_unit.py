"""Unit tests for contract_service.py (Prompt 2: Contracts and Sorties)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.extensions import session_scope
from app.models.campaign_unit import CampaignUnit
from app.services import campaign_service, contract_service
from tests.conftest import validate_expunged_object

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


def _campaign(force_id: int, name: str = "Reach"):
    return campaign_service.create_campaign_from_force(
        force_id,
        name,
        current_location="Galatea",
        opening_warchest=200,
        starting_bt_year=3151,
        starting_bt_month=1,
    )


def _ensure_units_as_ready(campaign, *, tonnage: int = 70, point_value: int = 40):
    with session_scope() as session:
        units = list(
            session.execute(
                select(CampaignUnit).where(CampaignUnit.campaign_id == campaign.id)
            ).scalars()
        )
        for unit in units:
            if unit.point_value is None:
                unit.point_value = point_value
            if unit.tonnage is None:
                unit.tonnage = tonnage
    return campaign_service.get_campaign_by_id(campaign.id)


def _commit_roster(contract, campaign, unit_ids: list[int] | None = None):
    ids = unit_ids if unit_ids is not None else [unit.id for unit in campaign.units]
    for unit_id in ids:
        try:
            contract_service.add_unit_to_contract_roster(contract.id, unit_id)
        except ValueError:
            pass


def _active_contract(campaign, *, roster_unit_ids: list[int] | None = None, **kwargs):
    campaign = _ensure_units_as_ready(campaign)
    contract = contract_service.create_contract(campaign.id, "Garrison", **kwargs)
    _commit_roster(contract, campaign, roster_unit_ids)
    return contract_service.activate_contract(contract.id)


def test_create_contract_history_and_number(client, minimal_force):
    """Contracts are stored on the campaign with auto numbers C-001, C-002."""
    # Arrange
    campaign = _campaign(minimal_force)

    # Act
    first = contract_service.create_contract(campaign.id, "First Job", employer="Lyran")
    second = contract_service.create_contract(campaign.id, "Second Job")

    # Assert
    assert first.contract_number == "C-001"
    assert second.contract_number == "C-002"
    assert first.status == "draft"
    assert first.start_campaign_month == campaign.current_campaign_month
    assert first.end_campaign_month == first.start_campaign_month
    history = contract_service.get_contracts_for_campaign(campaign.id)
    assert [row.contract_number for row in history] == ["C-002", "C-001"]
    validate_expunged_object(first, "id", "name", "sorties")


def test_end_month_from_length(client, minimal_force):
    """End month defaults to start + length - 1 and remains editable."""
    # Arrange
    campaign = _campaign(minimal_force)

    # Act
    contract = contract_service.create_contract(
        campaign.id, "Long", length_months=3, start_campaign_month=2
    )
    updated = contract_service.update_contract(contract.id, end_campaign_month=6)

    # Assert
    assert contract.end_campaign_month == 4
    assert updated.end_campaign_month == 6


def test_one_active_contract(client, minimal_force):
    """Only one contract may be active on a campaign."""
    # Arrange
    campaign = _campaign(minimal_force)
    first = contract_service.create_contract(campaign.id, "Alpha")
    second = contract_service.create_contract(campaign.id, "Beta")
    contract_service.activate_contract(first.id)

    # Act & Assert
    with pytest.raises(ValueError, match="already active"):
        contract_service.activate_contract(second.id)
    assert contract_service.get_active_contract(campaign.id).id == first.id

    # Act
    contract_service.complete_contract(first.id)
    activated = contract_service.activate_contract(second.id)

    # Assert
    assert activated.status == "active"
    assert contract_service.get_contract_by_id(first.id).status == "completed"


def test_empty_roster_may_activate(client, minimal_force):
    """A Contract with an empty roster may still be activated."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = contract_service.create_contract(campaign.id, "Empty")

    # Act
    activated = contract_service.activate_contract(contract.id)

    # Assert
    assert activated.status == "active"
    assert activated.roster_units == []


def test_cancel_contract_records_penalty(client, minimal_force):
    """Cancelling posts a player-entered SP penalty to the ledger."""
    # Arrange
    campaign = _campaign(minimal_force, "Penalty")
    contract = _active_contract(campaign)

    # Act
    contract_service.cancel_contract(contract.id, penalty_wp=25, reputation_delta=-1)
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert loaded.warchest_balance == 175
    assert loaded.reputation == 0
    assert loaded.transactions[-1].transaction_type == "contract_cancel"
    assert contract_service.get_contract_by_id(contract.id).status == "cancelled"


def test_sortie_requires_active_contract(client, minimal_force):
    """Sorties cannot be created without an active contract."""
    # Arrange
    campaign = _campaign(minimal_force)
    draft = contract_service.create_contract(campaign.id, "Draft")

    # Act & Assert
    with pytest.raises(ValueError, match="active contract"):
        contract_service.create_sortie(draft.id, "Ambush")


def test_sortie_scale_cannot_exceed_contract(client, minimal_force):
    """Sortie Scale is independent but cannot exceed Contract Scale."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(campaign, scale=2)

    # Act
    sortie = contract_service.create_sortie(contract.id, "Probe", scale=2)

    # Assert
    assert sortie.scale == 2
    with pytest.raises(ValueError, match="cannot exceed"):
        contract_service.create_sortie(contract.id, "Too big", scale=3)
    with pytest.raises(ValueError, match="cannot exceed"):
        contract_service.update_sortie(sortie.id, scale=3)


def test_transportation_employer_payment_vs_actual_expense(client, minimal_force):
    """Employer payment is % of standard amount; excess vs actual expense is kept."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(
        campaign, transportation_percent=50, destination="Hartford", scale=1
    )

    # Act — standard 300, employer 150, actual expense 100 → net +50
    event = campaign_service.create_travel_event(
        campaign.id,
        "Galatea",
        "Hartford",
        transport_mode="standard",
        actual_expense=100,
        contract_id=contract.id,
    )
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert event.gross_cost == 300
    assert event.covered_amount == 150
    assert event.actual_expense == 100
    assert event.actual_warchest_impact == 50
    assert loaded.warchest_balance == 250


def test_base_pay_allows_110_percent(client, minimal_force):
    """Base Pay may exceed 100%, including 110%."""
    # Arrange
    campaign = _campaign(minimal_force)

    # Act
    contract = contract_service.create_contract(campaign.id, "Fat", base_pay_percent=110)

    # Assert
    assert contract.base_pay_percent == 110
    with pytest.raises(ValueError, match="Base Pay"):
        contract_service.create_contract(campaign.id, "Too fat", base_pay_percent=201)


def test_contract_roster_selection_and_sortie_eligibility(client, minimal_force):
    """Sorties may only use units committed to the Contract roster."""
    # Arrange
    campaign = _ensure_units_as_ready(_campaign(minimal_force))
    contract = contract_service.create_contract(campaign.id, "Roster")
    contract_service.add_unit_to_contract_roster(contract.id, campaign.units[0].id)
    contract = contract_service.activate_contract(contract.id)
    sortie = contract_service.create_sortie(contract.id, "Fight")

    # Act
    eligible = contract_service.eligible_campaign_units(campaign.id, contract_id=contract.id)

    # Assert
    assert {unit.id for unit in eligible} == {campaign.units[0].id}
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    with pytest.raises(ValueError, match="not committed"):
        contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)


def test_contract_scale_pv_and_unit_limits(client, minimal_force):
    """Contract roster additions are hard-blocked at Scale PV/unit limits."""
    # Arrange
    campaign = _ensure_units_as_ready(_campaign(minimal_force), point_value=80)
    contract = contract_service.create_contract(campaign.id, "Tight", scale=1)
    contract_service.add_unit_to_contract_roster(contract.id, campaign.units[0].id)

    # Act / Assert — Scale 1 = 150 PV / 3 units; second 80 PV unit → 160 > 150
    with pytest.raises(ValueError, match="150 PV"):
        contract_service.add_unit_to_contract_roster(contract.id, campaign.units[1].id)


def test_add_lance_to_roster_skips_already_on_roster(client, minimal_force):
    """Adding a lance skips units already on the Contract roster."""
    # Arrange
    campaign = _ensure_units_as_ready(_campaign(minimal_force))
    contract = contract_service.create_contract(campaign.id, "Lance")
    contract_service.add_unit_to_contract_roster(contract.id, campaign.units[0].id)

    # Act
    added = contract_service.add_lance_to_contract_roster(contract.id, campaign.lances[0].id)

    # Assert
    assert len(added) == 1
    assert added[0].campaign_unit_id == campaign.units[1].id


def test_add_lance_to_roster_empty_eligible_raises(client, minimal_force):
    """Adding a lance when every unit is already on the roster raises."""
    # Arrange
    campaign = _ensure_units_as_ready(_campaign(minimal_force))
    contract = contract_service.create_contract(campaign.id, "Full")
    for unit in campaign.units:
        contract_service.add_unit_to_contract_roster(contract.id, unit.id)

    # Act / Assert
    with pytest.raises(ValueError, match="already on the Contract roster"):
        contract_service.add_lance_to_contract_roster(contract.id, campaign.lances[0].id)


def test_eligible_unit_filtering(client, minimal_force):
    """Destroyed or unavailable units cannot join a Sortie."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(campaign)
    downed = campaign.units[0]
    campaign_service.update_campaign_unit(downed.id, condition="destroyed")

    # Act
    eligible = contract_service.eligible_campaign_units(campaign.id, contract_id=contract.id)
    sortie = contract_service.create_sortie(contract.id, "Fight")

    # Assert
    assert downed.id not in {unit.id for unit in eligible}
    with pytest.raises(ValueError, match="not currently available"):
        contract_service.add_unit_to_sortie(sortie.id, downed.id)


def test_add_lance_skips_unavailable(client, minimal_force):
    """Adding a lance adds available roster units only."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(campaign)
    campaign_service.update_campaign_unit(campaign.units[0].id, condition="truly-destroyed")
    sortie = contract_service.create_sortie(contract.id, "Lance drop")

    # Act
    added = contract_service.add_lance_to_sortie(sortie.id, campaign.lances[0].id)
    loaded = contract_service.get_sortie_by_id(sortie.id)

    # Assert
    assert len(added) == 1
    assert len(loaded.units) == 1
    assert loaded.units[0].campaign_unit_id == campaign.units[1].id


def test_preferred_pilot_preselection_and_override(client, minimal_force):
    """Preferred pairing is suggested, then can be cleared or swapped."""
    # Arrange
    campaign = _campaign(minimal_force)
    unit = campaign.units[0]
    other = campaign.units[1]
    preferred = campaign_service.add_campaign_pilot(
        campaign.id, "Rayan", callsign="Razor", preferred_unit_id=unit.id
    )
    extra = campaign_service.add_campaign_pilot(campaign.id, "Dana")
    contract = _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, "Pairing")

    # Act
    row = contract_service.add_unit_to_sortie(sortie.id, unit.id)
    other_row = contract_service.add_unit_to_sortie(sortie.id, other.id)

    # Assert
    assert row.campaign_pilot_id == preferred.id
    assert row.is_generic_crew is False
    assert other_row.is_generic_crew is True
    assert other_row.alpha_strike_skill == 4

    # Act
    cleared = contract_service.assign_sortie_pilot(row.id, None)
    swapped = contract_service.assign_sortie_pilot(row.id, extra.id)

    # Assert
    assert cleared.is_generic_crew is True
    assert swapped.campaign_pilot_id == extra.id


def test_named_pilot_one_unit_per_sortie(client, minimal_force):
    """A named pilot may only crew one unit in the same Sortie."""
    # Arrange
    campaign = _campaign(minimal_force)
    pilot = campaign_service.add_campaign_pilot(campaign.id, "Rayan")
    contract = _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, "One seat")
    first = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    second = contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)
    contract_service.assign_sortie_pilot(first.id, pilot.id)

    # Act & Assert
    with pytest.raises(ValueError, match="one unit"):
        contract_service.assign_sortie_pilot(second.id, pilot.id)


def test_sortie_snapshot_survives_campaign_edits(client, minimal_force):
    """Later campaign unit changes do not rewrite a Sortie snapshot."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, "Snapshot")
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    original_variant = row.variant

    # Act
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[0].id)
        unit.variant = "CHANGED"
        unit.chassis = "Not The Original"
    loaded = contract_service.get_sortie_by_id(sortie.id)

    # Assert
    assert loaded.units[0].variant == original_variant
    assert loaded.units[0].chassis == row.chassis
    assert loaded.units[0].chassis != "Not The Original"


def test_omni_reconfig_at_sortie_prep_is_rejected(client, minimal_force):
    """Omni loadouts are changed between Sorties, not during Sortie prep."""
    # Arrange
    campaign = _campaign(minimal_force)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign.units[0].id)
        unit.is_omni = True
        unit.variant = "Prime"
        unit.mul_unit_id = 12
        unit.chassis = "Timber Wolf"
        unit.mul_snapshot_json = json.dumps(
            {
                "Id": 12,
                "Name": "Timber Wolf Prime",
                "Class": "Timber Wolf",
                "Variant": "Prime",
                "Tonnage": 75,
                "BFPointValue": 54,
                "Type": {"Id": 18, "Name": "BattleMech"},
            }
        )
    contract = _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, "Omni prep")
    row = contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)

    # Act / Assert
    with pytest.raises(ValueError, match="between-sortie"):
        contract_service.apply_sortie_unit_configuration(row.id, OMNI_ALT, cost=15)


def test_mark_ready_and_fought(client, minimal_force):
    """Planning → Ready → Fought; outcome is optional until Fought."""
    # Arrange
    campaign = _campaign(minimal_force)
    contract = _active_contract(campaign)
    sortie = contract_service.create_sortie(contract.id, "Battle")

    # Act & Assert
    with pytest.raises(ValueError, match="at least one unit"):
        contract_service.mark_sortie_ready(sortie.id)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    ready = contract_service.mark_sortie_ready(sortie.id)
    assert ready.status == "ready"
    with pytest.raises(ValueError, match="locked"):
        contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)
    fought = contract_service.mark_sortie_fought(sortie.id, outcome="victory")
    assert fought.status == "fought"
    assert fought.outcome == "victory"


def test_sortie_ready_rejects_over_limits(client, minimal_force):
    """Sortie cannot become Ready when over its PV or unit limits."""
    # Arrange — Scale 1 sortie PV limit = 100; two 60 PV units = 120
    campaign = _ensure_units_as_ready(_campaign(minimal_force), point_value=60)
    contract = contract_service.create_contract(campaign.id, "Limits", scale=1)
    for unit in campaign.units:
        contract_service.add_unit_to_contract_roster(contract.id, unit.id)
    contract = contract_service.activate_contract(contract.id)
    sortie = contract_service.create_sortie(contract.id, "Over", scale=1)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[1].id)

    # Act / Assert
    with pytest.raises(ValueError, match="PV"):
        contract_service.mark_sortie_ready(sortie.id)


def test_scale_limit_helpers(client):
    """Alpha Strike Contract/Sortie Scale formulas match Hot Spots progression."""
    assert contract_service.contract_pv_limit(2) == 300
    assert contract_service.contract_unit_limit(2) == 6
    assert contract_service.sortie_pv_limit(2) == 200
    assert contract_service.sortie_unit_limit(2) == 6
    assert contract_service.calculate_standard_transport("standard", scale=2) == 600
    assert contract_service.calculate_standard_transport("jump", scale=2, jump_count=3) == 400


def test_create_contract_and_sortie_routes(client, minimal_force):
    """HTTP routes create a contract, activate it, and open a Sortie."""
    # Arrange
    campaign = _campaign(minimal_force)

    # Act
    created = client.post(
        f"/campaigns/{campaign.id}/contracts",
        data={"name": "Route Job", "scale": "2", "length_months": "2"},
        follow_redirects=True,
    )
    contract = contract_service.get_contracts_for_campaign(campaign.id)[0]
    client.post(f"/contracts/{contract.id}/activate", follow_redirects=True)
    sortie_resp = client.post(
        f"/contracts/{contract.id}/sorties",
        data={"name": "First Track", "scale": "2"},
        follow_redirects=True,
    )

    # Assert
    assert created.status_code == 200
    assert b"Route Job" in created.data
    assert sortie_resp.status_code == 200
    assert b"First Track" in sortie_resp.data
    assert b"Track" in sortie_resp.data
