"""Campaign management: roster snapshots, pilots, Warchest, and travel."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_lance import CampaignLance
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.miniature import Miniature
from ..models.travel_event import TravelEvent
from ..models.warchest_transaction import WarchestTransaction
from . import alpha_strike_service, force_service

logger = structlog.get_logger()

CAMPAIGN_STATUSES = ("planning", "active", "paused", "completed")
UNIT_CONDITIONS = ("active", "damaged", "destroyed", "truly-destroyed")
PILOT_STATUSES = ("alive", "dead", "retired")
TRAVEL_STATUSES = ("in_transit", "arrived")
BT_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
GENERIC_AS_SKILL = 4
DEFAULT_PILOT_GUNNERY = 4
DEFAULT_PILOT_PILOTING = 5
DEFAULT_OPENING_WARCHEST = 3000
UNAVAILABLE_CONDITIONS = {"destroyed", "truly-destroyed"}


class MiniatureInActiveCampaignError(ValueError):
    """Raised when a physical miniature cannot be deleted because it is on the loaded campaign."""


def unit_is_omni(raw: dict[str, Any] | None, variant: str | None = None) -> bool:
    """Detect Omni units from a MUL snapshot without inventing a configuration."""
    if not raw:
        return False
    type_info = raw.get("Type") or {}
    type_name = type_info.get("Name") if isinstance(type_info, dict) else str(type_info)
    abilities = str(raw.get("BFAbilities") or "")
    name = str(raw.get("Name") or "")
    resolved_variant = (variant or raw.get("Variant") or "").strip()
    haystack = f"{type_name} {abilities}".upper()
    if "OMNI" in haystack:
        return True
    if resolved_variant.lower() == "prime":
        return True
    return name.lower().endswith(" prime")


def availability_for_condition(condition: str, available: bool | None = None) -> bool:
    if condition in UNAVAILABLE_CONDITIONS:
        return False
    if available is not None:
        return available
    return condition in {"active", "damaged"}


def campaign_month_label(campaign: Campaign, month: int | None = None) -> str:
    """Return 'Campaign Month N' and optional BattleTech calendar display."""
    number = month if month is not None else campaign.current_campaign_month
    label = f"Campaign Month {number}"
    if campaign.starting_bt_year is None or campaign.starting_bt_month is None:
        return label
    if campaign.starting_bt_month < 1 or campaign.starting_bt_month > 12:
        return label
    offset = (campaign.starting_bt_month - 1) + (number - 1)
    year = campaign.starting_bt_year + offset // 12
    month_name = BT_MONTHS[offset % 12]
    return f"{label} — {month_name} {year}"


def location_display(campaign: Campaign) -> str:
    """Current location, or in-transit origin → destination when a move is underway."""
    in_transit = next(
        (event for event in campaign.travel_events if event.status == "in_transit"),
        None,
    )
    if in_transit:
        return f"In transit: {in_transit.origin} → {in_transit.destination}"
    return campaign.current_location or "Unknown"


def compute_opening_warchest(override: int | None = None) -> int:
    """Hot Spots default opening Warchest is 3,000 SP unless the player overrides."""
    if override is not None:
        return override
    return DEFAULT_OPENING_WARCHEST


def sync_pilot_wounded_flag(pilot: CampaignPilot) -> None:
    """Keep legacy wounded boolean aligned with wounds; wounds are authoritative."""
    pilot.wounded = pilot.wounds > 0


def pilot_is_available(pilot: CampaignPilot) -> bool:
    return pilot.status == "alive" and pilot.wounds == 0


def _eager_load_campaign(campaign: Campaign) -> None:
    for lance in campaign.lances:
        for unit in lance.units:
            _ = unit.miniature
    for unit in campaign.units:
        _ = unit.miniature
        _ = unit.lance
    for pilot in campaign.pilots:
        _ = pilot.preferred_unit
    _ = campaign.transactions
    _ = campaign.travel_events
    for contract in campaign.contracts:
        _ = contract.sorties
        for roster in contract.roster_units:
            _ = roster.campaign_unit
    for sortie in campaign.sorties:
        _ = sortie.units
    for order in campaign.repair_orders:
        _ = order.unit
    for order in campaign.rearm_orders:
        _ = order.unit
    for event in campaign.damage_events:
        _ = event.unit
    for event in campaign.injury_events:
        _ = event.pilot
    for event in campaign.configuration_events:
        _ = event.unit


def _expunge_campaign(session, campaign: Campaign) -> Campaign:
    _eager_load_campaign(campaign)
    session.expunge(campaign)
    return campaign


def get_active_campaign() -> Campaign | None:
    with session_scope() as session:
        campaign = session.execute(
            select(Campaign).where(Campaign.is_active == True)  # noqa: E712
        ).scalar_one_or_none()
        if campaign:
            return _expunge_campaign(session, campaign)
        return None


def get_all_campaigns() -> list[Campaign]:
    with session_scope() as session:
        campaigns = list(
            session.execute(
                select(Campaign).order_by(Campaign.is_active.desc(), Campaign.created_at.desc())
            )
            .scalars()
            .all()
        )
        for campaign in campaigns:
            _eager_load_campaign(campaign)
            session.expunge(campaign)
        return campaigns


def get_campaign_by_id(campaign_id: int) -> Campaign | None:
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if campaign:
            return _expunge_campaign(session, campaign)
        return None


def missing_miniature_units(campaign: Campaign) -> list[CampaignUnit]:
    missing: list[CampaignUnit] = []
    for unit in campaign.units:
        if unit.miniature_missing or (unit.miniature_id is not None and unit.miniature is None):
            missing.append(unit)
    return missing


def _snapshot_unit_from_miniature(
    session,
    *,
    campaign_id: int,
    lance_id: int | None,
    miniature: Miniature,
    assignment: Any | None,
    order: int,
) -> CampaignUnit:
    raw: dict[str, Any] | None = None
    variant: str | None = None
    if assignment is not None:
        try:
            raw = json.loads(assignment.mul_snapshot_json)
        except (TypeError, json.JSONDecodeError):
            raw = None
        variant = assignment.variant or None
        is_omni = unit_is_omni(raw, variant)
        unit = CampaignUnit(
            campaign_id=campaign_id,
            campaign_lance_id=lance_id,
            miniature_id=miniature.id,
            series=miniature.series,
            unique_id=miniature.unique_id,
            prefix=miniature.prefix,
            chassis=miniature.chassis,
            type=miniature.type,
            faction=miniature.faction,
            mul_unit_id=assignment.mul_unit_id,
            variant=variant,
            class_name=assignment.class_name,
            tonnage=assignment.tonnage,
            point_value=assignment.point_value,
            unit_type_id=assignment.unit_type_id,
            unit_type_name=assignment.unit_type_name,
            display_name=assignment.display_name,
            mul_snapshot_json=assignment.mul_snapshot_json,
            is_omni=is_omni,
            condition="active",
            available=True,
            miniature_missing=False,
            order=order,
        )
        session.add(unit)
        return unit

    unit = CampaignUnit(
        campaign_id=campaign_id,
        campaign_lance_id=lance_id,
        miniature_id=miniature.id,
        series=miniature.series,
        unique_id=miniature.unique_id,
        prefix=miniature.prefix,
        chassis=miniature.chassis,
        type=miniature.type,
        faction=miniature.faction,
        variant=None,
        is_omni=False,
        condition="active",
        available=True,
        miniature_missing=False,
        order=order,
    )
    session.add(unit)
    return unit


def create_campaign_from_force(
    force_id: int,
    name: str,
    *,
    scale: int = 1,
    reputation: int = 1,
    status: str = "planning",
    starting_bt_year: int,
    starting_bt_month: int,
    current_location: str | None = None,
    notes: str | None = None,
    opening_warchest: int | None = None,
) -> Campaign:
    """Snapshot a saved Force into an independent Campaign and load it as active."""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Campaign name is required")
    if status not in CAMPAIGN_STATUSES:
        raise ValueError("Invalid campaign status")
    if scale < 1 or scale > 5:
        raise ValueError("Scale must be between 1 and 5")
    if starting_bt_year is None:
        raise ValueError("Starting year is required")
    if starting_bt_year < 1000 or starting_bt_year > 9999:
        raise ValueError("Starting year must be a 4-digit year")
    if starting_bt_month is None:
        raise ValueError("Starting month is required")
    if starting_bt_month < 1 or starting_bt_month > 12:
        raise ValueError("Starting month must be between 1 and 12")

    force = force_service.get_force_by_id(force_id)
    if force is None:
        raise ValueError("Force not found")

    opening = compute_opening_warchest(opening_warchest)
    assignments = alpha_strike_service.get_assignments_for_force(force_id)
    as_force = alpha_strike_service.get_alpha_strike_force(force_id)

    with session_scope() as session:
        session.query(Campaign).update({"is_active": False})
        campaign = Campaign(
            name=cleaned,
            status=status,
            is_active=True,
            current_campaign_month=1,
            starting_bt_year=starting_bt_year,
            starting_bt_month=starting_bt_month,
            current_location=current_location.strip() if current_location else None,
            warchest_balance=0,
            reputation=reputation,
            scale=scale,
            notes=notes.strip() if notes else None,
            source_force_name=force.name,
            mul_faction_id=as_force.mul_faction_id if as_force else None,
            mul_era_id=as_force.mul_era_id if as_force else None,
            mul_faction_name=as_force.faction_name if as_force else None,
            mul_era_name=as_force.era_name if as_force else None,
        )
        session.add(campaign)
        session.flush()

        for lance in force.lances:
            campaign_lance = CampaignLance(
                campaign_id=campaign.id,
                name=lance.name or f"Lance {lance.order + 1}",
                order=lance.order,
            )
            session.add(campaign_lance)
            session.flush()
            for fm in lance.miniatures:
                miniature = fm.miniature
                _snapshot_unit_from_miniature(
                    session,
                    campaign_id=campaign.id,
                    lance_id=campaign_lance.id,
                    miniature=miniature,
                    assignment=assignments.get(fm.id),
                    order=fm.order,
                )

        tx = WarchestTransaction(
            campaign_id=campaign.id,
            campaign_month=1,
            transaction_type="opening_balance",
            description="Opening Warchest",
            gross_amount=opening,
            covered_amount=0,
            actual_amount=opening,
            resulting_balance=opening,
        )
        session.add(tx)
        campaign.warchest_balance = opening
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        logger.info(
            "campaign_created",
            campaign_id=campaign.id,
            source_force=force.name,
            opening_warchest=opening,
        )
        return _expunge_campaign(session, campaign)


def switch_campaign(campaign_id: int) -> Campaign | None:
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            return None
        session.query(Campaign).update({"is_active": False})
        campaign.is_active = True
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_campaign(session, campaign)


def update_campaign(
    campaign_id: int,
    *,
    name: str | None = None,
    status: str | None = None,
    current_campaign_month: int | None = None,
    starting_bt_year: int | None | object = ...,
    starting_bt_month: int | None | object = ...,
    current_location: str | None | object = ...,
    reputation: int | None = None,
    scale: int | None = None,
    notes: str | None | object = ...,
) -> Campaign | None:
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            return None
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Campaign name is required")
            campaign.name = cleaned
        if status is not None:
            if status not in CAMPAIGN_STATUSES:
                raise ValueError("Invalid campaign status")
            campaign.status = status
        if current_campaign_month is not None:
            if current_campaign_month < 1:
                raise ValueError("Campaign month must be 1 or greater")
            campaign.current_campaign_month = current_campaign_month
        if starting_bt_year is not ...:
            year = starting_bt_year
            if year is not None and (year < 1000 or year > 9999):
                raise ValueError("Starting year must be a 4-digit year")
            campaign.starting_bt_year = year  # type: ignore[assignment]
        if starting_bt_month is not ...:
            month = starting_bt_month
            if month is not None and (month < 1 or month > 12):
                raise ValueError("Starting month must be between 1 and 12")
            campaign.starting_bt_month = month  # type: ignore[assignment]
        if current_location is not ...:
            loc = current_location
            if isinstance(loc, str) and loc.strip():
                campaign.current_location = loc.strip()
            else:
                campaign.current_location = None
        if reputation is not None:
            campaign.reputation = reputation
        if scale is not None:
            if scale < 1 or scale > 5:
                raise ValueError("Scale must be between 1 and 5")
            campaign.scale = scale
        if notes is not ...:
            value = notes
            campaign.notes = value.strip() if isinstance(value, str) and value.strip() else None
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_campaign(session, campaign)


def delete_campaign(campaign_id: int) -> bool:
    from ..models.contract import Contract
    from ..models.contract_unit import ContractUnit
    from ..models.damage_event import DamageEvent
    from ..models.pilot_injury_event import PilotInjuryEvent
    from ..models.rearm_order import RearmOrder
    from ..models.repair_order import RepairOrder
    from ..models.sortie import Sortie
    from ..models.sortie_unit import SortieUnit
    from ..models.unit_configuration_event import UnitConfigurationEvent

    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            return False
        for model in (
            DamageEvent,
            RepairOrder,
            RearmOrder,
            PilotInjuryEvent,
            UnitConfigurationEvent,
        ):
            records = session.query(model).filter(model.campaign_id == campaign_id).all()
            for record in records:
                session.delete(record)
        sortie_ids = [
            row[0]
            for row in session.execute(select(Sortie.id).where(Sortie.campaign_id == campaign_id))
        ]
        if sortie_ids:
            records = session.query(SortieUnit).filter(SortieUnit.sortie_id.in_(sortie_ids)).all()
            for record in records:
                session.delete(record)
        session.query(Sortie).filter(Sortie.campaign_id == campaign_id).delete()
        contract_ids = [
            row[0]
            for row in session.execute(
                select(Contract.id).where(Contract.campaign_id == campaign_id)
            )
        ]
        if contract_ids:
            roster = (
                session.query(ContractUnit).filter(ContractUnit.contract_id.in_(contract_ids)).all()
            )
            for record in roster:
                session.delete(record)
        session.query(WarchestTransaction).filter(
            WarchestTransaction.campaign_id == campaign_id
        ).delete()
        session.query(TravelEvent).filter(TravelEvent.campaign_id == campaign_id).delete()
        session.query(Contract).filter(Contract.campaign_id == campaign_id).delete()
        session.query(CampaignPilot).filter(CampaignPilot.campaign_id == campaign_id).delete()
        session.query(CampaignUnit).filter(CampaignUnit.campaign_id == campaign_id).delete()
        session.query(CampaignLance).filter(CampaignLance.campaign_id == campaign_id).delete()
        session.delete(campaign)
        logger.info("campaign_deleted", campaign_id=campaign_id)
        return True


def delete_all_campaigns() -> int:
    campaigns = get_all_campaigns()
    deleted = 0
    for campaign in campaigns:
        if delete_campaign(campaign.id):
            deleted += 1
    return deleted


def add_campaign_lance(
    campaign_id: int, name: str, special_rules: str | None = None
) -> CampaignLance:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Lance name is required")
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        next_order = len(campaign.lances)
        lance = CampaignLance(
            campaign_id=campaign_id,
            name=cleaned,
            order=next_order,
            special_rules=special_rules.strip() if special_rules else None,
        )
        session.add(lance)
        session.flush()
        session.expunge(lance)
        return lance


def update_campaign_lance(
    lance_id: int, *, name: str | None = None, special_rules: str | None | object = ...
) -> CampaignLance | None:
    with session_scope() as session:
        lance = session.get(CampaignLance, lance_id)
        if not lance:
            return None
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Lance name is required")
            lance.name = cleaned
        if special_rules is not ...:
            value = special_rules
            if isinstance(value, str) and value.strip():
                lance.special_rules = value.strip()
            else:
                lance.special_rules = None
        session.flush()
        session.expunge(lance)
        return lance


def add_campaign_unit(
    campaign_id: int,
    miniature_id: int,
    *,
    lance_id: int | None = None,
    notes: str | None = None,
) -> CampaignUnit:
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        miniature = session.get(Miniature, miniature_id)
        if not miniature:
            raise ValueError("Miniature not found")
        existing = session.execute(
            select(CampaignUnit).where(
                CampaignUnit.campaign_id == campaign_id,
                CampaignUnit.miniature_id == miniature_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("Miniature is already in this campaign")
        if lance_id is not None:
            lance = session.get(CampaignLance, lance_id)
            if not lance or lance.campaign_id != campaign_id:
                raise ValueError("Lance not found in this campaign")
        order = session.query(CampaignUnit).filter(CampaignUnit.campaign_id == campaign_id).count()
        unit = _snapshot_unit_from_miniature(
            session,
            campaign_id=campaign_id,
            lance_id=lance_id,
            miniature=miniature,
            assignment=None,
            order=order,
        )
        unit.notes = notes.strip() if notes else None
        session.flush()
        _ = unit.miniature
        session.expunge(unit)
        return unit


def update_campaign_unit(
    unit_id: int,
    *,
    condition: str | None = None,
    available: bool | None = None,
    notes: str | None | object = ...,
    is_omni: bool | None = None,
    lance_id: int | None | object = ...,
) -> CampaignUnit | None:
    with session_scope() as session:
        unit = session.get(CampaignUnit, unit_id)
        if not unit:
            return None
        if condition is not None:
            if condition not in UNIT_CONDITIONS:
                raise ValueError("Invalid unit condition")
            unit.condition = condition
            unit.available = availability_for_condition(condition, available)
        elif available is not None:
            if unit.condition in UNAVAILABLE_CONDITIONS:
                unit.available = False
            else:
                unit.available = available
        if notes is not ...:
            value = notes
            unit.notes = value.strip() if isinstance(value, str) and value.strip() else None
        if is_omni is not None:
            unit.is_omni = is_omni
        if lance_id is not ...:
            if lance_id is None:
                unit.campaign_lance_id = None
            else:
                lance = session.get(CampaignLance, lance_id)
                if not lance or lance.campaign_id != unit.campaign_id:
                    raise ValueError("Lance not found in this campaign")
                unit.campaign_lance_id = lance.id  # type: ignore[assignment]
        session.flush()
        _ = unit.miniature
        session.expunge(unit)
        return unit


def delete_campaign_unit(unit_id: int) -> bool:
    with session_scope() as session:
        unit = session.get(CampaignUnit, unit_id)
        if not unit:
            return False
        session.query(CampaignPilot).filter(CampaignPilot.preferred_unit_id == unit_id).update(
            {"preferred_unit_id": None}
        )
        session.delete(unit)
        return True


def add_campaign_pilot(
    campaign_id: int,
    name: str,
    *,
    callsign: str | None = None,
    gunnery: int = DEFAULT_PILOT_GUNNERY,
    piloting: int = DEFAULT_PILOT_PILOTING,
    alpha_strike_skill: int = GENERIC_AS_SKILL,
    edge_tokens: int = 0,
    edge_abilities: str | None = None,
    improvement_sp: int = 0,
    wounds: int = 0,
    status: str = "alive",
    notes: str | None = None,
    preferred_unit_id: int | None = None,
) -> CampaignPilot:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Pilot name is required")
    if status not in PILOT_STATUSES:
        raise ValueError("Invalid pilot status")
    if wounds < 0:
        raise ValueError("Wounds cannot be negative")
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        if preferred_unit_id is not None:
            unit = session.get(CampaignUnit, preferred_unit_id)
            if not unit or unit.campaign_id != campaign_id:
                raise ValueError("Preferred unit must belong to this campaign")
        pilot = CampaignPilot(
            campaign_id=campaign_id,
            name=cleaned,
            callsign=callsign.strip() if callsign else None,
            gunnery=gunnery,
            piloting=piloting,
            alpha_strike_skill=alpha_strike_skill,
            edge_tokens=edge_tokens,
            edge_abilities=edge_abilities.strip() if edge_abilities else None,
            improvement_sp=improvement_sp,
            wounds=wounds,
            status=status,
            notes=notes.strip() if notes else None,
            preferred_unit_id=preferred_unit_id,
        )
        sync_pilot_wounded_flag(pilot)
        session.add(pilot)
        session.flush()
        _ = pilot.preferred_unit
        session.expunge(pilot)
        return pilot


def update_campaign_pilot(
    pilot_id: int,
    *,
    name: str | None = None,
    callsign: str | None | object = ...,
    gunnery: int | None = None,
    piloting: int | None = None,
    alpha_strike_skill: int | None = None,
    edge_tokens: int | None = None,
    edge_abilities: str | None | object = ...,
    improvement_sp: int | None = None,
    wounds: int | None = None,
    status: str | None = None,
    notes: str | None | object = ...,
    preferred_unit_id: int | None | object = ...,
) -> CampaignPilot | None:
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot:
            return None
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Pilot name is required")
            pilot.name = cleaned
        if callsign is not ...:
            value = callsign
            pilot.callsign = value.strip() if isinstance(value, str) and value.strip() else None
        if gunnery is not None:
            pilot.gunnery = gunnery
        if piloting is not None:
            pilot.piloting = piloting
        if alpha_strike_skill is not None:
            pilot.alpha_strike_skill = alpha_strike_skill
        if edge_tokens is not None:
            pilot.edge_tokens = edge_tokens
        if edge_abilities is not ...:
            value = edge_abilities
            if isinstance(value, str) and value.strip():
                pilot.edge_abilities = value.strip()
            else:
                pilot.edge_abilities = None
        if improvement_sp is not None:
            pilot.improvement_sp = improvement_sp
        if wounds is not None:
            if wounds < 0:
                raise ValueError("Wounds cannot be negative")
            pilot.wounds = wounds
            sync_pilot_wounded_flag(pilot)
        if status is not None:
            if status not in PILOT_STATUSES:
                raise ValueError("Invalid pilot status")
            pilot.status = status
            if status != "alive":
                sync_pilot_wounded_flag(pilot)
        if notes is not ...:
            value = notes
            pilot.notes = value.strip() if isinstance(value, str) and value.strip() else None
        if preferred_unit_id is not ...:
            if preferred_unit_id is None:
                pilot.preferred_unit_id = None
            else:
                unit = session.get(CampaignUnit, preferred_unit_id)
                if not unit or unit.campaign_id != pilot.campaign_id:
                    raise ValueError("Preferred unit must belong to this campaign")
                pilot.preferred_unit_id = unit.id
        session.flush()
        _ = pilot.preferred_unit
        session.expunge(pilot)
        return pilot


def delete_campaign_pilot(pilot_id: int) -> bool:
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot:
            return False
        session.delete(pilot)
        return True


def recover_pilot_wound(pilot_id: int) -> CampaignPilot:
    """Manually clear one wound from a living named pilot."""
    from ..models.pilot_injury_event import PilotInjuryEvent

    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot:
            raise ValueError("Pilot not found")
        if pilot.status != "alive":
            raise ValueError("Only living pilots can recover wounds")
        if pilot.wounds <= 0:
            raise ValueError("Pilot has no wounds to recover")
        campaign = session.get(Campaign, pilot.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        pilot.wounds -= 1
        sync_pilot_wounded_flag(pilot)
        session.add(
            PilotInjuryEvent(
                campaign_id=campaign.id,
                campaign_pilot_id=pilot.id,
                campaign_month=campaign.current_campaign_month,
                event_type="recovered",
                notes="Recovered 1 wound",
            )
        )
        session.flush()
        _ = pilot.preferred_unit
        session.expunge(pilot)
        return pilot


def add_warchest_transaction(
    campaign_id: int,
    *,
    transaction_type: str,
    description: str,
    actual_amount: int,
    campaign_month: int | None = None,
    gross_amount: int | None = None,
    covered_amount: int = 0,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
    notes: str | None = None,
) -> WarchestTransaction:
    cleaned = description.strip()
    if not cleaned:
        raise ValueError("Transaction description is required")
    if not transaction_type.strip():
        raise ValueError("Transaction type is required")
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        month = campaign_month if campaign_month is not None else campaign.current_campaign_month
        if month < 1:
            raise ValueError("Campaign month must be 1 or greater")
        gross = actual_amount if gross_amount is None else gross_amount
        new_balance = campaign.warchest_balance + actual_amount
        tx = WarchestTransaction(
            campaign_id=campaign_id,
            campaign_month=month,
            transaction_type=transaction_type.strip(),
            description=cleaned,
            gross_amount=gross,
            covered_amount=covered_amount,
            actual_amount=actual_amount,
            resulting_balance=new_balance,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            notes=notes.strip() if notes else None,
        )
        session.add(tx)
        campaign.warchest_balance = new_balance
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        session.expunge(tx)
        return tx


def create_travel_event(
    campaign_id: int,
    origin: str,
    destination: str,
    *,
    departure_campaign_month: int | None = None,
    arrival_campaign_month: int | None = None,
    jump_count: int | None = None,
    transport_mode: str = "manual",
    standard_amount: int | None = None,
    employer_payment: int | None = None,
    actual_expense: int | None = None,
    gross_cost: int | None = None,
    covered_amount: int | None = None,
    actual_warchest_impact: int | None = None,
    status: str = "in_transit",
    notes: str | None = None,
    contract_id: int | None = None,
) -> TravelEvent:
    """Record travel. Net SP = employer payment - actual expense."""
    from .contract_service import (
        TRANSPORT_MODES,
        calculate_standard_transport,
        round_half_up_sp,
    )

    if status not in TRAVEL_STATUSES:
        raise ValueError("Invalid travel status")
    mode = (transport_mode or "manual").strip().lower()
    if mode not in TRANSPORT_MODES:
        raise ValueError("Invalid transportation mode")
    origin_clean = origin.strip()
    dest_clean = destination.strip()
    if not origin_clean or not dest_clean:
        raise ValueError("Origin and destination are required")
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        linked_contract = None
        if contract_id is not None:
            from ..models.contract import Contract

            linked_contract = session.get(Contract, contract_id)
            if not linked_contract or linked_contract.campaign_id != campaign_id:
                raise ValueError("Contract not found in this campaign")
        scale = linked_contract.scale if linked_contract else campaign.scale
        transport_percent = linked_contract.transportation_percent if linked_contract else 0

        if standard_amount is None and gross_cost is not None:
            standard_amount = gross_cost
        if mode in {"standard", "jump"}:
            calculated = calculate_standard_transport(
                mode, scale=scale, jump_count=jump_count
            )
            if standard_amount is None:
                standard_amount = calculated
        if standard_amount is None:
            raise ValueError("Standard transportation amount is required")
        if standard_amount < 0:
            raise ValueError("Standard transportation amount cannot be negative")

        if employer_payment is None and covered_amount is not None:
            employer_payment = covered_amount
        if employer_payment is None:
            if linked_contract:
                employer_payment = round_half_up_sp(standard_amount * transport_percent / 100)
            else:
                employer_payment = 0
        if employer_payment < 0:
            raise ValueError("Employer transportation payment cannot be negative")

        if actual_expense is None:
            actual_expense = standard_amount
        if actual_expense < 0:
            raise ValueError("Actual transportation expense cannot be negative")

        impact = (
            actual_warchest_impact
            if actual_warchest_impact is not None
            else employer_payment - actual_expense
        )
        departure = (
            departure_campaign_month
            if departure_campaign_month is not None
            else campaign.current_campaign_month
        )
        event = TravelEvent(
            campaign_id=campaign_id,
            contract_id=linked_contract.id if linked_contract else None,
            origin=origin_clean,
            destination=dest_clean,
            departure_campaign_month=departure,
            arrival_campaign_month=arrival_campaign_month,
            jump_count=jump_count,
            transport_mode=mode,
            gross_cost=standard_amount,
            covered_amount=employer_payment,
            actual_expense=actual_expense,
            actual_warchest_impact=impact,
            status=status,
            notes=notes.strip() if notes else None,
        )
        session.add(event)
        session.flush()

        if impact:
            new_balance = campaign.warchest_balance + impact
            session.add(
                WarchestTransaction(
                    campaign_id=campaign_id,
                    campaign_month=departure,
                    transaction_type="travel",
                    description=(
                        f"Travel {origin_clean} → {dest_clean} "
                        f"(employer {employer_payment} SP − expense {actual_expense} SP)"
                    ),
                    gross_amount=-actual_expense,
                    covered_amount=employer_payment,
                    actual_amount=impact,
                    resulting_balance=new_balance,
                    related_entity_type="travel_event",
                    related_entity_id=event.id,
                )
            )
            campaign.warchest_balance = new_balance

        if status == "arrived":
            campaign.current_location = dest_clean
            if event.arrival_campaign_month is None:
                event.arrival_campaign_month = campaign.current_campaign_month

        campaign.updated_at = datetime.now(UTC)
        session.flush()
        session.expunge(event)
        return event


def complete_travel_event(
    event_id: int, *, arrival_campaign_month: int | None = None
) -> TravelEvent | None:
    with session_scope() as session:
        event = session.get(TravelEvent, event_id)
        if not event:
            return None
        campaign = session.get(Campaign, event.campaign_id)
        if not campaign:
            return None
        event.status = "arrived"
        event.arrival_campaign_month = (
            arrival_campaign_month
            if arrival_campaign_month is not None
            else campaign.current_campaign_month
        )
        campaign.current_location = event.destination
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        session.expunge(event)
        return event


def miniature_blocked_by_active_campaign(miniature_id: int) -> Campaign | None:
    """Return the loaded campaign if it still references this physical miniature."""
    with session_scope() as session:
        campaign = session.execute(
            select(Campaign).where(Campaign.is_active == True)  # noqa: E712
        ).scalar_one_or_none()
        if not campaign:
            return None
        unit = session.execute(
            select(CampaignUnit).where(
                CampaignUnit.campaign_id == campaign.id,
                CampaignUnit.miniature_id == miniature_id,
            )
        ).scalar_one_or_none()
        if unit:
            _eager_load_campaign(campaign)
            session.expunge(campaign)
            return campaign
        return None


def detach_miniature_from_inactive_campaigns(miniature_id: int) -> int:
    """Clear miniature FKs on non-loaded campaigns; history keeps a missing-mini warning."""
    with session_scope() as session:
        active = session.execute(
            select(Campaign).where(Campaign.is_active == True)  # noqa: E712
        ).scalar_one_or_none()
        active_id = active.id if active else None
        stmt = select(CampaignUnit).where(CampaignUnit.miniature_id == miniature_id)
        if active_id is not None:
            stmt = stmt.where(CampaignUnit.campaign_id != active_id)
        units = list(session.execute(stmt).scalars().all())
        for unit in units:
            unit.miniature_id = None
            unit.miniature_missing = True
        return len(units)
