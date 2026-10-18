"""Aces After-Sortie workflow: casualties, accounting, pilot improvement, finalize, report.

Flow (see campaign6.prompt.md section 22):

1. ``build_plan`` / ``apply_aces_after_action`` - outcome, casualties, income, expenses,
   repairs, rearming, personnel, Earnings, pilot SP entitlements, MVP, Story Keywords.
   Everything is computed once by ``build_plan`` (so the preview matches what is applied),
   then written in one transaction. Failed Sorties never reach this module.
2. ``allocate_pilot_share`` - each pilot allocates their SP and picks new Edge Abilities.
3. ``finalize_aces_sortie`` - records Next Steps and freezes the Sortie Report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..extensions import session_scope
from ..models.aces_sortie_report import AcesSortieReport, SortiePilotShare
from ..models.campaign import Campaign
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.damage_event import DamageEvent
from ..models.pilot_advancement_event import PilotAdvancementEvent
from ..models.pilot_injury_event import PilotInjuryEvent
from ..models.rearm_order import RearmOrder
from ..models.repair_order import RepairOrder
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from . import aces_pilot_rules as pilot_rules
from . import aces_pilot_service, aces_sortie_service, campaign_rules
from .after_action_service import (
    REARM_COST,
    REPAIRABLE_DAMAGE,
    _condition_for_damage,
    _post_wp,
    unit_has_ene,
)

ACES_DAMAGE_OUTCOMES = ("none", "armour", "structure", "crippled", "destroyed", "truly-destroyed")
WOUND_TREATMENT_COST = pilot_rules.WOUND_TREATMENT_COST
GENERIC_CREW_COST = 100
SUCCESS_OUTCOME = "success"


def _non_negative(value: Any, label: str) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a whole number") from exc
    if number < 0:
        raise ValueError(f"{label} cannot be negative")
    return number


def _is_battlemech(unit_type_name: str | None) -> bool:
    if unit_type_name is None:
        return True  # legacy rows without MUL type data are treated as BattleMechs
    return pilot_rules.pilot_type_for_unit_type(unit_type_name) == "BM"


def _require_fought_aces_sortie(session, sortie_id: int) -> tuple[Sortie, Campaign]:
    sortie = session.get(Sortie, sortie_id)
    if not sortie:
        raise ValueError("Sortie not found")
    campaign = session.get(Campaign, sortie.campaign_id)
    if not campaign or campaign.ruleset != "aces":
        raise ValueError("This action is only available for Aces Sorties")
    return sortie, campaign


# --- plan (pure computation; no writes) ----------------------------------------------------


def build_plan(session, sortie: Sortie, campaign: Campaign, inputs: dict[str, Any]) -> dict:
    if sortie.status != "fought":
        raise ValueError("After-Sortie can only be recorded for a Fought Sortie")
    if sortie.outcome == aces_sortie_service.FAILED_OUTCOME:
        raise ValueError("Failed Sorties do not run the After-Sortie workflow")

    by_id = {int(item["sortie_unit_id"]): item for item in inputs.get("unit_results", [])}
    units: list[dict[str, Any]] = []
    for row in sortie.units:
        result = by_id.get(row.id, {})
        damage = (result.get("damage_outcome") or "none").strip()
        if damage not in ACES_DAMAGE_OUTCOMES:
            raise ValueError("Invalid damage outcome")
        killed = bool(result.get("pilot_killed")) and bool(row.campaign_pilot_id)
        wounded = bool(result.get("pilot_wounded")) and bool(row.campaign_pilot_id) and not killed
        crew_lost = bool(result.get("generic_crew_lost")) and row.is_generic_crew
        truly = damage == "truly-destroyed"
        battlemech = _is_battlemech(row.unit_type_name)
        size = campaign_rules.aces_unit_size(row.mul_snapshot_json, row.tonnage, row.unit_type_name)
        repair = 0
        if damage in REPAIRABLE_DAMAGE:
            if size is None:
                raise ValueError(
                    f"{row.chassis}: Alpha Strike Size is unknown, cannot cost repairs"
                )
            repair = campaign_rules.aces_repair_cost(damage, size, battlemech=battlemech)
        rearm = 0 if truly or unit_has_ene(row) else REARM_COST
        units.append(
            {
                "row": row,
                "damage": damage,
                "truly_destroyed": truly,
                "killed": killed,
                "wounded": wounded,
                "generic_crew_lost": crew_lost,
                "size": size,
                "battlemech": battlemech,
                "repair_cost": repair,
                "rearm_cost": rearm,
            }
        )

    difficulty = campaign.difficulty
    primary_base = _non_negative(inputs.get("primary_objective_sp"), "Primary Objective SP")
    secondary_base = _non_negative(inputs.get("secondary_objective_sp"), "Secondary Objective SP")
    other_income = _non_negative(inputs.get("other_income"), "Other income")
    primary_adj = campaign_rules.adjusted_objective_sp(primary_base, difficulty)
    secondary_adj = campaign_rules.adjusted_objective_sp(secondary_base, difficulty)
    total_income = primary_adj + secondary_adj + other_income

    wounded_count = sum(1 for u in units if u["wounded"])
    crew_lost_count = sum(1 for u in units if u["generic_crew_lost"])
    personnel_lines = []
    if wounded_count:
        personnel_lines.append(
            (
                f"Treatment for {wounded_count} wounded Named Pilot(s)",
                wounded_count * WOUND_TREATMENT_COST,
            )
        )
    if crew_lost_count:
        personnel_lines.append(
            (
                f"Replacement for {crew_lost_count} lost generic crew",
                crew_lost_count * GENERIC_CREW_COST,
            )
        )
    expenses = {
        "reconnaissance": _non_negative(inputs.get("reconnaissance"), "Reconnaissance"),
        "waypoint": _non_negative(inputs.get("waypoint"), "Waypoint adjustments"),
        "rearming": sum(u["rearm_cost"] for u in units),
        "personnel": sum(amount for _, amount in personnel_lines),
        "repairs": sum(u["repair_cost"] for u in units),
        "other": _non_negative(inputs.get("other_expense"), "Other expenses"),
    }
    total_expenses = sum(expenses.values())
    earnings = total_income - total_expenses

    # Pilot improvement entitlements.
    participating = {u["row"].campaign_pilot_id: u for u in units if u["row"].campaign_pilot_id}
    pilots = list(
        session.execute(
            select(CampaignPilot)
            .where(CampaignPilot.campaign_id == campaign.id, CampaignPilot.pilot_type.is_not(None))
            .order_by(CampaignPilot.id)
        ).scalars()
    )
    states: dict[int, str] = {}
    for pilot in pilots:
        if pilot.status == "dead":
            states[pilot.id] = pilot_rules.DEAD
        elif pilot.status != "alive":
            continue  # retired pilots take no part in improvement
        elif pilot.id in participating:
            states[pilot.id] = (
                pilot_rules.KILLED if participating[pilot.id]["killed"] else pilot_rules.PARTICIPANT
            )
        else:
            states[pilot.id] = pilot_rules.NON_PARTICIPANT

    max_pilot_sp = _non_negative(inputs.get("max_pilot_sp"), "Maximum pilot SP")
    awards = pilot_rules.distribute_pilot_sp(earnings, max_pilot_sp, states)
    pilot_pool = sum(awards.values())

    eligible_mvp = [pid for pid, state in states.items() if state == pilot_rules.PARTICIPANT]
    mvp_id = inputs.get("mvp_pilot_id")
    if eligible_mvp:
        if mvp_id is None:
            raise ValueError("Select an MVP from the participating Named Pilots who survived")
        if mvp_id not in eligible_mvp:
            raise ValueError("MVP must be a Named Pilot who participated and survived")
    elif mvp_id is not None:
        raise ValueError("No surviving participating Named Pilot is eligible for MVP")

    by_pilot = {pilot.id: pilot for pilot in pilots}
    shares = [
        {
            "pilot_id": pid,
            "callsign": by_pilot[pid].display_name,
            "pilot_type": by_pilot[pid].pilot_type,
            "state": state,
            "cap": pilot_rules.pilot_sp_cap(state, max_pilot_sp),
            "awarded": awards[pid],
            "mvp_bonus": pilot_rules.MVP_BONUS_SP if pid == mvp_id else 0,
        }
        for pid, state in states.items()
    ]

    before = campaign.warchest_balance
    remainder = earnings - pilot_pool
    return {
        "units": units,
        "income": {
            "difficulty": difficulty,
            "objective_percent": campaign_rules.objective_sp_percent(difficulty),
            "primary_base": primary_base,
            "primary_adjusted": primary_adj,
            "secondary_base": secondary_base,
            "secondary_adjusted": secondary_adj,
            "other": other_income,
            "total": total_income,
        },
        "expenses": {**expenses, "total": total_expenses, "personnel_lines": personnel_lines},
        "earnings": earnings,
        "pilot": {"max_sp": max_pilot_sp, "pool": pilot_pool, "shares": shares, "mvp_id": mvp_id},
        "warchest": {"before": before, "remainder": remainder, "after": before + remainder},
        "force_pv": sum(int(u["row"].point_value or 0) for u in units),
    }


def _plan_summary(plan: dict) -> dict:
    """JSON-safe view of a plan for the preview endpoint."""
    return {
        "units": [
            {
                "unit": f"{u['row'].chassis} {u['row'].variant or ''}".strip(),
                "damage": u["damage"],
                "size": u["size"],
                "repair_cost": u["repair_cost"],
                "rearm_cost": u["rearm_cost"],
            }
            for u in plan["units"]
        ],
        "income": plan["income"],
        "expenses": {k: v for k, v in plan["expenses"].items() if k != "personnel_lines"},
        "earnings": plan["earnings"],
        "pilot": plan["pilot"],
        "warchest": plan["warchest"],
    }


def preview_aces_after_action(sortie_id: int, inputs: dict[str, Any]) -> dict:
    """Compute exactly what Apply would do, without writing anything."""
    with session_scope() as session:
        sortie, campaign = _require_fought_aces_sortie(session, sortie_id)
        plan = build_plan(session, sortie, campaign, inputs)
        return _plan_summary(plan)


# --- apply ---------------------------------------------------------------------------------


def apply_aces_after_action(sortie_id: int, inputs: dict[str, Any]) -> Sortie:
    with session_scope() as session:
        sortie, campaign = _require_fought_aces_sortie(session, sortie_id)
        plan = build_plan(session, sortie, campaign, inputs)
        month = sortie.campaign_month
        income = plan["income"]
        expenses = plan["expenses"]
        pilot_plan = plan["pilot"]

        # 2. Story Keywords (successful Sortie only; duplicates/unheld removals abort all).
        for keyword in inputs.get("keywords_gained") or []:
            aces_sortie_service.append_keyword(session, sortie, keyword, "acquired")
        for keyword in inputs.get("keywords_removed") or []:
            aces_sortie_service.append_keyword(session, sortie, keyword, "removed")

        # 11a. Pilots who sat this successful Sortie out while wounded recover first.
        for pilot in session.execute(
            select(CampaignPilot).where(
                CampaignPilot.campaign_id == campaign.id,
                CampaignPilot.pilot_type.is_not(None),
                CampaignPilot.status == "alive",
                CampaignPilot.wounds > 0,
            )
        ).scalars():
            pilot.wounds = 0
            pilot.wounded = False
            session.add(
                PilotInjuryEvent(
                    campaign_id=campaign.id,
                    campaign_pilot_id=pilot.id,
                    sortie_id=sortie.id,
                    campaign_month=month,
                    event_type="recovered",
                    notes="Sat out a successful Sortie",
                )
            )

        # 3. Casualties and unit state, 6. repair and rearm orders.
        repair_orders: list[tuple[RepairOrder, SortieUnit]] = []
        rearm_orders: list[tuple[RearmOrder, SortieUnit]] = []
        for item in plan["units"]:
            row: SortieUnit = item["row"]
            row.damage_outcome = item["damage"]
            row.pilot_wounded = item["wounded"]
            row.pilot_killed = item["killed"]
            row.generic_crew_lost = item["generic_crew_lost"]
            row.repair_cost = item["repair_cost"]
            row.rearm_cost = item["rearm_cost"]
            row.needs_rearm = item["rearm_cost"] > 0

            unit = session.get(CampaignUnit, row.campaign_unit_id) if row.campaign_unit_id else None
            if unit:
                condition, available = _condition_for_damage(item["damage"])
                unit.damage_category = item["damage"]
                unit.condition = condition
                unit.available = available
                session.add(
                    DamageEvent(
                        campaign_id=campaign.id,
                        campaign_unit_id=unit.id,
                        sortie_id=sortie.id,
                        campaign_month=month,
                        damage_category=item["damage"],
                    )
                )
                if item["repair_cost"] > 0:
                    order = RepairOrder(
                        campaign_id=campaign.id,
                        sortie_id=sortie.id,
                        campaign_unit_id=unit.id,
                        damage_category=item["damage"],
                        ruleset="aces",
                        gross_cost=item["repair_cost"],
                        covered_amount=0,
                        actual_cost=-item["repair_cost"],
                        campaign_month=month,
                        status="pending",
                    )
                    session.add(order)
                    repair_orders.append((order, row))
                if item["rearm_cost"] > 0:
                    rearm = RearmOrder(
                        campaign_id=campaign.id,
                        sortie_id=sortie.id,
                        campaign_unit_id=unit.id,
                        campaign_month=month,
                        gross_cost=item["rearm_cost"],
                        covered_amount=0,
                        actual_cost=-item["rearm_cost"],
                    )
                    session.add(rearm)
                    rearm_orders.append((rearm, row))

            if row.campaign_pilot_id and (item["killed"] or item["wounded"]):
                pilot = session.get(CampaignPilot, row.campaign_pilot_id)
                if item["killed"]:
                    pilot.status = "dead"
                    pilot.wounded = False
                    event_type = "died"
                else:
                    pilot.wounds = 1  # Aces: a single one-Sortie recovery state
                    pilot.wounded = True
                    event_type = "wounded"
                session.add(
                    PilotInjuryEvent(
                        campaign_id=campaign.id,
                        campaign_pilot_id=pilot.id,
                        sortie_id=sortie.id,
                        campaign_month=month,
                        event_type=event_type,
                    )
                )
        session.flush()

        # 4-7. Ledger: income, then expenses, then the pilot-improvement SP set aside.
        def post(kind: str, description: str, amount: int, entity: tuple[str, int] | None = None):
            _post_wp(
                session,
                campaign,
                campaign_month=month,
                transaction_type=kind,
                description=description,
                gross_amount=amount,
                covered_amount=0,
                actual_amount=amount,
                related_entity_type=entity[0] if entity else "sortie",
                related_entity_id=entity[1] if entity else sortie.id,
            )

        post(
            "objective_income",
            f"Primary objective - {sortie.attempt_label}",
            income["primary_adjusted"],
        )
        post(
            "objective_income",
            f"Secondary objectives - {sortie.attempt_label}",
            income["secondary_adjusted"],
        )
        post("other_income", f"Other income - {sortie.attempt_label}", income["other"])
        post(
            "reconnaissance",
            f"Reconnaissance - {sortie.attempt_label}",
            -expenses["reconnaissance"],
        )
        post("waypoint", f"Waypoint adjustments - {sortie.attempt_label}", -expenses["waypoint"])
        for rearm, row in rearm_orders:
            post("rearm", f"Rearm {row.chassis}", -rearm.gross_cost, ("rearm_order", rearm.id))
        for order, row in repair_orders:
            post(
                "repair",
                f"Repair {row.chassis} ({order.damage_category})",
                -order.gross_cost,
                ("repair_order", order.id),
            )
        for description, amount in expenses["personnel_lines"]:
            post("personnel", description, -amount)
        post("other_expense", f"Other expenses - {sortie.attempt_label}", -expenses["other"])
        post(
            "pilot_improvement",
            f"Named Pilot improvement SP - {sortie.attempt_label}",
            -pilot_plan["pool"],
        )

        # 8-10. Pilot entitlements, MVP.
        for share in pilot_plan["shares"]:
            total = share["awarded"] + share["mvp_bonus"]
            session.add(
                SortiePilotShare(
                    sortie_id=sortie.id,
                    campaign_pilot_id=share["pilot_id"],
                    callsign=share["callsign"],
                    pilot_type=share["pilot_type"],
                    state=share["state"],
                    max_sp=share["cap"],
                    awarded_sp=share["awarded"],
                    mvp_bonus=share["mvp_bonus"],
                    allocated=total == 0,
                )
            )
        if pilot_plan["mvp_id"] is not None:
            mvp = session.get(CampaignPilot, pilot_plan["mvp_id"])
            mvp.mvp_count += 1
            sortie.mvp_pilot_id = mvp.id

        sortie.outcome = SUCCESS_OUTCOME
        sortie.after_action_notes = (inputs.get("after_action_notes") or "").strip() or None
        sortie.status = "after_action"
        sortie.updated_at = datetime.now(UTC)
        campaign.updated_at = datetime.now(UTC)

        session.add(
            AcesSortieReport(
                sortie_id=sortie.id,
                campaign_id=campaign.id,
                difficulty=campaign.difficulty,
                objective_percent=income["objective_percent"],
                force_pv=plan["force_pv"],
                primary_objective_base=income["primary_base"],
                primary_objective_adjusted=income["primary_adjusted"],
                secondary_objective_base=income["secondary_base"],
                secondary_objective_adjusted=income["secondary_adjusted"],
                other_income=income["other"],
                total_income=income["total"],
                expense_reconnaissance=expenses["reconnaissance"],
                expense_waypoint=expenses["waypoint"],
                expense_rearming=expenses["rearming"],
                expense_personnel=expenses["personnel"],
                expense_repairs=expenses["repairs"],
                expense_other=expenses["other"],
                total_expenses=expenses["total"],
                earnings=plan["earnings"],
                max_pilot_sp=pilot_plan["max_sp"],
                pilot_sp_pool=pilot_plan["pool"],
                warchest_before=plan["warchest"]["before"],
                warchest_remainder=plan["warchest"]["remainder"],
                warchest_after_accounting=campaign.warchest_balance,
                story_notes=(inputs.get("story_notes") or "").strip() or None,
            )
        )
        session.flush()
        session.expunge(sortie)
        return sortie


# --- pilot improvement ---------------------------------------------------------------------


def allocate_pilot_share(
    sortie_id: int,
    pilot_id: int,
    *,
    skill_sp: int,
    edge_sp: int,
    ability_sp: int,
    abilities: list[str] | None = None,
) -> PilotAdvancementEvent:
    """Allocate one pilot's Sortie SP (plus MVP bonus) and choose newly earned abilities."""
    with session_scope() as session:
        sortie, _ = _require_fought_aces_sortie(session, sortie_id)
        report = session.execute(
            select(AcesSortieReport).where(AcesSortieReport.sortie_id == sortie_id)
        ).scalar_one_or_none()
        if sortie.status != "after_action" or not report or report.finalized:
            raise ValueError("Pilot SP can only be allocated while the After-Sortie is open")
        share = session.execute(
            select(SortiePilotShare).where(
                SortiePilotShare.sortie_id == sortie_id,
                SortiePilotShare.campaign_pilot_id == pilot_id,
            )
        ).scalar_one_or_none()
        if not share:
            raise ValueError("This pilot has no improvement SP from this Sortie")
        if share.allocated:
            raise ValueError("This pilot's SP has already been allocated")
        pilot = session.get(CampaignPilot, pilot_id)
        event = aces_pilot_service.apply_advancement(
            session,
            pilot,
            source_type="sortie",
            sortie_id=sortie_id,
            participation_state=share.state,
            sp_received=share.awarded_sp,
            mvp_bonus=share.mvp_bonus,
            skill_sp=skill_sp,
            edge_sp=edge_sp,
            ability_sp=ability_sp,
            new_abilities=abilities or [],
        )
        share.allocated = True
        share.advancement_event_id = event.id
        session.flush()
        session.expunge(event)
        return event


