"""Contracts and Sorties for MechBay campaigns.

A Sortie is MechBay's term for one tabletop battle (a Track in Hot Spots /
Chaos Campaign terminology). Sorties require an active Contract. The Campaign
roster is the Contract force; players pick lances or individuals per Sortie.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_lance import CampaignLance
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.contract import Contract
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from ..models.warchest_transaction import WarchestTransaction
from . import campaign_service, mul_service
from .campaign_service import GENERIC_AS_SKILL, unit_is_omni

logger = structlog.get_logger()

CONTRACT_STATUSES = ("draft", "active", "completed", "cancelled")
SORTIE_STATUSES = ("planning", "ready", "fought", "after_action", "closed")
SORTIE_OUTCOMES = ("victory", "loss", "draw", "inconclusive")
EDITABLE_SORTIE_STATUSES = {"planning"}


def transportation_coverage(gross_cost: int, transportation_percent: int) -> int:
    """Employer coverage of a transportation expense: percent of gross, rounded."""
    if gross_cost <= 0 or transportation_percent <= 0:
        return 0
    return int(round(gross_cost * transportation_percent / 100))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_scale(scale: int) -> None:
    if scale < 1 or scale > 5:
        raise ValueError("Scale must be between 1 and 5")


def _percent(value: int, label: str) -> int:
    if value < 0 or value > 100:
        raise ValueError(f"{label} must be between 0 and 100")
    return value


def _eager_load_contract(contract: Contract) -> None:
    _ = contract.campaign
    for sortie in contract.sorties:
        for unit in sortie.units:
            _ = unit.campaign_unit
            _ = unit.campaign_pilot
    _ = contract.travel_events


def _expunge_contract(session, contract: Contract) -> Contract:
    _eager_load_contract(contract)
    session.expunge(contract)
    return contract


def _eager_load_sortie(sortie: Sortie) -> None:
    _ = sortie.contract
    _ = sortie.campaign
    for unit in sortie.units:
        _ = unit.campaign_unit
        _ = unit.campaign_pilot


def _expunge_sortie(session, sortie: Sortie) -> Sortie:
    _eager_load_sortie(sortie)
    session.expunge(sortie)
    return sortie


def next_contract_number(campaign_id: int) -> str:
    with session_scope() as session:
        numbers = list(
            session.execute(
                select(Contract.contract_number).where(Contract.campaign_id == campaign_id)
            ).scalars()
        )
    taken = set(numbers)
    index = 1
    while f"C-{index:03d}" in taken:
        index += 1
    return f"C-{index:03d}"


def get_contract_by_id(contract_id: int) -> Contract | None:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if contract:
            return _expunge_contract(session, contract)
        return None


def get_active_contract(campaign_id: int) -> Contract | None:
    with session_scope() as session:
        contract = session.execute(
            select(Contract).where(Contract.campaign_id == campaign_id, Contract.status == "active")
        ).scalar_one_or_none()
        if contract:
            return _expunge_contract(session, contract)
        return None


def get_contracts_for_campaign(campaign_id: int) -> list[Contract]:
    with session_scope() as session:
        contracts = list(
            session.execute(
                select(Contract)
                .where(Contract.campaign_id == campaign_id)
                .order_by(Contract.id.desc())
            )
            .scalars()
            .all()
        )
        for contract in contracts:
            _eager_load_contract(contract)
            session.expunge(contract)
        return contracts


def create_contract(
    campaign_id: int,
    name: str,
    *,
    contract_number: str | None = None,
    employer: str | None = None,
    destination: str | None = None,
    type_of_action: str | None = None,
    scale: int | None = None,
    length_months: int = 1,
    start_campaign_month: int | None = None,
    end_campaign_month: int | None = None,
    base_pay_percent: int = 0,
    support_percent: int = 0,
    transportation_percent: int = 0,
    salvage_rights: str | None = None,
    command_rights: str | None = None,
    notes: str | None = None,
) -> Contract:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Contract name is required")
    if length_months < 1:
        raise ValueError("Contract length must be at least 1 month")
    _percent(base_pay_percent, "Base Pay percentage")
    _percent(support_percent, "Support percentage")
    _percent(transportation_percent, "Transportation percentage")
    number = (contract_number or "").strip() or next_contract_number(campaign_id)

    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        resolved_scale = campaign.scale if scale is None else scale
        _require_scale(resolved_scale)
        start = (
            start_campaign_month
            if start_campaign_month is not None
            else campaign.current_campaign_month
        )
        if start < 1:
            raise ValueError("Start campaign month must be 1 or greater")
        end = end_campaign_month if end_campaign_month is not None else start + length_months - 1
        if end < start:
            raise ValueError("End month cannot be before start month")
        if session.execute(
            select(Contract).where(
                Contract.campaign_id == campaign_id, Contract.contract_number == number
            )
        ).scalar_one_or_none():
            raise ValueError(f"Contract number {number} is already used")

        contract = Contract(
            campaign_id=campaign_id,
            name=cleaned,
            contract_number=number,
            employer=_blank_to_none(employer),
            destination=_blank_to_none(destination),
            type_of_action=_blank_to_none(type_of_action),
            scale=resolved_scale,
            length_months=length_months,
            start_campaign_month=start,
            end_campaign_month=end,
            base_pay_percent=base_pay_percent,
            support_percent=support_percent,
            transportation_percent=transportation_percent,
            salvage_rights=_blank_to_none(salvage_rights),
            command_rights=_blank_to_none(command_rights),
            status="draft",
            notes=_blank_to_none(notes),
        )
        session.add(contract)
        session.flush()
        return _expunge_contract(session, contract)


def update_contract(
    contract_id: int,
    *,
    name: str | None = None,
    contract_number: str | None = None,
    employer: str | None | object = ...,
    destination: str | None | object = ...,
    type_of_action: str | None | object = ...,
    scale: int | None = None,
    length_months: int | None = None,
    start_campaign_month: int | None = None,
    end_campaign_month: int | None = None,
    base_pay_percent: int | None = None,
    support_percent: int | None = None,
    transportation_percent: int | None = None,
    salvage_rights: str | None | object = ...,
    command_rights: str | None | object = ...,
    notes: str | None | object = ...,
) -> Contract | None:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            return None
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Contract name is required")
            contract.name = cleaned
        if contract_number is not None:
            number = contract_number.strip()
            if not number:
                raise ValueError("Contract number is required")
            clash = session.execute(
                select(Contract).where(
                    Contract.campaign_id == contract.campaign_id,
                    Contract.contract_number == number,
                    Contract.id != contract.id,
                )
            ).scalar_one_or_none()
            if clash:
                raise ValueError(f"Contract number {number} is already used")
            contract.contract_number = number
        if employer is not ...:
            contract.employer = _blank_to_none(employer if isinstance(employer, str) else None)
        if destination is not ...:
            contract.destination = _blank_to_none(
                destination if isinstance(destination, str) else None
            )
        if type_of_action is not ...:
            contract.type_of_action = _blank_to_none(
                type_of_action if isinstance(type_of_action, str) else None
            )
        if scale is not None:
            _require_scale(scale)
            contract.scale = scale
        if length_months is not None:
            if length_months < 1:
                raise ValueError("Contract length must be at least 1 month")
            contract.length_months = length_months
        if start_campaign_month is not None:
            if start_campaign_month < 1:
                raise ValueError("Start campaign month must be 1 or greater")
            contract.start_campaign_month = start_campaign_month
        if end_campaign_month is not None:
            contract.end_campaign_month = end_campaign_month
        if contract.end_campaign_month < contract.start_campaign_month:
            raise ValueError("End month cannot be before start month")
        if base_pay_percent is not None:
            contract.base_pay_percent = _percent(base_pay_percent, "Base Pay percentage")
        if support_percent is not None:
            contract.support_percent = _percent(support_percent, "Support percentage")
        if transportation_percent is not None:
            contract.transportation_percent = _percent(
                transportation_percent, "Transportation percentage"
            )
        if salvage_rights is not ...:
            contract.salvage_rights = _blank_to_none(
                salvage_rights if isinstance(salvage_rights, str) else None
            )
        if command_rights is not ...:
            contract.command_rights = _blank_to_none(
                command_rights if isinstance(command_rights, str) else None
            )
        if notes is not ...:
            contract.notes = _blank_to_none(notes if isinstance(notes, str) else None)
        contract.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_contract(session, contract)


def activate_contract(contract_id: int) -> Contract:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status == "active":
            return _expunge_contract(session, contract)
        if contract.status != "draft":
            raise ValueError("Only a draft contract can be activated")
        existing = session.execute(
            select(Contract).where(
                Contract.campaign_id == contract.campaign_id,
                Contract.status == "active",
                Contract.id != contract.id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Contract {existing.contract_number} is already active. "
                "Complete or cancel it first."
            )
        contract.status = "active"
        contract.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_contract(session, contract)


def complete_contract(contract_id: int) -> Contract:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status != "active":
            raise ValueError("Only an active contract can be completed")
        contract.status = "completed"
        contract.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_contract(session, contract)


def cancel_contract(
    contract_id: int, *, penalty_wp: int = 0, reputation_delta: int = 0
) -> Contract:
    """Cancel a draft or active contract. Penalty WP is player-entered (positive cost)."""
    if penalty_wp < 0:
        raise ValueError("Cancel penalty must be zero or a positive WP cost")
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status in {"completed", "cancelled"}:
            raise ValueError("Contract is already closed")
        campaign = session.get(Campaign, contract.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        if penalty_wp:
            new_balance = campaign.warchest_balance - penalty_wp
            session.add(
                WarchestTransaction(
                    campaign_id=campaign.id,
                    campaign_month=campaign.current_campaign_month,
                    transaction_type="contract_cancel",
                    description=f"Cancel penalty for {contract.contract_number}",
                    gross_amount=-penalty_wp,
                    covered_amount=0,
                    actual_amount=-penalty_wp,
                    resulting_balance=new_balance,
                    related_entity_type="contract",
                    related_entity_id=contract.id,
                )
            )
            campaign.warchest_balance = new_balance
        if reputation_delta:
            campaign.reputation += reputation_delta
        contract.status = "cancelled"
        contract.updated_at = datetime.now(UTC)
        campaign.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_contract(session, contract)


def get_sortie_by_id(sortie_id: int) -> Sortie | None:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if sortie:
            return _expunge_sortie(session, sortie)
        return None


def create_sortie(
    contract_id: int,
    name: str,
    *,
    scale: int | None = None,
    campaign_month: int | None = None,
    scenario_type: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> Sortie:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Sortie name is required")
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status != "active":
            raise ValueError("Sorties require an active contract")
        campaign = session.get(Campaign, contract.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        resolved_scale = contract.scale if scale is None else scale
        _require_scale(resolved_scale)
        if resolved_scale > contract.scale:
            raise ValueError("Sortie Scale cannot exceed Contract Scale")
        month = campaign_month if campaign_month is not None else campaign.current_campaign_month
        if month < 1:
            raise ValueError("Campaign month must be 1 or greater")
        sortie = Sortie(
            campaign_id=campaign.id,
            contract_id=contract.id,
            name=cleaned,
            campaign_month=month,
            scale=resolved_scale,
            scenario_type=_blank_to_none(scenario_type),
            location=_blank_to_none(location) or contract.destination,
            notes=_blank_to_none(notes),
            status="planning",
        )
        session.add(sortie)
        session.flush()
        return _expunge_sortie(session, sortie)


def update_sortie(
    sortie_id: int,
    *,
    name: str | None = None,
    scale: int | None = None,
    campaign_month: int | None = None,
    scenario_type: str | None | object = ...,
    location: str | None | object = ...,
    notes: str | None | object = ...,
) -> Sortie | None:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            return None
        if sortie.status not in EDITABLE_SORTIE_STATUSES and scale is not None:
            raise ValueError("Sortie force is locked")
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Sortie name is required")
            sortie.name = cleaned
        if scale is not None:
            _require_scale(scale)
            contract = session.get(Contract, sortie.contract_id)
            if contract and scale > contract.scale:
                raise ValueError("Sortie Scale cannot exceed Contract Scale")
            sortie.scale = scale
        if campaign_month is not None:
            if campaign_month < 1:
                raise ValueError("Campaign month must be 1 or greater")
            sortie.campaign_month = campaign_month
        if scenario_type is not ...:
            sortie.scenario_type = _blank_to_none(
                scenario_type if isinstance(scenario_type, str) else None
            )
        if location is not ...:
            sortie.location = _blank_to_none(location if isinstance(location, str) else None)
        if notes is not ...:
            sortie.notes = _blank_to_none(notes if isinstance(notes, str) else None)
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_sortie(session, sortie)


def unit_is_available(unit: CampaignUnit) -> bool:
    return bool(unit.available) and unit.condition not in {"destroyed", "truly-destroyed"}


def eligible_campaign_units(campaign_id: int) -> list[CampaignUnit]:
    with session_scope() as session:
        units = list(
            session.execute(
                select(CampaignUnit).where(CampaignUnit.campaign_id == campaign_id)
            ).scalars()
        )
        eligible = [unit for unit in units if unit_is_available(unit)]
        for unit in eligible:
            _ = unit.lance
            _ = unit.miniature
            session.expunge(unit)
        return eligible


def eligible_named_pilots(campaign_id: int) -> list[CampaignPilot]:
    with session_scope() as session:
        pilots = list(
            session.execute(
                select(CampaignPilot).where(
                    CampaignPilot.campaign_id == campaign_id,
                    CampaignPilot.status == "alive",
                )
            ).scalars()
        )
        for pilot in pilots:
            _ = pilot.preferred_unit
            session.expunge(pilot)
        return pilots


def _preferred_pilot_for_unit(session, unit: CampaignUnit, taken_pilot_ids: set[int]):
    pilots = list(
        session.execute(
            select(CampaignPilot).where(
                CampaignPilot.campaign_id == unit.campaign_id,
                CampaignPilot.preferred_unit_id == unit.id,
                CampaignPilot.status == "alive",
            )
        ).scalars()
    )
    for pilot in pilots:
        if pilot.id not in taken_pilot_ids:
            return pilot
    return None


def _snapshot_pilot_fields(row: SortieUnit, pilot: CampaignPilot | None) -> None:
    if pilot is None:
        row.campaign_pilot_id = None
        row.pilot_name = "Generic crew"
        row.pilot_callsign = None
        row.gunnery = GENERIC_AS_SKILL
        row.piloting = GENERIC_AS_SKILL
        row.alpha_strike_skill = GENERIC_AS_SKILL
        row.is_generic_crew = True
        return
    row.campaign_pilot_id = pilot.id
    row.pilot_name = pilot.name
    row.pilot_callsign = pilot.callsign
    row.gunnery = pilot.gunnery
    row.piloting = pilot.piloting
    row.alpha_strike_skill = pilot.alpha_strike_skill
    row.is_generic_crew = False


def _copy_unit_config(row: SortieUnit, unit: CampaignUnit) -> None:
    row.prefix = unit.prefix
    row.chassis = unit.chassis
    row.mul_unit_id = unit.mul_unit_id
    row.variant = unit.variant
    row.class_name = unit.class_name
    row.tonnage = unit.tonnage
    row.point_value = unit.point_value
    row.unit_type_id = unit.unit_type_id
    row.unit_type_name = unit.unit_type_name
    row.display_name = unit.display_name
    row.mul_snapshot_json = unit.mul_snapshot_json
    row.is_omni = unit.is_omni


def add_unit_to_sortie(sortie_id: int, campaign_unit_id: int) -> SortieUnit:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status not in EDITABLE_SORTIE_STATUSES:
            raise ValueError("Sortie force is locked")
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit or unit.campaign_id != sortie.campaign_id:
            raise ValueError("Unit is not part of this campaign")
        if not unit_is_available(unit):
            raise ValueError("Unit is not currently available")
        existing = session.execute(
            select(SortieUnit).where(
                SortieUnit.sortie_id == sortie_id,
                SortieUnit.campaign_unit_id == campaign_unit_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("Unit is already in this Sortie")
        taken_pilots = {
            row.campaign_pilot_id for row in sortie.units if row.campaign_pilot_id is not None
        }
        lance = (
            session.get(CampaignLance, unit.campaign_lance_id) if unit.campaign_lance_id else None
        )
        order = session.execute(
            select(func.coalesce(func.max(SortieUnit.order), -1)).where(
                SortieUnit.sortie_id == sortie_id
            )
        ).scalar_one()
        row = SortieUnit(
            sortie_id=sortie_id,
            campaign_unit_id=unit.id,
            campaign_lance_id=unit.campaign_lance_id,
            lance_name=lance.name if lance else None,
            order=int(order) + 1,
        )
        _copy_unit_config(row, unit)
        preferred = _preferred_pilot_for_unit(session, unit, taken_pilots)
        _snapshot_pilot_fields(row, preferred)
        session.add(row)
        session.flush()
        session.expunge(row)
        return row


def add_lance_to_sortie(sortie_id: int, campaign_lance_id: int) -> list[SortieUnit]:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        lance = session.get(CampaignLance, campaign_lance_id)
        if not lance or lance.campaign_id != sortie.campaign_id:
            raise ValueError("Lance is not part of this campaign")
        unit_ids = [unit.id for unit in lance.units if unit_is_available(unit)]
    added: list[SortieUnit] = []
    for unit_id in unit_ids:
        try:
            added.append(add_unit_to_sortie(sortie_id, unit_id))
        except ValueError:
            continue
    return added


def remove_sortie_unit(sortie_unit_id: int) -> bool:
    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        if not row:
            return False
        sortie = session.get(Sortie, row.sortie_id)
        if sortie and sortie.status not in EDITABLE_SORTIE_STATUSES:
            raise ValueError("Sortie force is locked")
        session.delete(row)
        return True


def assign_sortie_pilot(sortie_unit_id: int, campaign_pilot_id: int | None) -> SortieUnit:
    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        if not row:
            raise ValueError("Sortie unit not found")
        sortie = session.get(Sortie, row.sortie_id)
        if not sortie or sortie.status not in EDITABLE_SORTIE_STATUSES:
            raise ValueError("Sortie force is locked")
        if campaign_pilot_id is None:
            _snapshot_pilot_fields(row, None)
        else:
            pilot = session.get(CampaignPilot, campaign_pilot_id)
            if not pilot or pilot.campaign_id != sortie.campaign_id:
                raise ValueError("Pilot is not part of this campaign")
            if pilot.status != "alive":
                raise ValueError("Pilot is not available")
            clash = session.execute(
                select(SortieUnit).where(
                    SortieUnit.sortie_id == sortie.id,
                    SortieUnit.campaign_pilot_id == campaign_pilot_id,
                    SortieUnit.id != row.id,
                )
            ).scalar_one_or_none()
            if clash:
                raise ValueError("Named pilots can only crew one unit in a Sortie")
            _snapshot_pilot_fields(row, pilot)
        session.flush()
        session.expunge(row)
        return row


def apply_sortie_unit_configuration(
    sortie_unit_id: int,
    mul_raw: dict[str, Any],
    *,
    cost: int = 0,
) -> SortieUnit:
    """Set the Omni loadout used for this Sortie. Cost is player-entered WP."""
    if cost < 0:
        raise ValueError("Reconfiguration cost must be zero or a positive WP amount")
    parsed = mul_service.parse_mul_unit(mul_raw)
    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        if not row:
            raise ValueError("Sortie unit not found")
        sortie = session.get(Sortie, row.sortie_id)
        if not sortie or sortie.status not in EDITABLE_SORTIE_STATUSES:
            raise ValueError("Sortie force is locked")
        unit = session.get(CampaignUnit, row.campaign_unit_id) if row.campaign_unit_id else None
        is_omni = row.is_omni or (unit.is_omni if unit else False)
        if unit:
            is_omni = is_omni or unit_is_omni(
                json.loads(unit.mul_snapshot_json) if unit.mul_snapshot_json else None,
                unit.variant,
            )
        if not is_omni:
            raise ValueError("Only Omni units can change configuration")
        unchanged = row.mul_unit_id == parsed.id and (row.variant or "") == (parsed.variant or "")
        snapshot = json.dumps(mul_raw)
        row.mul_unit_id = parsed.id
        row.variant = parsed.variant
        row.class_name = parsed.class_name
        row.tonnage = parsed.tonnage
        row.point_value = parsed.point_value
        row.unit_type_id = parsed.unit_type_id
        row.unit_type_name = parsed.unit_type_name
        row.display_name = parsed.name
        row.mul_snapshot_json = snapshot
        row.is_omni = True
        if unit:
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
        applied_cost = 0 if unchanged else cost
        row.configuration_changed = not unchanged
        row.reconfiguration_cost = applied_cost
        if applied_cost:
            campaign = session.get(Campaign, sortie.campaign_id)
            if campaign:
                new_balance = campaign.warchest_balance - applied_cost
                session.add(
                    WarchestTransaction(
                        campaign_id=campaign.id,
                        campaign_month=sortie.campaign_month,
                        transaction_type="omni_reconfigure",
                        description=f"Omni reconfiguration ({row.chassis} {parsed.variant})",
                        gross_amount=-applied_cost,
                        covered_amount=0,
                        actual_amount=-applied_cost,
                        resulting_balance=new_balance,
                        related_entity_type="sortie",
                        related_entity_id=sortie.id,
                    )
                )
                campaign.warchest_balance = new_balance
        session.flush()
        session.expunge(row)
        return row


def sortie_point_total(sortie: Sortie) -> int:
    return sum(unit.point_value or 0 for unit in sortie.units)


def mark_sortie_ready(sortie_id: int) -> Sortie:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status != "planning":
            raise ValueError("Only a planning Sortie can be marked Ready")
        if not sortie.units:
            raise ValueError("Select at least one unit before marking Ready")
        sortie.status = "ready"
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_sortie(session, sortie)


def reopen_sortie_planning(sortie_id: int) -> Sortie:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status != "ready":
            raise ValueError("Only a Ready Sortie can return to Planning")
        sortie.status = "planning"
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_sortie(session, sortie)


def mark_sortie_fought(sortie_id: int, outcome: str | None = None) -> Sortie:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            raise ValueError("Sortie not found")
        if sortie.status != "ready":
            raise ValueError("Mark the Sortie Ready before recording that it was fought")
        if outcome:
            if outcome not in SORTIE_OUTCOMES:
                raise ValueError("Invalid Sortie outcome")
            sortie.outcome = outcome
        sortie.status = "fought"
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        return _expunge_sortie(session, sortie)


def search_omni_variants(campaign_id: int, campaign_unit_id: int) -> list[dict[str, Any]]:
    campaign = campaign_service.get_campaign_by_id(campaign_id)
    if not campaign or campaign.mul_faction_id is None or campaign.mul_era_id is None:
        raise ValueError("Set MUL faction and era on the campaign to search Omni configurations")
    with session_scope() as session:
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit or unit.campaign_id != campaign_id:
            raise ValueError("Unit not found")
        chassis = unit.chassis
        type_id = unit.unit_type_id or mul_service.map_miniature_type_to_mul(unit.type)
    return mul_service.search_variants(
        chassis,
        faction_id=campaign.mul_faction_id,
        era_id=campaign.mul_era_id,
        unit_type_id=type_id,
    )


def apply_omni_from_search(
    sortie_unit_id: int,
    mul_unit_id: int,
    *,
    cost: int = 0,
) -> SortieUnit:
    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        if not row:
            raise ValueError("Sortie unit not found")
        sortie = session.get(Sortie, row.sortie_id)
        campaign = session.get(Campaign, sortie.campaign_id) if sortie else None
        if not campaign or campaign.mul_faction_id is None or campaign.mul_era_id is None:
            raise ValueError("Set MUL faction and era on the campaign to change Omni loadouts")
        chassis = row.chassis
        type_id = row.unit_type_id
        faction_id = campaign.mul_faction_id
        era_id = campaign.mul_era_id
    raw = mul_service.find_unit_in_search_results(
        chassis,
        mul_unit_id,
        faction_id=faction_id,
        era_id=era_id,
        unit_type_id=type_id,
    )
    return apply_sortie_unit_configuration(sortie_unit_id, raw, cost=cost)
