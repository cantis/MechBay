"""Alpha Strike force configuration and variant assignment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select

from ..extensions import session_scope
from ..models.alpha_strike_assignment import AlphaStrikeAssignment
from ..models.alpha_strike_force import AlphaStrikeForce
from ..models.force import Force
from ..models.force_miniature import ForceMiniature
from . import mul_service

logger = structlog.get_logger()

DEFAULT_FUDGE_PERCENT = 2


@dataclass
class BudgetStatus:
    total_pv: int
    configured_count: int
    unconfigured_count: int
    point_budget: int | None
    fudge_percent: int
    effective_budget: int | None
    status: str  # none | under | within | over_fudge | over_hard

    def to_dict(self) -> dict:
        return {
            "total_pv": self.total_pv,
            "configured_count": self.configured_count,
            "unconfigured_count": self.unconfigured_count,
            "point_budget": self.point_budget,
            "fudge_percent": self.fudge_percent,
            "effective_budget": self.effective_budget,
            "status": self.status,
        }


def compute_budget_status(
    total_pv: int,
    configured_count: int,
    unconfigured_count: int,
    point_budget: int | None,
    fudge_percent: int = DEFAULT_FUDGE_PERCENT,
) -> BudgetStatus:
    if point_budget is None:
        return BudgetStatus(
            total_pv=total_pv,
            configured_count=configured_count,
            unconfigured_count=unconfigured_count,
            point_budget=None,
            fudge_percent=fudge_percent,
            effective_budget=None,
            status="none",
        )

    effective = int(point_budget * (1 + fudge_percent / 100))
    if total_pv <= point_budget:
        status = "within" if total_pv > 0 else "under"
    elif total_pv <= effective:
        status = "over_fudge"
    else:
        status = "over_hard"

    return BudgetStatus(
        total_pv=total_pv,
        configured_count=configured_count,
        unconfigured_count=unconfigured_count,
        point_budget=point_budget,
        fudge_percent=fudge_percent,
        effective_budget=effective,
        status=status,
    )


def get_alpha_strike_force(force_id: int) -> AlphaStrikeForce | None:
    with session_scope() as session:
        stmt = select(AlphaStrikeForce).where(AlphaStrikeForce.force_id == force_id)
        row = session.execute(stmt).scalar_one_or_none()
        if row:
            session.expunge(row)
        return row


def get_mul_filters_for_force(force_id: int) -> tuple[int, int] | None:
    """Return MUL faction and era IDs when Alpha Strike is configured for the force."""
    as_force = get_alpha_strike_force(force_id)
    if not as_force:
        return None
    return as_force.mul_faction_id, as_force.mul_era_id


def enable_alpha_strike(
    force_id: int,
    *,
    mul_faction_id: int,
    mul_era_id: int,
    point_budget: int | None = None,
    fudge_percent: int = DEFAULT_FUDGE_PERCENT,
) -> AlphaStrikeForce:
    faction = mul_service.get_faction_by_id(mul_faction_id)
    era = mul_service.get_era_by_id(mul_era_id)
    if not faction:
        raise ValueError("Invalid faction")
    if not era:
        raise ValueError("Invalid era")

    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            raise ValueError("Force not found")

        existing = session.execute(
            select(AlphaStrikeForce).where(AlphaStrikeForce.force_id == force_id)
        ).scalar_one_or_none()

        if existing:
            existing.mul_faction_id = mul_faction_id
            existing.mul_era_id = mul_era_id
            existing.faction_name = faction["name"]
            existing.era_name = era["name"]
            existing.point_budget = point_budget
            existing.fudge_percent = fudge_percent
            row = existing
        else:
            row = AlphaStrikeForce(
                force_id=force_id,
                mul_faction_id=mul_faction_id,
                mul_era_id=mul_era_id,
                faction_name=faction["name"],
                era_name=era["name"],
                point_budget=point_budget,
                fudge_percent=fudge_percent,
            )
            session.add(row)

        session.flush()
        logger.info(
            "alpha_strike_enabled",
            force_id=force_id,
            faction=faction["name"],
            era=era["name"],
        )
        session.expunge(row)
        return row


def update_config(
    force_id: int,
    *,
    point_budget: int | None = ...,  # type: ignore[assignment]
    fudge_percent: int | None = None,
) -> AlphaStrikeForce | None:
    with session_scope() as session:
        row = session.execute(
            select(AlphaStrikeForce).where(AlphaStrikeForce.force_id == force_id)
        ).scalar_one_or_none()
        if not row:
            return None
        if point_budget is not ...:
            row.point_budget = point_budget
        if fudge_percent is not None:
            row.fudge_percent = fudge_percent
        session.flush()
        session.expunge(row)
        return row


def get_assignments_for_force(force_id: int) -> dict[int, AlphaStrikeAssignment]:
    """Return assignments keyed by force_miniature_id."""
    with session_scope() as session:
        force = session.get(Force, force_id)
        if not force:
            return {}
        fm_ids = [fm.id for lance in force.lances for fm in lance.miniatures]
        if not fm_ids:
            return {}
        stmt = select(AlphaStrikeAssignment).where(
            AlphaStrikeAssignment.force_miniature_id.in_(fm_ids)
        )
        rows = list(session.execute(stmt).scalars().all())
        for row in rows:
            session.expunge(row)
        return {row.force_miniature_id: row for row in rows}


def get_force_summary(force_id: int) -> BudgetStatus:
    force = _get_force_with_slots(force_id)
    as_force = get_alpha_strike_force(force_id)
    if not force or not as_force:
        return compute_budget_status(0, 0, 0, None)

    configured = 0
    unconfigured = 0
    total_pv = 0
    assignments = get_assignments_for_force(force_id)

    for lance in force.lances:
        for fm in lance.miniatures:
            assignment = assignments.get(fm.id)
            if assignment:
                configured += 1
                total_pv += assignment.point_value
            else:
                unconfigured += 1

    return compute_budget_status(
        total_pv,
        configured,
        unconfigured,
        as_force.point_budget,
        as_force.fudge_percent,
    )


def get_lance_pv_totals(force_id: int) -> dict[int, int]:
    """Return configured Alpha Strike PV sum per lance id."""
    force = _get_force_with_slots(force_id)
    if not force:
        return {}

    assignments = get_assignments_for_force(force_id)
    totals: dict[int, int] = {}
    for lance in force.lances:
        totals[lance.id] = sum(
            assignments[fm.id].point_value for fm in lance.miniatures if fm.id in assignments
        )
    return totals


def _get_force_with_slots(force_id: int) -> Force | None:
    with session_scope() as session:
        force = session.get(Force, force_id)
        if force:
            for lance in force.lances:
                _ = lance.miniatures
            session.expunge(force)
        return force


def assign_variant(
    force_id: int,
    force_miniature_id: int,
    mul_unit_id: int,
    *,
    search_name: str,
    unit_type_id: int | None = None,
) -> AlphaStrikeAssignment:
    as_force = get_alpha_strike_force(force_id)
    if not as_force:
        raise ValueError("Alpha Strike is not configured for this force")

    raw = mul_service.find_unit_in_search_results(
        search_name,
        mul_unit_id,
        faction_id=as_force.mul_faction_id,
        era_id=as_force.mul_era_id,
        unit_type_id=unit_type_id,
    )
    unit = mul_service.parse_mul_unit(raw)

    with session_scope() as session:
        fm = session.get(ForceMiniature, force_miniature_id)
        if not fm:
            raise ValueError("Invalid force miniature")
        _ = fm.lance
        if fm.lance.force_id != force_id:
            raise ValueError("Invalid force miniature")

        existing = session.execute(
            select(AlphaStrikeAssignment).where(
                AlphaStrikeAssignment.force_miniature_id == force_miniature_id
            )
        ).scalar_one_or_none()

        if existing:
            existing.mul_unit_id = unit.id
            existing.variant = unit.variant
            existing.class_name = unit.class_name
            existing.tonnage = unit.tonnage
            existing.point_value = unit.point_value
            existing.unit_type_id = unit.unit_type_id
            existing.unit_type_name = unit.unit_type_name
            existing.display_name = unit.name
            existing.mul_snapshot_json = json.dumps(raw)
            row = existing
        else:
            row = AlphaStrikeAssignment(
                force_miniature_id=force_miniature_id,
                mul_unit_id=unit.id,
                variant=unit.variant,
                class_name=unit.class_name,
                tonnage=unit.tonnage,
                point_value=unit.point_value,
                unit_type_id=unit.unit_type_id,
                unit_type_name=unit.unit_type_name,
                display_name=unit.name,
                mul_snapshot_json=json.dumps(raw),
            )
            session.add(row)

        session.flush()
        logger.info(
            "alpha_strike_variant_assigned",
            force_id=force_id,
            force_miniature_id=force_miniature_id,
            variant=unit.variant,
            point_value=unit.point_value,
        )
        session.expunge(row)
        return row


def clear_assignment(force_id: int, force_miniature_id: int) -> bool:
    with session_scope() as session:
        fm = session.get(ForceMiniature, force_miniature_id)
        if not fm:
            return False
        _ = fm.lance
        if fm.lance.force_id != force_id:
            return False
        assignment = session.execute(
            select(AlphaStrikeAssignment).where(
                AlphaStrikeAssignment.force_miniature_id == force_miniature_id
            )
        ).scalar_one_or_none()
        if not assignment:
            return False
        session.delete(assignment)
        return True


def search_variants_for_slot(
    force_id: int,
    force_miniature_id: int,
) -> list[dict[str, Any]]:
    as_force = get_alpha_strike_force(force_id)
    if not as_force:
        raise ValueError("Alpha Strike is not configured for this force")

    with session_scope() as session:
        fm = session.get(ForceMiniature, force_miniature_id)
        if not fm:
            raise ValueError("Invalid force miniature")
        _ = fm.lance
        if fm.lance.force_id != force_id:
            raise ValueError("Invalid force miniature")
        session.expunge(fm.miniature)
        miniature = fm.miniature

    type_id = mul_service.map_miniature_type_to_mul(miniature.type)
    return mul_service.search_variants(
        miniature.chassis,
        faction_id=as_force.mul_faction_id,
        era_id=as_force.mul_era_id,
        unit_type_id=type_id,
    )
