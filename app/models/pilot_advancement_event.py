from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign_pilot import CampaignPilot
    from .sortie import Sortie


class PilotAdvancementEvent(Base):
    """Immutable Aces Named Pilot advancement record (creation or Sortie improvement)."""

    __tablename__ = "pilot_advancement_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    campaign_pilot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_pilots.id"), nullable=False
    )
    sortie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="SET NULL"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    participation_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    sp_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mvp_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skill_sp_allocated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_sp_allocated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ability_sp_allocated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skill_sp_total: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_sp_total: Mapped[int] = mapped_column(Integer, nullable=False)
    ability_sp_total: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_after: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_tokens_after: Mapped[int] = mapped_column(Integer, nullable=False)
    ability_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    new_abilities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    total_sp_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    pilot: Mapped[CampaignPilot] = relationship("CampaignPilot", back_populates="advancements")
    sortie: Mapped[Sortie | None] = relationship("Sortie")


@event.listens_for(PilotAdvancementEvent, "before_update")
def _reject_update(mapper, connection, target) -> None:  # noqa: ARG001
    raise ValueError("Pilot advancement history is immutable")
