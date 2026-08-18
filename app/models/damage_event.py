from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_unit import CampaignUnit
    from .sortie import Sortie


class DamageEvent(Base):
    __tablename__ = "damage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    campaign_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_units.id"), nullable=False
    )
    sortie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="SET NULL"), nullable=True
    )
    campaign_month: Mapped[int] = mapped_column(Integer, nullable=False)
    damage_category: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="damage_events")
    unit: Mapped[CampaignUnit] = relationship("CampaignUnit")
    sortie: Mapped[Sortie | None] = relationship("Sortie")
