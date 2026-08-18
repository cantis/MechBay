from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_unit import CampaignUnit


class UnitConfigurationEvent(Base):
    __tablename__ = "unit_configuration_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    campaign_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_units.id"), nullable=False
    )
    campaign_month: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mul_unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mul_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="configuration_events")
    unit: Mapped[CampaignUnit] = relationship("CampaignUnit")
