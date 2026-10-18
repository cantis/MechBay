"""Aces Sortie workflow: Force Commander, failed Sorties and replays, Story Keywords.

Aces Sorties are contract-free (see ``campaign_service.create_aces_sortie``). A failed
Sortie is kept as history and has no persistent After-Sortie consequences; a replay is a
new Sortie row linked back to the failed attempt.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select

from ..extensions import session_scope
from ..models.aces_sortie_report import AcesSortieReport, SortiePilotShare
from ..models.campaign import Campaign
from ..models.campaign_pilot import CampaignPilot
from ..models.campaign_unit import CampaignUnit
from ..models.sortie import Sortie
from ..models.sortie_unit import SortieUnit
from ..models.story_keyword_event import STORY_KEYWORD_ACTIONS, StoryKeywordEvent
from . import campaign_rules, contract_service, mul_service
from .campaign_service import pilot_is_available

FAILED_OUTCOME = "failed"
KEYWORD_ALLOWED_STATUSES = {"fought", "after_action", "closed"}


def _require_aces_sortie(session, sortie_id: int) -> tuple[Sortie, Campaign]:
    sortie = session.get(Sortie, sortie_id)
    if not sortie:
        raise ValueError("Sortie not found")
    campaign = session.get(Campaign, sortie.campaign_id)
    if not campaign or campaign.ruleset != "aces":
        raise ValueError("This action is only available for Aces Sorties")
    return sortie, campaign


# --- Force Commander ---------------------------------------------------------------------


def set_force_commander(sortie_id: int, pilot_id: int) -> Sortie:
    """Pick the Force Commander from the Named Pilots crewing units in this Sortie."""
    with session_scope() as session:
        sortie, _ = _require_aces_sortie(session, sortie_id)
        if sortie.status not in contract_service.EDITABLE_SORTIE_STATUSES:
            raise ValueError("Force Commander is locked once the Sortie is Ready")
        pilot = session.get(CampaignPilot, pilot_id)
        if not pilot or pilot.campaign_id != sortie.campaign_id or pilot.pilot_type is None:
            raise ValueError("Force Commander must be a Named Pilot in this campaign")
        participating = {row.campaign_pilot_id for row in sortie.units}
        if pilot.id not in participating:
            raise ValueError("Force Commander must be a Named Pilot participating in this Sortie")
        if pilot.status != "alive" or not pilot_is_available(pilot):
            raise ValueError("Force Commander must be alive and available")
        sortie.force_commander_pilot_id = pilot.id
        sortie.force_commander_callsign = pilot.display_name
        session.flush()
        session.expunge(sortie)
        return sortie


# --- Failed Sorties and replays ------------------------------------------------------------


def unreplayed_failed_sortie(session, campaign_id: int) -> Sortie | None:
    """A failed Aces Sortie that has not yet been replayed (replay is mandatory)."""
    replayed_ids = select(Sortie.replay_of_sortie_id).where(
        Sortie.campaign_id == campaign_id, Sortie.replay_of_sortie_id.is_not(None)
    )
    return (
        session.execute(
            select(Sortie)
            .where(
                Sortie.campaign_id == campaign_id,
                Sortie.contract_id.is_(None),
                Sortie.status == "failed",
                Sortie.id.not_in(replayed_ids),
            )
            .order_by(Sortie.id)
        )
        .scalars()
        .first()
    )


def get_replay_required(campaign_id: int) -> Sortie | None:
    with session_scope() as session:
        sortie = unreplayed_failed_sortie(session, campaign_id)
        if sortie:
            session.expunge(sortie)
        return sortie


def fail_sortie(sortie_id: int, notes: str | None = None) -> Sortie:
    """Record that the primary objective was not completed. Replay becomes required.

    Nothing is applied to persistent campaign state: no keywords, casualties, repairs,
    rearming, advancement, MVP or Warchest changes. The force/pilot snapshot is kept.
    """
    with session_scope() as session:
        sortie, _ = _require_aces_sortie(session, sortie_id)
        if sortie.status not in {"ready", "fought"}:
            raise ValueError("Only a Ready or Fought Sortie can be recorded as failed")
        sortie.status = "failed"
        sortie.outcome = FAILED_OUTCOME
        if notes and notes.strip():
            sortie.after_action_notes = notes.strip()
        session.flush()
        session.expunge(sortie)
        return sortie


def create_replay(failed_sortie_id: int) -> Sortie:
    """Create the replacement attempt for a failed Sortie.

    The force and pilot assignments are copied (and re-snapshotted from current state,
    which a failed attempt left untouched) and may be edited before the replay is Ready.
    """
    with session_scope() as session:
        failed, _ = _require_aces_sortie(session, failed_sortie_id)
        if failed.status != "failed":
            raise ValueError("Only a failed Sortie can be replayed")
        existing = session.execute(
            select(Sortie.id).where(Sortie.replay_of_sortie_id == failed.id)
        ).first()
        if existing:
            raise ValueError("This failed Sortie already has a replay attempt")

        replay = Sortie(
            campaign_id=failed.campaign_id,
            contract_id=None,
            name=failed.name,
            campaign_month=failed.campaign_month,
            scale=failed.scale,
            scenario_type=failed.scenario_type,
            location=failed.location,
            notes=failed.notes,
            status="planning",
            date_played=date.today(),
            sortie_number=failed.sortie_number,
            attempt_number=(failed.attempt_number or 1) + 1,
            replay_of_sortie_id=failed.id,
        )
        session.add(replay)
        session.flush()
        new_id = replay.id
        old_assignments = [(row.campaign_unit_id, row.campaign_pilot_id) for row in failed.units]
        commander_id = failed.force_commander_pilot_id

    # Re-add units and pilots through the normal validating path. Anything no longer
    # available (a unit or a wounded pilot) is skipped; the player adjusts the replay.
    for unit_id, _ in old_assignments:
        if unit_id is None:
            continue
        try:
            contract_service.add_unit_to_sortie(new_id, unit_id)
        except ValueError:
            continue
    with session_scope() as session:
        rows = {
            row.campaign_unit_id: row.id
            for row in session.execute(
                select(SortieUnit).where(SortieUnit.sortie_id == new_id)
            ).scalars()
        }
    for unit_id, pilot_id in old_assignments:
        if pilot_id is None or unit_id not in rows:
            continue
        try:
            contract_service.assign_sortie_pilot(rows[unit_id], pilot_id)
        except ValueError:
            continue
    if commander_id is not None:
        try:
            set_force_commander(new_id, commander_id)
        except ValueError:
            pass  # commander unavailable or no longer crewing; must be re-selected
    with session_scope() as session:
        replay = session.get(Sortie, new_id)
        session.expunge(replay)
        return replay


def get_lineage(sortie_id: int) -> dict[str, Sortie | None]:
    """The failed attempt this Sortie replays, and the replay of this Sortie if any."""
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie:
            return {"replay_of": None, "replayed_by": None}
        replay_of = (
            session.get(Sortie, sortie.replay_of_sortie_id) if sortie.replay_of_sortie_id else None
        )
        replayed_by = (
            session.execute(select(Sortie).where(Sortie.replay_of_sortie_id == sortie.id))
            .scalars()
            .first()
        )
        for item in (replay_of, replayed_by):
            if item:
                session.expunge(item)
        return {"replay_of": replay_of, "replayed_by": replayed_by}


# --- Story Keywords -----------------------------------------------------------------------


def _keyword_events(session, campaign_id: int) -> list[StoryKeywordEvent]:
    return list(
        session.execute(
            select(StoryKeywordEvent)
            .where(StoryKeywordEvent.campaign_id == campaign_id)
            .order_by(StoryKeywordEvent.sequence)
        ).scalars()
    )


def derive_current_keywords(events: list[StoryKeywordEvent]) -> list[str]:
    """Replay history in order; later removals cancel earlier acquisitions."""
    current: dict[str, None] = {}
    for item in events:
        if item.action == "acquired":
            current[item.keyword] = None
        else:
            current.pop(item.keyword, None)
    return list(current)


def get_current_keywords(campaign_id: int) -> list[str]:
    with session_scope() as session:
        return derive_current_keywords(_keyword_events(session, campaign_id))


def record_story_keyword(sortie_id: int, keyword: str, action: str = "acquired") -> None:
    """Append a Story Keyword event for a successful Aces Sortie."""
    cleaned = (keyword or "").strip()
    if not cleaned:
        raise ValueError("Keyword is required")
    if len(cleaned) > 64:
        raise ValueError("Keyword must be 64 characters or fewer")
    if action not in STORY_KEYWORD_ACTIONS:
        raise ValueError("Keyword action must be acquired or removed")
    with session_scope() as session:
        sortie, _ = _require_aces_sortie(session, sortie_id)
        append_keyword(session, sortie, cleaned, action)


def append_keyword(session, sortie: Sortie, keyword: str, action: str) -> None:
    """Validate and append one Story Keyword event inside the caller's transaction."""
    cleaned = (keyword or "").strip()
    if not cleaned:
        raise ValueError("Keyword is required")
    if len(cleaned) > 64:
        raise ValueError("Keyword must be 64 characters or fewer")
    if action not in STORY_KEYWORD_ACTIONS:
        raise ValueError("Keyword action must be acquired or removed")
    if sortie.status == "failed" or sortie.outcome == FAILED_OUTCOME:
        raise ValueError("Failed Sorties do not grant Story Keywords")
    if sortie.status not in KEYWORD_ALLOWED_STATUSES:
        raise ValueError("Story Keywords are recorded after the Sortie has been fought")
    events = _keyword_events(session, sortie.campaign_id)
    current = {k.lower(): k for k in derive_current_keywords(events)}
    if action == "acquired" and cleaned.lower() in current:
        raise ValueError(f"Story Keyword '{current[cleaned.lower()]}' is already held")
    if action == "removed":
        if cleaned.lower() not in current:
            raise ValueError(f"Story Keyword '{cleaned}' is not currently held")
        cleaned = current[cleaned.lower()]
    sequence = (
        session.execute(
            select(func.coalesce(func.max(StoryKeywordEvent.sequence), 0)).where(
                StoryKeywordEvent.campaign_id == sortie.campaign_id
            )
        ).scalar_one()
        + 1
    )
    session.add(
        StoryKeywordEvent(
            campaign_id=sortie.campaign_id,
            sortie_id=sortie.id,
            sequence=sequence,
            keyword=cleaned,
            action=action,
        )
    )
    session.flush()


