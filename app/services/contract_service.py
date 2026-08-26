"""Contracts and Sorties for MechBay campaigns.

A Sortie is MechBay's term for one tabletop battle (a Track in Hot Spots /
Chaos Campaign terminology). Sorties require an active Contract. Units must be
committed to the Contract roster before they can be selected for a Sortie.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from sqlalchemy import func, select

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_lance import CampaignLance
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.contract import Contract
from ..models.contract_unit import ContractUnit
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from ..models.warchest_transaction import WarchestTransaction
from . import campaign_service, mul_service
from .campaign_service import GENERIC_AS_SKILL, pilot_is_available

logger = structlog.get_logger()

CONTRACT_STATUSES = ("draft", "active", "completed", "cancelled")
SORTIE_STATUSES = ("planning", "ready", "fought", "after_action", "closed")
SORTIE_OUTCOMES = ("victory", "loss", "draw", "inconclusive")
EDITABLE_SORTIE_STATUSES = {"planning"}
EDITABLE_CONTRACT_ROSTER_STATUSES = {"draft", "active"}
HISTORICAL_SORTIE_STATUSES = {"ready", "fought", "after_action", "closed"}
TRANSPORT_MODES = ("standard", "jump", "manual")


def round_half_up_sp(value: float | int | Decimal) -> int:
    """Round to nearest whole SP with half-up rounding (not banker's rounding)."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def transportation_coverage(gross_cost: int, transportation_percent: int) -> int:
    """Employer payment from a standard amount × percent, half-up to whole SP."""
    if gross_cost <= 0 or transportation_percent <= 0:
        return 0
    return round_half_up_sp(gross_cost * transportation_percent / 100)


def calculate_standard_transport(
    mode: str, *, scale: int, jump_count: int | None = None
) -> int:
    """Hot Spots standard or jump-tracked transportation amount."""
    _require_scale(scale)
    if mode == "standard":
        return 300 * scale
    if mode == "jump":
        if jump_count is None or jump_count < 1:
            raise ValueError("Jump-tracked transportation requires a jump count of at least 1")
        return (50 + (50 * jump_count)) * scale
    raise ValueError("Calculated transportation requires standard or jump mode")


def contract_pv_limit(scale: int) -> int:
    _require_scale(scale)
    return 150 * scale


def contract_unit_limit(scale: int) -> int:
    _require_scale(scale)
    return 3 * scale


def sortie_pv_limit(scale: int) -> int:
    _require_scale(scale)
    return 100 * scale


def sortie_unit_limit(scale: int) -> int:
    _require_scale(scale)
    return 3 * scale


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_scale(scale: int) -> None:
    if scale < 1 or scale > 5:
        raise ValueError("Scale must be between 1 and 5")


def _base_pay_percent(value: int) -> int:
    if value < 0 or value > 200:
        raise ValueError("Base Pay percentage must be between 0 and 200")
    return value


def _support_percent(value: int) -> int:
    if value < 0 or value > 100:
        raise ValueError("Support percentage must be between 0 and 100")
    return value


def _transportation_percent(value: int) -> int:
    if value < 0 or value > 100:
        raise ValueError("Transportation percentage must be between 0 and 100")
    return value


def _require_unit_pv(unit: CampaignUnit) -> int:
    if unit.point_value is None:
        raise ValueError(
            "This unit has no Alpha Strike Point Value and cannot be added to a campaign force."
        )
    return int(unit.point_value)


def _eager_load_contract(contract: Contract) -> None:
    _ = contract.campaign
    for roster in contract.roster_units:
        _ = roster.campaign_unit
        if roster.campaign_unit:
            _ = roster.campaign_unit.lance
            _ = roster.campaign_unit.miniature
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
    _base_pay_percent(base_pay_percent)
    _support_percent(support_percent)
    _transportation_percent(transportation_percent)
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
            contract.base_pay_percent = _base_pay_percent(base_pay_percent)
        if support_percent is not None:
            contract.support_percent = _support_percent(support_percent)
        if transportation_percent is not None:
            contract.transportation_percent = _transportation_percent(transportation_percent)
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
        _validate_contract_roster_limits(session, contract)
        for roster in contract.roster_units:
            unit = roster.campaign_unit
            if unit is None:
                continue
            clash = session.execute(
                select(ContractUnit)
                .join(Contract, ContractUnit.contract_id == Contract.id)
                .where(
                    ContractUnit.campaign_unit_id == unit.id,
                    Contract.status == "active",
                    Contract.id != contract.id,
                )
            ).scalar_one_or_none()
            if clash:
                raise ValueError(
                    f"{unit.chassis} is already committed to another active Contract"
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
    """Cancel a draft or active contract. Penalty SP is player-entered (positive cost)."""
    if penalty_wp < 0:
        raise ValueError("Cancel penalty must be zero or a positive SP cost")
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


def _contract_roster_totals(session, contract: Contract) -> tuple[int, int]:
    count = 0
    pv = 0
    for roster in contract.roster_units:
        unit = roster.campaign_unit or session.get(CampaignUnit, roster.campaign_unit_id)
        if not unit:
            continue
        count += 1
        pv += _require_unit_pv(unit)
    return count, pv


def _validate_contract_roster_limits(session, contract: Contract) -> None:
    count, pv = _contract_roster_totals(session, contract)
    max_units = contract_unit_limit(contract.scale)
    max_pv = contract_pv_limit(contract.scale)
    if count > max_units:
        raise ValueError(
            f"Contract force would be {count} / {max_units} units for Scale {contract.scale}"
        )
    if pv > max_pv:
        raise ValueError(
            f"Contract force would be {pv} / {max_pv} PV for Scale {contract.scale}"
        )


def contract_roster_summary(contract: Contract) -> dict[str, int]:
    units = [row.campaign_unit for row in contract.roster_units if row.campaign_unit]
    pv = sum(int(unit.point_value or 0) for unit in units if unit.point_value is not None)
    return {
        "unit_count": len(units),
        "unit_limit": contract_unit_limit(contract.scale),
        "pv_total": pv,
        "pv_limit": contract_pv_limit(contract.scale),
    }


def add_unit_to_contract_roster(contract_id: int, campaign_unit_id: int) -> ContractUnit:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status not in EDITABLE_CONTRACT_ROSTER_STATUSES:
            raise ValueError("Contract roster can only be edited while draft or active")
        unit = session.get(CampaignUnit, campaign_unit_id)
        if not unit or unit.campaign_id != contract.campaign_id:
            raise ValueError("Unit is not part of this campaign")
        pv = _require_unit_pv(unit)
        existing = session.execute(
            select(ContractUnit).where(
                ContractUnit.contract_id == contract_id,
                ContractUnit.campaign_unit_id == campaign_unit_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("Unit is already on this Contract roster")
        if contract.status == "active":
            clash = session.execute(
                select(ContractUnit)
                .join(Contract, ContractUnit.contract_id == Contract.id)
                .where(
                    ContractUnit.campaign_unit_id == campaign_unit_id,
                    Contract.status == "active",
                    Contract.id != contract.id,
                )
            ).scalar_one_or_none()
            if clash:
                raise ValueError("Unit is already committed to another active Contract")

        count, total_pv = _contract_roster_totals(session, contract)
        max_units = contract_unit_limit(contract.scale)
        max_pv = contract_pv_limit(contract.scale)
        if count + 1 > max_units:
            raise ValueError(
                f"Cannot add {unit.chassis}: Contract force would be "
                f"{count + 1} / {max_units} units"
            )
        if total_pv + pv > max_pv:
            raise ValueError(
                f"Cannot add {unit.chassis}: Contract force would be "
                f"{total_pv + pv} / {max_pv} PV"
            )
        order = session.execute(
            select(func.coalesce(func.max(ContractUnit.order), -1)).where(
                ContractUnit.contract_id == contract_id
            )
        ).scalar_one()
        row = ContractUnit(
            contract_id=contract_id,
            campaign_unit_id=campaign_unit_id,
            order=int(order) + 1,
        )
        session.add(row)
        session.flush()
        _ = row.campaign_unit
        session.expunge(row)
        return row


def add_lance_to_contract_roster(contract_id: int, campaign_lance_id: int) -> list[ContractUnit]:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status not in EDITABLE_CONTRACT_ROSTER_STATUSES:
            raise ValueError("Contract roster can only be edited while draft or active")
        lance = session.get(CampaignLance, campaign_lance_id)
        if not lance or lance.campaign_id != contract.campaign_id:
            raise ValueError("Lance is not part of this campaign")
        already = {
            row.campaign_unit_id
            for row in session.execute(
                select(ContractUnit).where(ContractUnit.contract_id == contract_id)
            ).scalars()
        }
        candidates = [unit for unit in lance.units if unit.id not in already]
        if not candidates:
            raise ValueError("All units from this lance are already on the Contract roster")
        for unit in candidates:
            _require_unit_pv(unit)
        count, total_pv = _contract_roster_totals(session, contract)
        add_pv = sum(int(unit.point_value or 0) for unit in candidates)
        max_units = contract_unit_limit(contract.scale)
        max_pv = contract_pv_limit(contract.scale)
        if count + len(candidates) > max_units:
            raise ValueError(
                f"Cannot add lance {lance.name}: Contract force would be "
                f"{count + len(candidates)} / {max_units} units"
            )
        if total_pv + add_pv > max_pv:
            raise ValueError(
                f"Cannot add lance {lance.name}: Contract force would be "
                f"{total_pv + add_pv} / {max_pv} PV"
            )
        if contract.status == "active":
            for unit in candidates:
                clash = session.execute(
                    select(ContractUnit)
                    .join(Contract, ContractUnit.contract_id == Contract.id)
                    .where(
                        ContractUnit.campaign_unit_id == unit.id,
                        Contract.status == "active",
                        Contract.id != contract.id,
                    )
                ).scalar_one_or_none()
                if clash:
                    raise ValueError(
                        f"{unit.chassis} is already committed to another active Contract"
                    )
        order = session.execute(
            select(func.coalesce(func.max(ContractUnit.order), -1)).where(
                ContractUnit.contract_id == contract_id
            )
        ).scalar_one()
        added: list[ContractUnit] = []
        next_order = int(order) + 1
        for unit in candidates:
            row = ContractUnit(
                contract_id=contract_id,
                campaign_unit_id=unit.id,
                order=next_order,
            )
            next_order += 1
            session.add(row)
            added.append(row)
        session.flush()
        for row in added:
            _ = row.campaign_unit
            session.expunge(row)
        return added


def remove_unit_from_contract_roster(contract_id: int, campaign_unit_id: int) -> bool:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if contract.status not in EDITABLE_CONTRACT_ROSTER_STATUSES:
            raise ValueError("Contract roster can only be edited while draft or active")
        row = session.execute(
            select(ContractUnit).where(
                ContractUnit.contract_id == contract_id,
                ContractUnit.campaign_unit_id == campaign_unit_id,
            )
        ).scalar_one_or_none()
        if not row:
            return False
        historical = session.execute(
            select(SortieUnit)
            .join(Sortie, SortieUnit.sortie_id == Sortie.id)
            .where(
                Sortie.contract_id == contract_id,
                SortieUnit.campaign_unit_id == campaign_unit_id,
                Sortie.status.in_(HISTORICAL_SORTIE_STATUSES),
            )
        ).scalar_one_or_none()
        if historical:
            raise ValueError(
                "Cannot remove a unit referenced by a Ready or later Sortie on this Contract"
            )
        planning = session.execute(
            select(SortieUnit)
            .join(Sortie, SortieUnit.sortie_id == Sortie.id)
            .where(
                Sortie.contract_id == contract_id,
                SortieUnit.campaign_unit_id == campaign_unit_id,
                Sortie.status == "planning",
            )
        ).scalar_one_or_none()
        if planning:
            raise ValueError("Remove this unit from the Planning Sortie first.")
        session.delete(row)
        return True


def unit_on_contract_roster(session, contract_id: int, campaign_unit_id: int) -> bool:
    return (
        session.execute(
            select(ContractUnit).where(
                ContractUnit.contract_id == contract_id,
                ContractUnit.campaign_unit_id == campaign_unit_id,
            )
        ).scalar_one_or_none()
        is not None
    )


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


def eligible_campaign_units(
    campaign_id: int, *, contract_id: int | None = None
) -> list[CampaignUnit]:
    with session_scope() as session:
        units = list(
            session.execute(
                select(CampaignUnit).where(CampaignUnit.campaign_id == campaign_id)
            ).scalars()
        )
        roster_ids: set[int] | None = None
        if contract_id is not None:
            roster_ids = {
                row.campaign_unit_id
                for row in session.execute(
                    select(ContractUnit).where(ContractUnit.contract_id == contract_id)
                ).scalars()
            }
        eligible = []
        for unit in units:
            if not unit_is_available(unit):
                continue
            if roster_ids is not None and unit.id not in roster_ids:
                continue
            if unit.point_value is None:
                continue
            eligible.append(unit)
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
        eligible = [pilot for pilot in pilots if pilot_is_available(pilot)]
        for pilot in eligible:
            _ = pilot.preferred_unit
            session.expunge(pilot)
        return eligible


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
        if pilot.id in taken_pilot_ids:
            continue
        if not pilot_is_available(pilot):
            continue
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
        if unit.point_value is None:
            raise ValueError(
                "This unit has no Alpha Strike Point Value and cannot be added to a campaign force."
            )
        if not unit_on_contract_roster(session, sortie.contract_id, campaign_unit_id):
            raise ValueError("Unit is not committed to this Contract roster")
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
        roster_ids = {
            row.campaign_unit_id
            for row in session.execute(
                select(ContractUnit).where(ContractUnit.contract_id == sortie.contract_id)
            ).scalars()
        }
        unit_ids = [
            unit.id
            for unit in lance.units
            if unit_is_available(unit)
            and unit.id in roster_ids
            and unit.point_value is not None
        ]
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
            if not pilot_is_available(pilot):
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
    sortie_unit_id: int,  # noqa: ARG001
    mul_raw: dict[str, Any],  # noqa: ARG001
    *,
    cost: int = 0,  # noqa: ARG001
) -> SortieUnit:
    """Omni loadouts are chosen between Sorties, not during Sortie prep."""
    raise ValueError("Omni reconfiguration is a between-sortie activity")


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
        contract = session.get(Contract, sortie.contract_id)
        if not contract:
            raise ValueError("Contract not found")
        if sortie.scale > contract.scale:
            raise ValueError("Sortie Scale cannot exceed Contract Scale")
        unit_count = len(sortie.units)
        max_units = sortie_unit_limit(sortie.scale)
        if unit_count > max_units:
            raise ValueError(
                f"Sortie force would be {unit_count} / {max_units} units for Scale {sortie.scale}"
            )
        pv_total = sum(int(row.point_value or 0) for row in sortie.units)
        max_pv = sortie_pv_limit(sortie.scale)
        if any(row.point_value is None for row in sortie.units):
            raise ValueError(
                "This unit has no Alpha Strike Point Value and cannot be added to a campaign force."
            )
        if pv_total > max_pv:
            raise ValueError(
                f"Sortie force would be {pv_total} / {max_pv} PV for Scale {sortie.scale}"
            )
        for row in sortie.units:
            if row.campaign_unit_id and not unit_on_contract_roster(
                session, sortie.contract_id, row.campaign_unit_id
            ):
                raise ValueError(f"{row.chassis} is not on this Contract roster")
            if not row.campaign_pilot_id:
                continue
            pilot = session.get(CampaignPilot, row.campaign_pilot_id)
            if pilot and not pilot_is_available(pilot):
                raise ValueError(f"{pilot.name} is not available")
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
    sortie_unit_id: int,  # noqa: ARG001
    mul_unit_id: int,  # noqa: ARG001
    *,
    cost: int = 0,  # noqa: ARG001
) -> SortieUnit:
    raise ValueError("Omni reconfiguration is a between-sortie activity")
