from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .sortie import Sortie


class AcesSortieReport(Base):
    """Accounting and narrative snapshot for one successful Aces Sortie.

    Created when After-Sortie is applied; once ``finalized`` it can no longer change, so the
    Sortie Report never depends on current pilot/unit/campaign state.
    """

    __tablename__ = "aces_sortie_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sortie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    objective_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    force_pv: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    primary_objective_base: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    primary_objective_adjusted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    secondary_objective_base: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    secondary_objective_adjusted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    other_income: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_income: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    expense_reconnaissance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expense_waypoint: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expense_rearming: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expense_personnel: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expense_repairs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expense_other: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_expenses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    earnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_pilot_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pilot_sp_pool: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    warchest_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warchest_remainder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warchest_after_accounting: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON ledger lines decided at Apply and posted to the Warchest at Finalize.
    pending_ledger: Mapped[str | None] = mapped_column(Text, nullable=True)

    story_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    sortie: Mapped[Sortie] = relationship("Sortie")


@event.listens_for(AcesSortieReport, "before_update")
def _lock_finalized(mapper, connection, target) -> None:  # noqa: ARG001
    history = inspect(target).attrs.finalized.history
    was_final = history.deleted[0] if history.deleted else target.finalized
    if was_final:
        raise ValueError("A finalized Sortie Report is immutable")


class SortiePilotShare(Base):
    """A Named Pilot's improvement entitlement from one Aces Sortie (and its allocation)."""

    __tablename__ = "sortie_pilot_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sortie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="CASCADE"), nullable=False
    )
    campaign_pilot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_pilots.id"), nullable=False
    )
    callsign: Mapped[str] = mapped_column(String(64), nullable=False)
    pilot_type: Mapped[str | None] = mapped_column(String(2), nullable=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    max_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    awarded_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mvp_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    advancement_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