def pending_shares(sortie_id: int) -> list[dict[str, Any]]:
    """Unallocated shares with the pilot state the allocation form needs."""
    with session_scope() as session:
        result = []
        for share in session.execute(
            select(SortiePilotShare)
            .where(SortiePilotShare.sortie_id == sortie_id, SortiePilotShare.allocated.is_(False))
            .order_by(SortiePilotShare.id)
        ).scalars():
            pilot = session.get(CampaignPilot, share.campaign_pilot_id)
            result.append(
                {
                    "share": share,
                    "total": share.awarded_sp + share.mvp_bonus,
                    "skill_sp": pilot.skill_sp,
                    "edge_sp": pilot.edge_sp,
                    "ability_sp": pilot.ability_sp,
                    "owned_abilities": aces_pilot_service.pilot_ability_list(pilot),
                }
            )
            session.expunge(share)
        return result


def finalize_aces_sortie(sortie_id: int, next_steps: str | None = None) -> Sortie:
    """Record Next Steps and freeze the Sortie Report. All pilot SP must be allocated."""
    with session_scope() as session:
        sortie, campaign = _require_fought_aces_sortie(session, sortie_id)
        report = session.execute(
            select(AcesSortieReport).where(AcesSortieReport.sortie_id == sortie_id)
        ).scalar_one_or_none()
        if sortie.status != "after_action" or not report or report.finalized:
            raise ValueError("Only an open After-Sortie can be finalized")
        unallocated = (
            session.execute(
                select(SortiePilotShare).where(
                    SortiePilotShare.sortie_id == sortie_id, SortiePilotShare.allocated.is_(False)
                )
            )
            .scalars()
            .first()
        )
        if unallocated:
            raise ValueError(f"{unallocated.callsign}'s improvement SP must be allocated first")
        report.next_steps = (next_steps or "").strip() or None
        report.warchest_after = campaign.warchest_balance
        report.finalized = True
        report.finalized_at = datetime.now(UTC)
        sortie.status = "closed"
        sortie.updated_at = datetime.now(UTC)
        session.flush()
        session.expunge(sortie)
        return sortie


