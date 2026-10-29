"""Unit tests for campaign_service.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.extensions import session_scope
from app.models.alpha_strike_assignment import AlphaStrikeAssignment
from app.models.alpha_strike_force import AlphaStrikeForce
from app.services import campaign_service, force_service, inventory_project_service
from app.services.campaign_service import (
    MiniatureInActiveCampaignError,
    campaign_month_label,
    location_display,
)
from app.services.miniature_service import delete_miniature, get_all_miniatures
from tests.conftest import validate_expunged_object

DEFAULT_START_YEAR = 3151
DEFAULT_START_MONTH = 1


def _create_campaign(force_id: int, name: str, **kwargs):
    kwargs.setdefault("starting_bt_year", DEFAULT_START_YEAR)
    kwargs.setdefault("starting_bt_month", DEFAULT_START_MONTH)
    return campaign_service.create_campaign_from_force(force_id, name, **kwargs)

WHM_RAW = {
    "Id": 7563,
    "Name": "Warhammer WHM-8R",
    "Class": "Warhammer",
    "Variant": "WHM-8R",
    "Tonnage": 70,
    "BFPointValue": 40,
    "BFAbilities": "IF, SRM",
    "Type": {"Id": 18, "Name": "BattleMech"},
}

OMNI_RAW = {
    "Id": 12,
    "Name": "Timber Wolf Prime",
    "Class": "Timber Wolf",
    "Variant": "Prime",
    "Tonnage": 75,
    "BFPointValue": 54,
    "BFAbilities": "OMNI, IF0",
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _enable_alpha_strike(force_id: int, point_budget: int | None) -> None:
    with session_scope() as session:
        session.add(
            AlphaStrikeForce(
                force_id=force_id,
                mul_faction_id=29,
                mul_era_id=14,
                faction_name="Clan Wolf",
                era_name="ilClan",
                point_budget=point_budget,
            )
        )


def _assign_variant(force_miniature_id: int, raw: dict, point_value: int | None = None) -> None:
    with session_scope() as session:
        session.add(
            AlphaStrikeAssignment(
                force_miniature_id=force_miniature_id,
                mul_unit_id=int(raw["Id"]),
                variant=raw["Variant"],
                class_name=raw["Class"],
                tonnage=int(raw["Tonnage"]),
                point_value=point_value if point_value is not None else int(raw["BFPointValue"]),
                unit_type_id=raw["Type"]["Id"],
                unit_type_name=raw["Type"]["Name"],
                display_name=raw["Name"],
                mul_snapshot_json=json.dumps(raw),
            )
        )


def _first_force_miniatures(force_id: int) -> list:
    force = force_service.get_force_by_id(force_id)
    return force.lances[0].miniatures


def test_create_campaign_from_force_snapshots_units(client, minimal_force):
    """Campaign creation copies force members and keeps lance grouping."""
    # Arrange
    force = force_service.get_force_by_id(minimal_force)

    # Act
    campaign = _create_campaign(
        minimal_force, "Reach Campaign", current_location="Galatea"
    )

    # Assert
    assert campaign.name == "Reach Campaign"
    assert campaign.is_active is True
    assert campaign.source_force_name == force.name
    assert campaign.current_location == "Galatea"
    assert campaign.reputation == 1
    assert campaign.scale == 1
    assert campaign.current_campaign_month == 1
    assert len(campaign.lances) == 1
    assert campaign.lances[0].name == "Alpha Lance"
    assert len(campaign.units) == 2
    validate_expunged_object(campaign, "id", "name", "lances", "units", "transactions")


def test_campaign_unit_snapshot_copies_assigned_variant(client, minimal_force):
    """Assigned MUL variants are copied; Omni is flagged from the snapshot."""
    # Arrange
    minis = _first_force_miniatures(minimal_force)
    _enable_alpha_strike(minimal_force, 200)
    _assign_variant(minis[0].id, WHM_RAW)
    _assign_variant(minis[1].id, OMNI_RAW)

    # Act
    campaign = _create_campaign(minimal_force, "Variant Campaign")

    # Assert
    by_chassis = {unit.chassis: unit for unit in campaign.units}
    warhammer = next(unit for unit in campaign.units if unit.variant == "WHM-8R")
    omni = next(unit for unit in campaign.units if unit.is_omni)
    assert warhammer.is_omni is False
    assert warhammer.mul_unit_id == 7563
    assert omni.variant == "Prime"
    assert omni.class_name == "Timber Wolf"
    assert by_chassis


def test_campaign_skips_variant_when_unconfigured(client, minimal_force):
    """Units without a MUL assignment omit variant instead of inventing one."""
    # Act
    campaign = _create_campaign(minimal_force, "No Variant")

    # Assert
    assert all(unit.variant is None for unit in campaign.units)
    assert all(unit.is_omni is False for unit in campaign.units)


def test_campaign_independent_of_source_force(client, minimal_force):
    """Deleting the source Force does not remove campaign roster history."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Independent")
    campaign_id = campaign.id

    # Act
    force_service.delete_force(minimal_force)
    loaded = campaign_service.get_campaign_by_id(campaign_id)

    # Assert
    assert loaded is not None
    assert loaded.source_force_name == "Jade Falcon Scout"
    assert len(loaded.units) == 2


