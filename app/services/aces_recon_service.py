"""Aces reconnaissance actions: recorded in Sortie Setup, settled in the After-Sortie.

MechBay only records what the player did and what it cost (the SP figure comes from the
physical Aces rules). Nothing is deducted from the Warchest when an action is entered; the
Sortie's total feeds that Sortie's After-Sortie expenses.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ..extensions import session_scope
from ..models.campaign import Campaign
from ..models.campaign_unit import CampaignUnit
from ..models.sortie import Sortie
from ..models.sortie_recon_action import SortieReconAction
from . import contract_service

OUT_OF_SERVICE = ("retired", "truly-destroyed")


def _editable_aces_sortie(session, sortie_id: int) -> Sortie:
    sortie = session.get(Sortie, sortie_id)
    if not sortie:
        raise ValueError("Sortie not found")
    campaign = session.get(Campaign, sortie.campaign_id)
    if not campaign or campaign.ruleset != "aces":
        raise ValueError("Reconnaissance is only available for Aces Sorties")
    if sortie.status not in contract_service.EDITABLE_SORTIE_STATUSES:
        raise ValueError("Reconnaissance can only be changed while the Sortie is in Planning")
    return sortie


def _unit_for_recon(session, sortie: Sortie, unit_id: int | None) -> tuple[int | None, str | None]:
    if unit_id is None:
        return None, None
    unit = session.get(CampaignUnit, unit_id)
    if not unit or unit.campaign_id != sortie.campaign_id:
        raise ValueError("The unit must belong to this campaign's Player Force")
    if unit.condition in OUT_OF_SERVICE:
        raise ValueError("The unit is no longer part of the Player Force")
    label = " ".join(part for part in (unit.prefix, unit.chassis, unit.variant) if part)
    return unit.id, label


def _clean(name: str | None, sp_cost: Any, notes: str | None) -> tuple[str, int, str | None]:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Reconnaissance action name is required")
    if len(cleaned) > 256:
        raise ValueError("Reconnaissance action name must be 256 characters or fewer")
    try:
        cost = int(sp_cost or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Reconnaissance SP cost must be a whole number") from exc
    if cost < 0:
        raise ValueError("Reconnaissance SP cost cannot be negative")
    return cleaned, cost, (notes or "").strip() or None


def _renumber(session, sortie_id: int) -> None:
    rows = session.execute(
        select(SortieReconAction)
        .where(SortieReconAction.sortie_id == sortie_id)
        .order_by(SortieReconAction.position, SortieReconAction.id)
    ).scalars()
    for index, row in enumerate(rows):
        row.position = index


def add_recon_action(
    sortie_id: int,
    name: str,
    *,
    campaign_unit_id: int | None = None,
    sp_cost: Any = 0,
    notes: str | None = None,
) -> SortieReconAction:
    cleaned, cost, clean_notes = _clean(name, sp_cost, notes)
    with session_scope() as session:
        sortie = _editable_aces_sortie(session, sortie_id)
        unit_id, label = _unit_for_recon(session, sortie, campaign_unit_id)
        position = session.execute(
            select(func.coalesce(func.max(SortieReconAction.position), -1)).where(
                SortieReconAction.sortie_id == sortie_id
            )
        ).scalar_one()
        action = SortieReconAction(
            sortie_id=sortie_id,
            position=int(position) + 1,
            name=cleaned,
            campaign_unit_id=unit_id,
            unit_label=label,
            sp_cost=cost,
            notes=clean_notes,
        )
        session.add(action)
        session.flush()
        session.expunge(action)
        return action


def update_recon_action(
    action_id: int,
    name: str,
    *,
    campaign_unit_id: int | None = None,
    sp_cost: Any = 0,
    notes: str | None = None,
) -> SortieReconAction:
    cleaned, cost, clean_notes = _clean(name, sp_cost, notes)
    with session_scope() as session:
        action = session.get(SortieReconAction, action_id)
        if not action:
            raise ValueError("Reconnaissance action not found")
        sortie = _editable_aces_sortie(session, action.sortie_id)
        if campaign_unit_id != action.campaign_unit_id:
            action.campaign_unit_id, action.unit_label = _unit_for_recon(
                session, sortie, campaign_unit_id
            )
        action.name = cleaned
        action.sp_cost = cost
        action.notes = clean_notes
        session.flush()
        session.expunge(action)
        return action


def delete_recon_action(action_id: int) -> int:
    """Remove an action while the Sortie is editable; returns the Sortie id."""
    with session_scope() as session:
        action = session.get(SortieReconAction, action_id)
        if not action:
            raise ValueError("Reconnaissance action not found")
        sortie = _editable_aces_sortie(session, action.sortie_id)
        sortie_id = sortie.id
        session.delete(action)
        session.flush()
        _renumber(session, sortie_id)
        return sortie_id


def list_recon_actions(sortie_id: int) -> list[SortieReconAction]:
    with session_scope() as session:
        rows = list(
            session.execute(
                select(SortieReconAction)
                .where(SortieReconAction.sortie_id == sortie_id)
                .order_by(SortieReconAction.position, SortieReconAction.id)
            ).scalars()
        )
        for row in rows:
            session.expunge(row)
        return rows


def recon_total(session, sortie_id: int) -> int:
    """Total reconnaissance SP for a Sortie, inside the caller's session."""
    return int(
        session.execute(
            select(func.coalesce(func.sum(SortieReconAction.sp_cost), 0)).where(
                SortieReconAction.sortie_id == sortie_id
            )
        ).scalar_one()
    )


def copy_from_previous_attempt(sortie_id: int) -> list[SortieReconAction]:
    """Copy the failed attempt's actions into this replay, if it has none of its own yet.

    Never happens automatically: the player asks for it. A unit that is no longer in the
    Player Force is dropped from the copy (the action itself is kept).
    """
    with session_scope() as session:
        sortie = _editable_aces_sortie(session, sortie_id)
        if sortie.replay_of_sortie_id is None:
            raise ValueError("Only a replay can copy reconnaissance from a previous attempt")
        existing = session.execute(
            select(SortieReconAction.id).where(SortieReconAction.sortie_id == sortie_id)
        ).first()
        if existing:
            raise ValueError("This Sortie already has reconnaissance set up")
        previous = list(
            session.execute(
                select(SortieReconAction)
                .where(SortieReconAction.sortie_id == sortie.replay_of_sortie_id)
                .order_by(SortieReconAction.position, SortieReconAction.id)
            ).scalars()
        )
        if not previous:
            raise ValueError("The previous attempt had no reconnaissance to copy")
        copies = []
        for index, old in enumerate(previous):
            try:
                unit_id, label = _unit_for_recon(session, sortie, old.campaign_unit_id)
            except ValueError:
                unit_id, label = None, None
            copy = SortieReconAction(
                sortie_id=sortie_id,
                position=index,
                name=old.name,
                campaign_unit_id=unit_id,
                unit_label=label,
                sp_cost=old.sp_cost,
                notes=old.notes,
            )
            session.add(copy)
            copies.append(copy)
        session.flush()
        for copy in copies:
            session.expunge(copy)
        return copies


def previous_attempt_has_recon(sortie_id: int) -> bool:
    with session_scope() as session:
        sortie = session.get(Sortie, sortie_id)
        if not sortie or sortie.replay_of_sortie_id is None:
            return False
        return (
            session.execute(
                select(SortieReconAction.id).where(
                    SortieReconAction.sortie_id == sortie.replay_of_sortie_id
                )
            ).first()
            is not None
        )