# --- reporting -----------------------------------------------------------------------------


def get_sortie_report(sortie_id: int) -> dict[str, Any] | None:
    """Everything the Sortie Report page shows, from stored snapshots only."""
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            return None
        campaign = session.get(Campaign, sortie.campaign_id)
        if not campaign or campaign.ruleset != "aces":
            return None
        report = session.execute(
            select(AcesSortieReport).where(AcesSortieReport.sortie_id == sortie_id)
        ).scalar_one_or_none()
        units = list(sortie.units)
        shares = []
        for share in session.execute(
            select(SortiePilotShare)
            .where(SortiePilotShare.sortie_id == sortie_id)
            .order_by(SortiePilotShare.id)
        ).scalars():
            event = (
                session.get(PilotAdvancementEvent, share.advancement_event_id)
                if share.advancement_event_id
                else None
            )
            shares.append(
                {
                    "share": share,
                    "event": event,
                    "new_abilities": json.loads(event.new_abilities)
                    if event and event.new_abilities
                    else [],
                }
            )
        injuries = list(
            session.execute(
                select(PilotInjuryEvent)
                .where(PilotInjuryEvent.sortie_id == sortie_id)
                .order_by(PilotInjuryEvent.id)
            ).scalars()
        )
        mvp_share = next((s["share"] for s in shares if s["share"].mvp_bonus), None)
        data = {
            "sortie": sortie,
            "campaign": campaign,
            "report": report,
            "units": units,
            "shares": shares,
            "injuries": injuries,
            "mvp_callsign": mvp_share.callsign if mvp_share else None,
            "mvp_pilot_id": mvp_share.campaign_pilot_id if mvp_share else None,
            "force_pv": report.force_pv if report else sum(int(u.point_value or 0) for u in units),
        }
        for key in ("sortie", "report"):
            if data[key] is not None:
                session.expunge(data[key])
    # These open their own session scopes (which share the thread's session), so they must
    # run after the objects above have been detached.
    data["keywords"] = aces_sortie_service.get_sortie_keywords(sortie_id)
    data["lineage"] = aces_sortie_service.get_lineage(sortie_id)
    return data