def get_sortie_keywords(sortie_id: int) -> dict[str, list[str]]:
    with session_scope() as session:
        rows = list(
            session.execute(
                select(StoryKeywordEvent)
                .where(StoryKeywordEvent.sortie_id == sortie_id)
                .order_by(StoryKeywordEvent.sequence)
            ).scalars()
        )
        return {
            "gained": [r.keyword for r in rows if r.action == "acquired"],
            "removed": [r.keyword for r in rows if r.action == "removed"],
        }


# --- Campaign listing ---------------------------------------------------------------------


def sortie_stats_by_campaign(campaign_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Completed-Sortie count and most recent date played, for the campaign list."""
    if not campaign_ids:
        return {}
    with session_scope() as session:
        stats: dict[int, dict[str, Any]] = {
            cid: {"completed": 0, "last_played": None} for cid in campaign_ids
        }
        for sortie in session.execute(
            select(Sortie).where(
                Sortie.campaign_id.in_(campaign_ids),
                Sortie.contract_id.is_(None),
                Sortie.status.in_(["after_action", "closed"]),
            )
        ).scalars():
            entry = stats[sortie.campaign_id]
            entry["completed"] += 1
            if sortie.date_played and (
                entry["last_played"] is None or sortie.date_played > entry["last_played"]
            ):
                entry["last_played"] = sortie.date_played
        return stats


def list_aces_sorties(campaign_id: int) -> list[dict[str, Any]]:
    """Every attempt (including failed ones) with label, date, result and keywords."""
    with session_scope() as session:
        sorties = list(
            session.execute(
                select(Sortie)
                .where(Sortie.campaign_id == campaign_id, Sortie.contract_id.is_(None))
                .order_by(Sortie.sortie_number, Sortie.attempt_number, Sortie.id)
            ).scalars()
        )
        gained: dict[int, list[str]] = {}
        for item in session.execute(
            select(StoryKeywordEvent).where(
                StoryKeywordEvent.campaign_id == campaign_id,
                StoryKeywordEvent.action == "acquired",
            )
        ).scalars():
            if item.sortie_id is not None:
                gained.setdefault(item.sortie_id, []).append(item.keyword)
        reports = {
            r.sortie_id: r
            for r in session.execute(
                select(AcesSortieReport).where(AcesSortieReport.campaign_id == campaign_id)
            ).scalars()
        }
        mvps = {
            s.sortie_id: s.callsign
            for s in session.execute(
                select(SortiePilotShare).where(SortiePilotShare.mvp_bonus > 0)
            ).scalars()
        }
        result = []
        for sortie in sorties:
            report = reports.get(sortie.id)
            net = None
            if report:
                end = (
                    report.warchest_after if report.finalized else report.warchest_after_accounting
                )
                net = end - report.warchest_before
            result.append(
                {
                    "report_available": sortie.status in {"after_action", "closed", "failed"},
                    "force_pv": report.force_pv
                    if report
                    else sum(int(u.point_value or 0) for u in sortie.units),
                    "mvp": mvps.get(sortie.id),
                    "net_sp": net,
                    "next_steps": report.next_steps if report else None,
                    "id": sortie.id,
                    "label": sortie.attempt_label,
                    "name": sortie.name,
                    "date_played": sortie.date_played,
                    "status": sortie.status,
                    "outcome": sortie.outcome,
                    "force_commander": sortie.force_commander_callsign,
                    "keywords": gained.get(sortie.id, []),
                    "is_replay": sortie.replay_of_sortie_id is not None,
                }
            )
        return result


# --- Omni reconfiguration ------------------------------------------------------------------


def reconfigure_aces_omni(sortie_unit_id: int, mul_unit_id: int) -> SortieUnit:
    """Change an Omni unit's configuration while a Sortie is being prepared.

    Cost (Aces rules, never the Chaos rules): equal/lower PV -> Size x 5 SP; higher PV ->
    PV difference x 40 SP. The CampaignUnit's current configuration changes, a
    configuration event is kept, the cost is posted to the Warchest ledger, and the
    SortieUnit snapshots the configuration actually fielded.
    """
    from . import after_action_service

    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        if not row:
            raise ValueError("Sortie unit not found")
        sortie, campaign = _require_aces_sortie(session, row.sortie_id)
        if sortie.status not in contract_service.EDITABLE_SORTIE_STATUSES:
            raise ValueError("Omni configuration can only change while the Sortie is in Planning")
        if row.campaign_unit_id is None:
            raise ValueError("This Sortie unit is not linked to a Campaign Unit")
        unit = session.get(CampaignUnit, row.campaign_unit_id)
        if not unit or not unit.is_omni:
            raise ValueError("Only Omni-capable units can change configuration")
        if campaign.mul_faction_id is None or campaign.mul_era_id is None:
            raise ValueError("Set MUL faction and era on the campaign to change Omni loadouts")
        if not unit.point_value:
            raise ValueError("The unit's current Point Value is unknown")
        size = campaign_rules.aces_unit_size(
            unit.mul_snapshot_json, unit.tonnage, unit.unit_type_name
        )
        if size is None:
            raise ValueError(
                f"{unit.chassis}: Alpha Strike Size is unknown, cannot cost the change"
            )
        chassis = unit.chassis
        type_id = unit.unit_type_id
        faction_id = campaign.mul_faction_id
        era_id = campaign.mul_era_id
        old_pv = int(unit.point_value)
        old_mul_id = unit.mul_unit_id
        unit_id = unit.id
        campaign_id = campaign.id

    raw = mul_service.find_unit_in_search_results(
        chassis, mul_unit_id, faction_id=faction_id, era_id=era_id, unit_type_id=type_id
    )
    parsed = mul_service.parse_mul_unit(raw)
    if not parsed.point_value:
        raise ValueError("The selected configuration has no valid MUL Point Value")
    if parsed.id == old_mul_id:
        raise ValueError("The unit is already in that configuration")
    cost = campaign_rules.aces_omni_cost(old_pv, int(parsed.point_value), size)
    balance = campaign_service_balance(campaign_id)
    if balance < cost:
        raise ValueError(
            f"Insufficient Warchest: reconfiguration costs {cost} SP, Warchest has {balance} SP"
        )
    after_action_service.reconfigure_omni_unit(unit_id, raw, cost=cost)

    with session_scope() as session:
        row = session.get(SortieUnit, sortie_unit_id)
        unit = session.get(CampaignUnit, unit_id)
        contract_service._copy_unit_config(row, unit)
        row.configuration_changed = True
        row.reconfiguration_cost = (row.reconfiguration_cost or 0) + cost
        session.flush()
        session.expunge(row)
        return row


def campaign_service_balance(campaign_id: int) -> int:
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        return campaign.warchest_balance if campaign else 0