def test_preferred_unit_is_convenience_only(client, minimal_force):
    """Preferred unit is stored but is not a permanent assignment."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Pilots")
    unit_id = campaign.units[0].id

    # Act
    pilot = campaign_service.add_campaign_pilot(
        campaign.id, "Rayan", callsign="Razor", preferred_unit_id=unit_id
    )
    campaign_service.update_campaign_pilot(pilot.id, preferred_unit_id=None)
    cleared = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert pilot.preferred_unit_id == unit_id
    assert cleared.pilots[0].preferred_unit_id is None
    assert cleared.units[0].id == unit_id


def test_preferred_unit_must_belong_to_same_campaign(client, multiple_forces):
    """A pilot cannot prefer a unit from another campaign."""
    # Arrange
    first = _create_campaign(
        multiple_forces["Jade Falcon Strikers"], "One"
    )
    second = _create_campaign(multiple_forces["Wolf Hunters"], "Two")

    # Act & Assert
    with pytest.raises(ValueError, match="Preferred unit"):
        campaign_service.add_campaign_pilot(
            second.id, "Visitor", preferred_unit_id=first.units[0].id
        )


def test_opening_warchest_defaults_to_3000_sp(client, minimal_force):
    """Default opening Warchest is 3,000 SP, not leftover force PV."""
    # Arrange
    minis = _first_force_miniatures(minimal_force)
    _enable_alpha_strike(minimal_force, 100)
    _assign_variant(minis[0].id, WHM_RAW, point_value=40)
    _assign_variant(minis[1].id, OMNI_RAW, point_value=54)

    # Act
    campaign = _create_campaign(minimal_force, "SP")

    # Assert
    assert campaign.warchest_balance == 3000
    assert campaign.transactions[0].transaction_type == "opening_balance"
    assert campaign.transactions[0].description == "Opening Warchest"
    assert campaign.transactions[0].actual_amount == 3000
    assert campaign.transactions[0].resulting_balance == 3000


def test_opening_warchest_default_without_budget(client, minimal_force):
    """Missing force budget still opens at the Hot Spots 3,000 SP default."""
    # Act
    campaign = _create_campaign(minimal_force, "No Budget")

    # Assert
    assert campaign.warchest_balance == 3000
    assert campaign.transactions[0].actual_amount == 3000


def test_opening_warchest_allows_negative_override(client, minimal_force):
    """Players may override to a negative opening Warchest."""
    # Act
    campaign = _create_campaign(minimal_force, "Over", opening_warchest=-44)

    # Assert
    assert campaign.warchest_balance == -44


def test_opening_warchest_override(client, minimal_force):
    """Players can override the computed opening balance."""
    # Act
    campaign = _create_campaign(
        minimal_force, "Override", opening_warchest=250
    )

    # Assert
    assert campaign.warchest_balance == 250


def test_named_pilot_defaults_gunnery_4_piloting_5(client, minimal_force):
    """Hot Spots named pilots default to Gunnery 4 / Piloting 5 / AS 4."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Pilots")

    # Act
    pilot = campaign_service.add_campaign_pilot(campaign.id, "Rayan")

    # Assert
    assert pilot.gunnery == 4
    assert pilot.piloting == 5
    assert pilot.alpha_strike_skill == 4
    assert pilot.wounds == 0
    assert pilot.wounded is False


def test_warchest_transaction_updates_cached_balance(client, minimal_force):
    """Ledger entries keep history and move the cached balance."""
    # Arrange
    campaign = _create_campaign(
        minimal_force, "Ledger", opening_warchest=100
    )

    # Act
    campaign_service.add_warchest_transaction(
        campaign.id,
        transaction_type="income",
        description="Bonus pay",
        actual_amount=25,
        gross_amount=25,
    )
    campaign_service.add_warchest_transaction(
        campaign.id,
        transaction_type="expense",
        description="Parts",
        actual_amount=-10,
        gross_amount=-10,
    )
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert loaded.warchest_balance == 115
    assert [tx.resulting_balance for tx in loaded.transactions] == [100, 125, 115]


