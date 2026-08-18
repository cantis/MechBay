"""After Action, repairs, rearming, Omni reconfiguration, and month advance."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.contract import Contract
from ..models.damage_event import DamageEvent
from ..models.pilot_injury_event import PilotInjuryEvent
from ..models.rearm_order import RearmOrder
from ..models.repair_order import RepairOrder
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from ..models.travel_event import TravelEvent
from ..models.unit_configuration_event import UnitConfigurationEvent
from ..models.warchest_transaction import WarchestTransaction
from . import campaign_service, contract_service, mul_service
from .campaign_service import unit_is_omni
from .contract_service import SORTIE_OUTCOMES, transportation_coverage

DAMAGE_OUTCOMES = (
    "none",
    "armour",
    "structure",
    "crippled",
    "destroyed",
)
REPAIR_STATUSES = ("pending", "approved", "in_progress", "completed", "cancelled")
OPEN_REPAIR_STATUSES = {"pending", "approved", "in_progress"}
REPAIRABLE_DAMAGE = {"armour", "structure", "crippled", "destroyed"}
REARM_COST = 20
_ENE_ABILITY = re.compile(r"\bENE\b", re.IGNORECASE)


def _abilities(raw_json: str | None) -> str:
    if not raw_json:
        return ""
    try:
        raw = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return ""
    return str(raw.get("BFAbilities") or "")


def unit_has_ene(unit: CampaignUnit | SortieUnit) -> bool:
    abilities = _abilities(unit.mul_snapshot_json)
    return bool(_ENE_ABILITY.search(abilities))


def support_coverage(gross_cost: int, support_percent: int) -> int:
    return transportation_coverage(gross_cost, support_percent)


def _condition_for_damage(damage: str) -> tuple[str, bool]:
    if damage == "none":
        return "active", True
    if damage == "armour":
        return "damaged", True
    if damage in {"structure", "crippled"}:
        return "damaged", False
    if damage == "destroyed":
        return "destroyed", False
    return "truly-destroyed", False


def _post_wp(
    session,
    campaign: Campaign,
    *,
    campaign_month: int,
    transaction_type: str,
    description: str,
    gross_amount: int,
    covered_amount: int,
    actual_amount: int,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
) -> None:
    if actual_amount == 0 and gross_amount == 0:
        return
    new_balance = campaign.warchest_balance + actual_amount
    session.add(
        WarchestTransaction(
            campaign_id=campaign.id,
            campaign_month=campaign_month,
            transaction_type=transaction_type,
            description=description,
            gross_amount=gross_amount,
            covered_amount=covered_amount,
            actual_amount=actual_amount,
            resulting_balance=new_balance,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
    )
    campaign.warchest_balance = new_balance


def _active_support_percent(session, campaign_id: int) -> int:
    contract = session.execute(
        select(Contract).where(Contract.campaign_id == campaign_id, Contract.status == "active")
    ).scalar_one_or_none()
    return contract.support_percent if contract else 0


def _open_repairs(session, campaign_unit_id: int) -> list[RepairOrder]:
    return list(
        session.execute(
            select(RepairOrder).where(
                RepairOrder.campaign_unit_id == campaign_unit_id,
                RepairOrder.status.in_(OPEN_REPAIR_STATUSES),
            )
        ).scalars()
    )


def unit_is_fully_repaired(session, unit: CampaignUnit) -> bool:
    if unit.condition != "active" or not unit.available:
        return False
    if unit.damage_category not in {"none", ""}:
        return False
    return not _open_repairs(session, unit.id)


def recover_wounded_pilots(session, sortie: Sortie) -> None:
    """Wounded pilots who sat this Sortie out become available for the next one."""
    fought_ids = {row.campaign_pilot_id for row in sortie.units if row.campaign_pilot_id}
    pilots = list(
        session.execute(
            select(CampaignPilot).where(
                CampaignPilot.campaign_id == sortie.campaign_id,
                CampaignPilot.wounded == True,  # noqa: E712
                CampaignPilot.status == "alive",
            )
        ).scalars()
    )
    for pilot in pilots:
        if pilot.id in fought_ids:
            continue
        pilot.wounded = False
        session.add(
            PilotInjuryEvent(
                campaign_id=sortie.campaign_id,
                campaign_pilot_id=pilot.id,
                sortie_id=sortie.id,
                campaign_month=sortie.campaign_month,
                event_type="recovered",
                notes="Auto-cleared after sitting out one Sortie",
            )
        )


def apply_after_action(
    sortie_id: int,
    unit_results: list[dict[str, Any]],
    *,
    outcome: str | None = None,
    objectives_summary: str | None = None,
    combat_pay: int = 0,
    salvage_notes: str | None = None,
    salvage_wp: int = 0,
    mvp_pilot_id: int | None = None,
    after_action_notes: str | None = None,
) -> Sortie:
    if combat_pay < 0 or salvage_wp < 0:
        raise ValueError("Combat pay and salvage must be zero or positive WP")
    by_id = {int(item["sortie_unit_id"]): item for item in unit_results}
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status not in {"fought", "after_action"}:
            raise ValueError("After Action can only be applied after the Sortie is fought")
        if sortie.status == "after_action":
            raise ValueError("After Action has already been applied")
        if outcome:
            if outcome not in SORTIE_OUTCOMES:
                raise ValueError("Invalid Sortie outcome")
            sortie.outcome = outcome
        if mvp_pilot_id is not None:
            on_sortie = any(row.campaign_pilot_id == mvp_pilot_id for row in sortie.units)
            if not on_sortie:
                raise ValueError("MVP must be a named pilot who fought this Sortie")
            pilot = session.get(CampaignPilot, mvp_pilot_id)
            if not pilot or pilot.campaign_id != sortie.campaign_id:
                raise ValueError("MVP must be a named pilot in this campaign")
        campaign = session.get(Campaign, sortie.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        support = _active_support_percent(session, campaign.id)

        for row in sortie.units:
            result = by_id.get(row.id, {})
            damage = (result.get("damage_outcome") or "none").strip()
            if damage not in DAMAGE_OUTCOMES:
                raise ValueError("Invalid damage outcome")
            row.damage_outcome = damage
            row.pilot_wounded = bool(result.get("pilot_wounded"))
            row.pilot_killed = bool(result.get("pilot_killed"))
            row.needs_rearm = not unit_has_ene(row)

            unit = session.get(CampaignUnit, row.campaign_unit_id) if row.campaign_unit_id else None
            if unit:
                condition, available = _condition_for_damage(damage)
                unit.damage_category = damage if damage != "none" else "none"
                unit.condition = condition
                unit.available = available
                session.add(
                    DamageEvent(
                        campaign_id=campaign.id,
                        campaign_unit_id=unit.id,
                        sortie_id=sortie.id,
                        campaign_month=sortie.campaign_month,
                        damage_category=damage,
                    )
                )
                if damage in REPAIRABLE_DAMAGE:
                    session.add(
                        RepairOrder(
                            campaign_id=campaign.id,
                            sortie_id=sortie.id,
                            campaign_unit_id=unit.id,
                            damage_category=damage,
                            gross_cost=0,
                            covered_amount=0,
                            actual_cost=0,
                            campaign_month=sortie.campaign_month,
                            status="pending",
                        )
                    )
                should_rearm = not unit_has_ene(row)
                if should_rearm:
                    covered = support_coverage(REARM_COST, support)
                    actual = -(REARM_COST - covered)
                    rearm = RearmOrder(
                        campaign_id=campaign.id,
                        sortie_id=sortie.id,
                        campaign_unit_id=unit.id,
                        campaign_month=sortie.campaign_month,
                        gross_cost=REARM_COST,
                        covered_amount=covered,
                        actual_cost=actual,
                    )
                    session.add(rearm)
                    session.flush()
                    _post_wp(
                        session,
                        campaign,
                        campaign_month=sortie.campaign_month,
                        transaction_type="rearm",
                        description=f"Rearm {row.chassis}",
                        gross_amount=-REARM_COST,
                        covered_amount=covered,
                        actual_amount=actual,
                        related_entity_type="rearm_order",
                        related_entity_id=rearm.id,
                    )

            if row.campaign_pilot_id:
                pilot = session.get(CampaignPilot, row.campaign_pilot_id)
                if pilot:
                    if row.pilot_killed:
                        pilot.status = "dead"
                        pilot.wounded = False
                        session.add(
                            PilotInjuryEvent(
                                campaign_id=campaign.id,
                                campaign_pilot_id=pilot.id,
                                sortie_id=sortie.id,
                                campaign_month=sortie.campaign_month,
                                event_type="died",
                            )
                        )
                    elif row.pilot_wounded:
                        pilot.wounded = True
                        session.add(
                            PilotInjuryEvent(
                                campaign_id=campaign.id,
                                campaign_pilot_id=pilot.id,
                                sortie_id=sortie.id,
                                campaign_month=sortie.campaign_month,
                                event_type="wounded",
                            )
                        )

        sortie.objectives_summary = (objectives_summary or "").strip() or None
        sortie.combat_pay = combat_pay
        sortie.salvage_notes = (salvage_notes or "").strip() or None
        sortie.salvage_wp = salvage_wp
        sortie.mvp_pilot_id = mvp_pilot_id
        sortie.after_action_notes = (after_action_notes or "").strip() or None
        sortie.status = "after_action"
        sortie.updated_at = datetime.now(UTC)
        campaign.updated_at = datetime.now(UTC)
        session.flush()

        if combat_pay:
            _post_wp(
                session,
                campaign,
                campaign_month=sortie.campaign_month,
                transaction_type="combat_pay",
                description=f"Combat pay for {sortie.name}",
                gross_amount=combat_pay,
                covered_amount=0,
                actual_amount=combat_pay,
                related_entity_type="sortie",
                related_entity_id=sortie.id,
            )
        if salvage_wp:
            _post_wp(
                session,
                campaign,
                campaign_month=sortie.campaign_month,
                transaction_type="salvage",
                description=f"Salvage from {sortie.name}",
                gross_amount=salvage_wp,
                covered_amount=0,
                actual_amount=salvage_wp,
                related_entity_type="sortie",
                related_entity_id=sortie.id,
            )
        session.flush()
        return contract_service._expunge_sortie(session, sortie)


def mark_unit_truly_destroyed(campaign_unit_id: int) -> CampaignUnit:
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit:
            raise ValueError("Campaign unit not found")
        if unit.condition != "destroyed" and unit.damage_category != "destroyed":
            raise ValueError("Only a destroyed unit can be marked truly destroyed")
        unit.condition = "truly-destroyed"
        unit.damage_category = "truly-destroyed"
        unit.available = False
        for order in _open_repairs(session, unit.id):
            order.status = "cancelled"
        campaign = session.get(Campaign, unit.campaign_id)
        month = campaign.current_campaign_month if campaign else 1
        session.add(
            DamageEvent(
                campaign_id=unit.campaign_id,
                campaign_unit_id=unit.id,
                campaign_month=month,
                damage_category="truly-destroyed",
                notes="Marked truly destroyed after recovery check",
            )
        )
        session.flush()
        _ = unit.miniature
        session.expunge(unit)
        return unit


def close_sortie(sortie_id: int) -> Sortie:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status != "after_action":
            raise ValueError("Close After Action before closing the Sortie")
        sortie.status = "closed"
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        return contract_service._expunge_sortie(session, sortie)


def get_repair_orders(campaign_id: int) -> list[RepairOrder]:
    with session_scope() as session:
        rows = list(
            session.execute(
                select(RepairOrder)
                .where(RepairOrder.campaign_id == campaign_id)
                .order_by(RepairOrder.id)
            ).scalars()
        )
        for row in rows:
            _ = row.unit
            session.expunge(row)
        return rows


def update_repair_order(
    order_id: int, *, gross_cost: int | None = None, notes: str | None = None
) -> RepairOrder:
    with session_scope() as session:
        order = session.get(RepairOrder, order_id)
        if not order:
            raise ValueError("Repair Order not found")
        if order.status not in OPEN_REPAIR_STATUSES:
            raise ValueError("Repair Order is closed")
        if gross_cost is not None:
            if gross_cost < 0:
                raise ValueError("Repair cost must be zero or positive")
            order.gross_cost = gross_cost
            support = _active_support_percent(session, order.campaign_id)
            order.covered_amount = support_coverage(gross_cost, support)
            order.actual_cost = -(gross_cost - order.covered_amount)
        if notes is not None:
            order.notes = notes.strip() or None
        session.flush()
        session.expunge(order)
        return order


def complete_repair_order(order_id: int) -> RepairOrder:
    with session_scope() as session:
        order = session.get(RepairOrder, order_id)
        if not order:
            raise ValueError("Repair Order not found")
        if order.status not in OPEN_REPAIR_STATUSES:
            raise ValueError("Repair Order is closed")
        unit = session.get(CampaignUnit, order.campaign_unit_id)
        if unit and unit.condition == "truly-destroyed":
            raise ValueError("A truly destroyed unit cannot be repaired")
        campaign = session.get(Campaign, order.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        support = _active_support_percent(session, order.campaign_id)
        order.covered_amount = support_coverage(order.gross_cost, support)
        order.actual_cost = -(order.gross_cost - order.covered_amount)
        order.status = "completed"
        order.completed_at = datetime.now(UTC)
        if unit:
            remaining = [row for row in _open_repairs(session, unit.id) if row.id != order.id]
            if not remaining:
                unit.condition = "active"
                unit.damage_category = "none"
                unit.available = True
        session.flush()
        _post_wp(
            session,
            campaign,
            campaign_month=order.campaign_month,
            transaction_type="repair",
            description=f"Repair {order.damage_category}",
            gross_amount=-order.gross_cost,
            covered_amount=order.covered_amount,
            actual_amount=order.actual_cost,
            related_entity_type="repair_order",
            related_entity_id=order.id,
        )
        session.expunge(order)
        return order


def cancel_repair_order(order_id: int) -> RepairOrder:
    with session_scope() as session:
        order = session.get(RepairOrder, order_id)
        if not order:
            raise ValueError("Repair Order not found")
        if order.status not in OPEN_REPAIR_STATUSES:
            raise ValueError("Repair Order is closed")
        order.status = "cancelled"
        session.flush()
        session.expunge(order)
        return order


def reconfigure_omni_unit(
    campaign_unit_id: int,
    mul_raw: dict[str, Any],
    *,
    cost: int = 0,
) -> CampaignUnit:
    if cost < 0:
        raise ValueError("Reconfiguration cost must be zero or a positive WP amount")
    parsed = mul_service.parse_mul_unit(mul_raw)
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit:
            raise ValueError("Campaign unit not found")
        raw = json.loads(unit.mul_snapshot_json) if unit.mul_snapshot_json else None
        if not (unit.is_omni or unit_is_omni(raw, unit.variant)):
            raise ValueError("Only Omni units can change configuration")
        if not unit_is_fully_repaired(session, unit):
            raise ValueError("Unit must be fully repaired before Omni reconfiguration")
        campaign = session.get(Campaign, unit.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        previous = unit.variant
        snapshot = json.dumps(mul_raw)
        unit.mul_unit_id = parsed.id
        unit.variant = parsed.variant
        unit.class_name = parsed.class_name
        unit.tonnage = parsed.tonnage
        unit.point_value = parsed.point_value
        unit.unit_type_id = parsed.unit_type_id
        unit.unit_type_name = parsed.unit_type_name
        unit.display_name = parsed.name
        unit.mul_snapshot_json = snapshot
        unit.is_omni = True
        session.add(
            UnitConfigurationEvent(
                campaign_id=campaign.id,
                campaign_unit_id=unit.id,
                campaign_month=campaign.current_campaign_month,
                previous_variant=previous,
                new_variant=parsed.variant,
                mul_unit_id=parsed.id,
                mul_snapshot_json=snapshot,
                cost=cost,
            )
        )
        if cost:
            _post_wp(
                session,
                campaign,
                campaign_month=campaign.current_campaign_month,
                transaction_type="omni_reconfigure",
                description=f"Omni reconfiguration ({unit.chassis} {parsed.variant})",
                gross_amount=-cost,
                covered_amount=0,
                actual_amount=-cost,
                related_entity_type="campaign_unit",
                related_entity_id=unit.id,
            )
        session.flush()
        _ = unit.miniature
        session.expunge(unit)
        return unit


def reconfigure_omni_from_search(
    campaign_unit_id: int, mul_unit_id: int, *, cost: int = 0
) -> CampaignUnit:
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit:
            raise ValueError("Campaign unit not found")
        campaign = session.get(Campaign, unit.campaign_id)
        if not campaign or campaign.mul_faction_id is None or campaign.mul_era_id is None:
            raise ValueError("Set MUL faction and era on the campaign to change Omni loadouts")
        chassis = unit.chassis
        type_id = unit.unit_type_id
        faction_id = campaign.mul_faction_id
        era_id = campaign.mul_era_id
    raw = mul_service.find_unit_in_search_results(
        chassis,
        mul_unit_id,
        faction_id=faction_id,
        era_id=era_id,
        unit_type_id=type_id,
    )
    return reconfigure_omni_unit(campaign_unit_id, raw, cost=cost)


def preview_month_advance(campaign_id: int) -> dict[str, Any]:
    campaign = campaign_service.get_campaign_by_id(campaign_id)
    if not campaign:
        raise ValueError("Campaign not found")
    new_month = campaign.current_campaign_month + 1
    contract = contract_service.get_active_contract(campaign_id)
    contract_month = None
    if contract:
        contract_month = new_month - contract.start_campaign_month + 1
    arriving = [
        event
        for event in campaign.travel_events
        if event.status == "in_transit" and event.arrival_campaign_month == new_month
    ]
    in_transit = [event for event in campaign.travel_events if event.status == "in_transit"]
    with session_scope() as session:
        outstanding = (
            session.execute(
                select(RepairOrder).where(
                    RepairOrder.campaign_id == campaign_id,
                    RepairOrder.status.in_(OPEN_REPAIR_STATUSES),
                )
            )
            .scalars()
            .all()
        )
        wounded = (
            session.execute(
                select(CampaignPilot).where(
                    CampaignPilot.campaign_id == campaign_id,
                    CampaignPilot.wounded == True,  # noqa: E712
                    CampaignPilot.status == "alive",
                )
            )
            .scalars()
            .all()
        )
        outstanding_count = len(list(outstanding))
        wounded_names = [pilot.name for pilot in wounded]
    return {
        "current_month": campaign.current_campaign_month,
        "new_month": new_month,
        "month_label": campaign_service.campaign_month_label(campaign, new_month),
        "location": campaign_service.location_display(campaign),
        "warchest": campaign.warchest_balance,
        "active_contract": contract.contract_number if contract else None,
        "contract_month": contract_month,
        "in_transit": [f"{event.origin} → {event.destination}" for event in in_transit],
        "arriving": [f"{event.origin} → {event.destination}" for event in arriving],
        "outstanding_repairs": outstanding_count,
        "wounded_pilots": wounded_names,
    }


def advance_campaign_month(
    campaign_id: int, *, base_pay: int = 0, maintenance: int = 0
) -> Campaign:
    if base_pay < 0 or maintenance < 0:
        raise ValueError("Base Pay and maintenance must be zero or positive")
    preview = preview_month_advance(campaign_id)
    new_month = preview["new_month"]
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        campaign.current_campaign_month = new_month
        campaign.updated_at = datetime.now(UTC)
        if base_pay:
            _post_wp(
                session,
                campaign,
                campaign_month=new_month,
                transaction_type="base_pay",
                description=f"Base Pay for campaign month {new_month}",
                gross_amount=base_pay,
                covered_amount=0,
                actual_amount=base_pay,
                related_entity_type="campaign",
                related_entity_id=campaign.id,
            )
        if maintenance:
            _post_wp(
                session,
                campaign,
                campaign_month=new_month,
                transaction_type="maintenance",
                description=f"Maintenance for campaign month {new_month}",
                gross_amount=-maintenance,
                covered_amount=0,
                actual_amount=-maintenance,
                related_entity_type="campaign",
                related_entity_id=campaign.id,
            )
        arriving = list(
            session.execute(
                select(TravelEvent).where(
                    TravelEvent.campaign_id == campaign_id,
                    TravelEvent.status == "in_transit",
                    TravelEvent.arrival_campaign_month == new_month,
                )
            ).scalars()
        )
        for event in arriving:
            event.status = "arrived"
            campaign.current_location = event.destination
        session.flush()
        return campaign_service._expunge_campaign(session, campaign)
