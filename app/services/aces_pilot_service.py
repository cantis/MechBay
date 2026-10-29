"""Aces Named Pilot creation, SP advancement and service history.

Reuses CampaignPilot. Skill, Edge Tokens and Edge Abilities on an Aces pilot are written
only by ``apply_advancement`` from cumulative per-category SP, and every change is
recorded as an immutable PilotAdvancementEvent.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_pilot import CampaignPilot
from ..models.pilot_advancement_event import PilotAdvancementEvent
from ..models.pilot_injury_event import PilotInjuryEvent
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from ..models.warchest_transaction import WarchestTransaction
from . import aces_pilot_rules as rules
from . import campaign_service


def pilot_ability_list(pilot: CampaignPilot) -> list[str]:
    """Edge Abilities held by a pilot, in acquisition order."""
    if not pilot.edge_abilities:
        return []
    return [name.strip() for name in pilot.edge_abilities.split(",") if name.strip()]


def apply_advancement(
    session: Session,
    pilot: CampaignPilot,
    *,
    source_type: str,
    skill_sp: int,
    edge_sp: int,
    ability_sp: int,
    new_abilities: list[str],
    sp_received: int,
    mvp_bonus: int = 0,
    sortie_id: int | None = None,
    participation_state: str | None = None,
) -> PilotAdvancementEvent:
    """Allocate newly earned SP across Skill/Edge/Abilities and record the event.

    All ``sp_received + mvp_bonus`` SP must be allocated. If the allocation crosses Edge
    Ability thresholds, exactly that many new abilities must be chosen in the same call.
    """
    if source_type not in ("initial", "sortie"):
        raise ValueError("Invalid advancement source")
    if sp_received < 0 or mvp_bonus < 0:
        raise ValueError("SP received cannot be negative")
    rules.validate_allocation(sp_received + mvp_bonus, skill_sp, edge_sp, ability_sp)

    existing = pilot_ability_list(pilot)
    new_skill_sp = pilot.skill_sp + skill_sp
    new_edge_sp = pilot.edge_sp + edge_sp
    new_ability_sp = pilot.ability_sp + ability_sp
    state = rules.derive_state(new_skill_sp, new_edge_sp, new_ability_sp)

    # Compare against abilities actually held, not the previous threshold count, so a
    # pilot is never left with fewer abilities than their SP entitles them to.
    required = state["ability_count"] - len(existing)
    rules.validate_ability_selection(existing, new_abilities, max(required, 0))

    sequence = (
        session.execute(
            select(func.coalesce(func.max(PilotAdvancementEvent.sequence), 0)).where(
                PilotAdvancementEvent.campaign_pilot_id == pilot.id
            )
        ).scalar_one()
        + 1
    )

    pilot.skill_sp = new_skill_sp
    pilot.edge_sp = new_edge_sp
    pilot.ability_sp = new_ability_sp
    pilot.total_sp_earned += sp_received + mvp_bonus
    pilot.alpha_strike_skill = state["skill"]
    pilot.edge_tokens = state["edge_tokens"]
    pilot.improvement_sp = pilot.total_sp_earned
    if new_abilities:
        pilot.edge_abilities = ", ".join(existing + new_abilities)

    event = PilotAdvancementEvent(
        campaign_id=pilot.campaign_id,
        campaign_pilot_id=pilot.id,
        sortie_id=sortie_id,
        sequence=sequence,
        source_type=source_type,
        participation_state=participation_state,
        sp_received=sp_received,
        mvp_bonus=mvp_bonus,
        skill_sp_allocated=skill_sp,
        edge_sp_allocated=edge_sp,
        ability_sp_allocated=ability_sp,
        skill_sp_total=new_skill_sp,
        edge_sp_total=new_edge_sp,
        ability_sp_total=new_ability_sp,
        skill_after=state["skill"],
        edge_tokens_after=state["edge_tokens"],
        ability_count_after=len(existing) + len(new_abilities),
        new_abilities=json.dumps(new_abilities) if new_abilities else None,
        total_sp_after=pilot.total_sp_earned,
    )
    session.add(event)
    session.flush()
    return event


def count_living_pilots(session: Session, campaign_id: int) -> int:
    return session.execute(
        select(func.count(CampaignPilot.id)).where(
            CampaignPilot.campaign_id == campaign_id,
            CampaignPilot.status == "alive",
            CampaignPilot.pilot_type.is_not(None),
        )
    ).scalar_one()


def create_aces_pilot(
    campaign_id: int,
    callsign: str,
    pilot_type: str,
    *,
    skill_sp: int,
    edge_sp: int,
    ability_sp: int,
    abilities: list[str] | None = None,
    notes: str | None = None,
    hired: bool = False,
) -> CampaignPilot:
    """Create a standard Aces Named Pilot with the starting 150 SP fully allocated.

    ``hired`` marks a new/replacement pilot bought mid-campaign: it costs 150 SP from the
    Warchest. The starting pilots of a new campaign are free.
    """
    cleaned = (callsign or "").strip()
    if not cleaned:
        raise ValueError("Callsign is required")
    if pilot_type not in rules.PILOT_TYPES:
        raise ValueError("Pilot Type must be BM, CV or BA")

    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        if campaign.ruleset != "aces":
            raise ValueError("Named Pilot creation here is only available for Aces campaigns")
        campaign_service.require_between_sorties(session, campaign, "add a Named Pilot")
        if count_living_pilots(session, campaign_id) >= rules.MAX_NAMED_PILOTS:
            raise ValueError(
                f"An Aces campaign allows at most {rules.MAX_NAMED_PILOTS} Named Pilots"
            )
        taken = session.execute(
            select(CampaignPilot.id).where(
                CampaignPilot.campaign_id == campaign_id,
                func.lower(CampaignPilot.callsign) == cleaned.lower(),
            )
        ).first()
        if taken:
            raise ValueError(f"Callsign '{cleaned}' is already used in this campaign")

        if hired:
            cost = rules.NEW_PILOT_COST
            if campaign.warchest_balance < cost:
                raise ValueError(
                    f"Insufficient Warchest: hiring a pilot costs {cost} SP, "
                    f"Warchest has {campaign.warchest_balance} SP"
                )
            campaign.warchest_balance -= cost
            session.add(
                WarchestTransaction(
                    campaign_id=campaign_id,
                    campaign_month=campaign.current_campaign_month,
                    transaction_type="personnel",
                    description=f"Hired Named Pilot {cleaned}",
                    gross_amount=-cost,
                    covered_amount=0,
                    actual_amount=-cost,
                    resulting_balance=campaign.warchest_balance,
                    related_entity_type="campaign_pilot",
                )
            )
        pilot = CampaignPilot(
            campaign_id=campaign_id,
            name=cleaned,
            callsign=cleaned,
            pilot_type=pilot_type,
            status="alive",
            notes=notes.strip() if notes and notes.strip() else None,
            alpha_strike_skill=rules.skill_for_sp(0),
            edge_tokens=rules.edge_tokens_for_sp(0),
        )
        session.add(pilot)
        session.flush()
        apply_advancement(
            session,
            pilot,
            source_type="initial",
            skill_sp=skill_sp,
            edge_sp=edge_sp,
            ability_sp=ability_sp,
            new_abilities=abilities or [],
            sp_received=rules.STARTING_PILOT_SP,
        )
        session.expunge(pilot)
        return pilot


def retire_aces_pilot(pilot_id: int) -> CampaignPilot:
    """Retire a living Named Pilot; history is kept."""
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot or pilot.pilot_type is None:
            raise ValueError("Aces pilot not found")
        if pilot.status != "alive":
            raise ValueError("Only living pilots can be retired")
        campaign = session.get(Campaign, pilot.campaign_id)
        campaign_service.require_between_sorties(session, campaign, "retire a Named Pilot")
        pilot.status = "retired"
        session.flush()
        session.expunge(pilot)
        return pilot


def get_pilot_service_history(pilot_id: int) -> dict[str, Any] | None:
    """Pilot snapshot plus a chronological timeline of advancement and injury events."""
    with session_scope() as session:
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot or pilot.pilot_type is None:
            return None
        advancements = list(pilot.advancements)
        injuries = list(
            session.execute(
                select(PilotInjuryEvent)
                .where(PilotInjuryEvent.campaign_pilot_id == pilot_id)
                .order_by(PilotInjuryEvent.id)
            ).scalars()
        )
        timeline: list[dict[str, Any]] = []
        for adv in advancements:
            timeline.append(
                {
                    "kind": "advancement",
                    "at": adv.created_at,
                    "order": (adv.created_at, 0, adv.id),
                    "event": adv,
                    "new_abilities": json.loads(adv.new_abilities) if adv.new_abilities else [],
                }
            )
        for inj in injuries:
            timeline.append(
                {
                    "kind": "injury",
                    "at": inj.created_at,
                    "order": (inj.created_at, 1, inj.id),
                    "event": inj,
                    "new_abilities": [],
                }
            )
        rows = session.execute(
            select(SortieUnit, Sortie)
            .join(Sortie, Sortie.id == SortieUnit.sortie_id)
            .where(
                SortieUnit.campaign_pilot_id == pilot_id,
                Sortie.status.in_(["ready", "fought", "after_action", "closed", "failed"]),
            )
            .order_by(Sortie.id)
        ).all()
        for unit_row, sortie in rows:
            timeline.append(
                {
                    "kind": "sortie",
                    "at": sortie.created_at,
                    "order": (sortie.created_at, 0, sortie.id),
                    "event": sortie,
                    "unit": unit_row,
                    "is_commander": sortie.force_commander_pilot_id == pilot_id,
                    "is_mvp": sortie.mvp_pilot_id == pilot_id,
                    "new_abilities": [],
                }
            )
            session.expunge(unit_row)
        # Aces chronology is Sortie-based: pilot creation first, then each Sortie in
        # sequence/attempt order (with that Sortie's participation, injuries and
        # advancement), never by campaign month. Events with no Sortie sort last.
        sorties = {
            s.id: s
            for s in session.execute(
                select(Sortie).where(Sortie.campaign_id == pilot.campaign_id)
            ).scalars()
        }
        within_sortie = {"sortie": 0, "injury": 1, "advancement": 2}
        for item in timeline:
            event = item["event"]
            if item["kind"] == "advancement" and event.source_type == "initial":
                item["order"] = (0, 0, 0, 0, event.created_at, event.id)
                continue
            sortie = event if item["kind"] == "sortie" else sorties.get(event.sortie_id)
            if sortie is None:
                item["order"] = (2, 0, 0, 0, event.created_at, event.id)
                continue
            item["order"] = (
                1,
                sortie.sortie_number or 0,
                sortie.attempt_number or 1,
                within_sortie[item["kind"]],
                event.created_at,
                event.id,
            )
        timeline.sort(key=lambda item: item["order"])
        for item in timeline:
            session.expunge(item["event"])
        abilities = pilot_ability_list(pilot)
        session.expunge(pilot)
        return {
            "pilot": pilot,
            "abilities": abilities,
            "type_label": rules.PILOT_TYPES.get(pilot.pilot_type, pilot.pilot_type),
            "timeline": timeline,
        }