def test_campaign_month_label_without_calendar(client, minimal_force):
    """Display stays on Campaign Month N when no BT calendar start is set."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Time")

    # Act
    campaign_service.update_campaign(
        campaign.id,
        current_campaign_month=4,
        starting_bt_year=None,
        starting_bt_month=None,
    )
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert loaded.current_campaign_month == 4
    assert campaign_month_label(loaded) == "Campaign Month 4"


def test_campaign_month_label_with_calendar(client, minimal_force):
    """Start month and year derive a BattleTech display date."""
    # Arrange
    campaign = _create_campaign(
        minimal_force,
        "Calendar",
        starting_bt_year=3152,
        starting_bt_month=7,
    )

    # Act
    campaign_service.update_campaign(campaign.id, current_campaign_month=4)
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert campaign_month_label(loaded) == "Campaign Month 4 — October 3152"
    assert campaign_month_label(loaded, 13) == "Campaign Month 13 — July 3153"


def test_travel_in_transit_then_updates_location(client, minimal_force):
    """Travel starts in transit, then arrival updates current location."""
    # Arrange
    campaign = _create_campaign(
        minimal_force, "Travel", current_location="Galatea", opening_warchest=100
    )

    # Act
    event = campaign_service.create_travel_event(
        campaign.id,
        "Galatea",
        "Hartford",
        transport_mode="manual",
        standard_amount=20,
        employer_payment=5,
        actual_expense=20,
        jump_count=3,
    )
    moving = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert event.status == "in_transit"
    assert event.transport_mode == "manual"
    assert event.gross_cost == 20
    assert event.covered_amount == 5
    assert event.actual_expense == 20
    assert event.actual_warchest_impact == -15
    assert moving.current_location == "Galatea"
    assert "In transit" in location_display(moving)
    assert moving.warchest_balance == 85

    # Act
    campaign_service.complete_travel_event(event.id)
    arrived = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert arrived.current_location == "Hartford"
    assert arrived.travel_events[0].status == "arrived"
    assert "In transit" not in location_display(arrived)


def test_travel_standard_mode_uses_scale(client, minimal_force):
    """Unlinked standard travel uses Campaign scale and 0 employer payment."""
    # Arrange
    campaign = _create_campaign(
        minimal_force, "StdTravel", current_location="Galatea", opening_warchest=1000, scale=2
    )

    # Act
    event = campaign_service.create_travel_event(
        campaign.id,
        "Galatea",
        "Outreach",
        transport_mode="standard",
    )
    loaded = campaign_service.get_campaign_by_id(campaign.id)

    # Assert
    assert event.gross_cost == 600
    assert event.covered_amount == 0
    assert event.actual_expense == 600
    assert event.actual_warchest_impact == -600
    assert loaded.warchest_balance == 400


def test_travel_jump_requires_jump_count(client, minimal_force):
    """Jump-tracked travel requires jump_count >= 1."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Jump", opening_warchest=1000)

    # Act / Assert
    with pytest.raises(ValueError, match="jump count"):
        campaign_service.create_travel_event(
            campaign.id, "A", "B", transport_mode="jump", jump_count=0
        )


def test_only_one_active_campaign(client, multiple_forces):
    """Creating or switching a campaign loads exactly one active campaign."""
    # Arrange
    first = _create_campaign(
        multiple_forces["Jade Falcon Strikers"], "First"
    )

    # Act
    second = _create_campaign(multiple_forces["Wolf Hunters"], "Second")
    campaigns = campaign_service.get_all_campaigns()

    # Assert
    assert second.is_active is True
    assert campaign_service.get_campaign_by_id(first.id).is_active is False
    assert sum(1 for item in campaigns if item.is_active) == 1

    # Act
    campaign_service.switch_campaign(first.id)

    # Assert
    assert campaign_service.get_active_campaign().id == first.id


def test_delete_miniature_blocked_in_active_campaign(client, minimal_force):
    """Loaded campaign units block deleting the physical miniature."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Block")
    miniature_id = campaign.units[0].miniature_id

    # Act & Assert
    with pytest.raises(MiniatureInActiveCampaignError):
        delete_miniature(miniature_id)
    assert get_all_miniatures()


def test_delete_miniature_from_inactive_campaign_warns(client, multiple_forces):
    """Miniatures on a non-loaded campaign can be deleted; opening warns."""
    # Arrange
    first = _create_campaign(
        multiple_forces["Jade Falcon Strikers"], "Loaded"
    )
    second = _create_campaign(multiple_forces["Wolf Hunters"], "Other")
    campaign_service.switch_campaign(first.id)
    miniature_id = second.units[0].miniature_id

    # Act
    delete_miniature(miniature_id)
    loaded = campaign_service.get_campaign_by_id(second.id)

    # Assert
    missing = campaign_service.missing_miniature_units(loaded)
    assert missing
    assert missing[0].miniature_missing is True
    assert missing[0].chassis


def test_new_inventory_clears_campaigns(client, minimal_force):
    """Resetting inventory invalidates campaigns along with forces."""
    # Arrange
    _create_campaign(minimal_force, "Gone")

    # Act
    inventory_project_service.new_inventory_project()

    # Assert
    assert campaign_service.get_all_campaigns() == []
    assert force_service.get_all_forces() == []


def test_create_campaign_requires_starting_calendar(client, minimal_force):
    """Creating a campaign requires a starting year and month."""
    # Act / Assert
    with pytest.raises(ValueError, match="Starting year is required"):
        campaign_service.create_campaign_from_force(
            minimal_force, "No Year", starting_bt_year=None, starting_bt_month=1
        )
    with pytest.raises(ValueError, match="Starting month is required"):
        campaign_service.create_campaign_from_force(
            minimal_force, "No Month", starting_bt_year=3151, starting_bt_month=None
        )


def test_create_campaign_route(client, minimal_force):
    """POST /campaigns/create snapshots the selected force."""
    # Act
    response = client.post(
        "/campaigns/create",
        data={
            "name": "From Route",
            "force_id": str(minimal_force),
            "scale": "2",
            "starting_bt_year": "3151",
            "starting_bt_month": "3",
        },
        follow_redirects=True,
    )

    # Assert
    assert response.status_code == 200
    assert b"From Route" in response.data
    campaigns = campaign_service.get_all_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].scale == 2
    assert campaigns[0].starting_bt_year == 3151
    assert campaigns[0].starting_bt_month == 3


def test_create_campaign_route_requires_calendar(client, minimal_force):
    """Create Campaign rejects a missing starting year or month."""
    # Act
    response = client.post(
        "/campaigns/create",
        data={"name": "No Calendar", "force_id": str(minimal_force), "scale": "1"},
        follow_redirects=True,
    )

    # Assert
    assert response.status_code == 200
    assert campaign_service.get_all_campaigns() == []
    assert b"Starting year and month are required" in response.data


def test_campaign_detail_can_load_campaign(client, multiple_forces):
    """A campaign opened from the list can be made the loaded campaign."""
    # Arrange
    first = _create_campaign(
        multiple_forces["Jade Falcon Strikers"], "First"
    )
    second = _create_campaign(multiple_forces["Wolf Hunters"], "Second")

    # Act
    response = client.get(f"/campaigns/{first.id}")
    body = response.get_data(as_text=True)

    # Assert
    assert response.status_code == 200
    assert "Load campaign" in body
    assert campaign_service.get_active_campaign().id == second.id

    # Act
    loaded = client.post(
        f"/campaigns/{first.id}/activate",
        data={"return_to": "detail"},
        follow_redirects=True,
    )

    # Assert
    assert loaded.status_code == 200
    assert b"loaded" in loaded.data
    assert campaign_service.get_active_campaign().id == first.id
    assert "Load campaign" not in loaded.get_data(as_text=True)


def test_miniatures_page_links_to_loaded_campaign(client, minimal_force):
    """The inventory start page links to the currently loaded campaign."""
    # Arrange
    campaign = _create_campaign(minimal_force, "Reach")

    # Act
    response = client.get("/miniatures")
    body = response.get_data(as_text=True)

    # Assert
    assert response.status_code == 200
    assert "Loaded Campaign" in body
    assert "Reach" in body
    assert f"/campaigns/{campaign.id}" in body


# --- Aces ruleset ---


def test_create_campaign_defaults_to_chaos_ruleset(client, minimal_force):
    """Campaigns default to the Chaos Campaign ruleset when none is given."""
    campaign = _create_campaign(minimal_force, "Default Ruleset")

    assert campaign.ruleset == "chaos"
    assert campaign.difficulty is None


def test_create_campaign_aces_ruleset_and_difficulty(client, minimal_force):
    """Aces campaigns persist their ruleset and optional difficulty."""
    campaign = _create_campaign(
        minimal_force, "Aces Campaign", ruleset="aces", difficulty="veteran"
    )

    assert campaign.ruleset == "aces"
    assert campaign.difficulty == "veteran"


def test_create_campaign_rejects_invalid_ruleset(client, minimal_force):
    with pytest.raises(ValueError, match="Unknown campaign ruleset"):
        _create_campaign(minimal_force, "Bad Ruleset", ruleset="not-a-ruleset")


def test_create_aces_sortie_requires_aces_campaign(client, minimal_force):
    """A Chaos Campaign cannot create a Contract-free Sortie."""
    campaign = _create_campaign(minimal_force, "Chaos Campaign")

    with pytest.raises(ValueError, match="only available for aces campaigns"):
        campaign_service.create_aces_sortie(campaign.id, "Sortie 1")


def test_create_aces_sortie_has_no_contract(client, minimal_force):
    """Aces Sorties attach directly to the Campaign, with no Contract."""
    campaign = _create_campaign(minimal_force, "Aces Campaign", ruleset="aces")

    sortie = campaign_service.create_aces_sortie(
        campaign.id, "Waypoint Alpha", scenario_type="Recon"
    )

    assert sortie.campaign_id == campaign.id
    assert sortie.contract_id is None
    assert sortie.status == "planning"
    assert sortie.scenario_type == "Recon"


@patch("app.services.campaign_service.mul_service.find_unit_in_search_results")
def test_purchase_campaign_unit_cost_and_ledger(mock_find, client, minimal_force):
    """Purchase cost is PV x 40 SP and is recorded as a new CampaignUnit + ledger entry."""
    _enable_alpha_strike(minimal_force, 400)
    campaign = _create_campaign(
        minimal_force, "Aces Campaign", ruleset="aces", opening_warchest=2000
    )
    mock_find.return_value = WHM_RAW  # BFPointValue 40

    unit = campaign_service.purchase_campaign_unit(
        campaign.id, 7563, search_name="Warhammer"
    )

    assert unit.miniature_id is None
    assert unit.point_value == 40
    assert unit.campaign_id == campaign.id

    reloaded = campaign_service.get_campaign_by_id(campaign.id)
    assert reloaded.warchest_balance == 2000 - (40 * 40)
    purchase_tx = next(
        tx for tx in reloaded.transactions if tx.transaction_type == "unit_purchase"
    )
    assert purchase_tx.actual_amount == -(40 * 40)


@patch("app.services.campaign_service.mul_service.find_unit_in_search_results")
def test_purchase_campaign_unit_rejects_missing_pv(mock_find, client, minimal_force):
    _enable_alpha_strike(minimal_force, 400)
    campaign = _create_campaign(minimal_force, "Aces Campaign", ruleset="aces")
    mock_find.return_value = {**WHM_RAW, "BFPointValue": 0}

    with pytest.raises(ValueError, match="no valid MUL Point Value"):
        campaign_service.purchase_campaign_unit(campaign.id, 7563, search_name="Warhammer")


@patch("app.services.campaign_service.mul_service.find_unit_in_search_results")
def test_purchase_campaign_unit_rejects_insufficient_warchest(mock_find, client, minimal_force):
    _enable_alpha_strike(minimal_force, 400)
    campaign = _create_campaign(
        minimal_force, "Aces Campaign", ruleset="aces", opening_warchest=100
    )
    mock_find.return_value = WHM_RAW  # cost = 1600

    with pytest.raises(ValueError, match="Insufficient Warchest"):
        campaign_service.purchase_campaign_unit(campaign.id, 7563, search_name="Warhammer")


@patch("app.services.campaign_service.mul_service.find_unit_in_search_results")
def test_purchase_campaign_unit_requires_aces_campaign(mock_find, client, minimal_force):
    campaign = _create_campaign(minimal_force, "Chaos Campaign")
    mock_find.return_value = WHM_RAW

    with pytest.raises(ValueError, match="only available for aces campaigns"):
        campaign_service.purchase_campaign_unit(campaign.id, 7563, search_name="Warhammer")


def test_get_units_missing_pv(client, minimal_force):
    """Units without a MUL PV are reported as ineligible for force accounting."""
    campaign = _create_campaign(minimal_force, "Aces Campaign", ruleset="aces")

    missing = campaign_service.get_units_missing_pv(campaign.id)

    assert len(missing) == 2  # neither seeded unit has an Alpha Strike assignment


def test_get_aces_force_summary(client, minimal_force):
    minis = _first_force_miniatures(minimal_force)
    _enable_alpha_strike(minimal_force, 400)
    _assign_variant(minis[0].id, WHM_RAW)
    campaign = _create_campaign(
        minimal_force, "Aces Campaign", ruleset="aces", difficulty="veteran"
    )

    summary = campaign_service.get_aces_force_summary(campaign.id)

    assert summary["total_active_pv"] == 40
    assert summary["difficulty"] == "veteran"
    assert summary["units_missing_pv"] == 1
    assert summary["completed_sortie_count"] == 0
