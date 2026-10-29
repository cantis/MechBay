from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_unit import CampaignUnit


class CampaignLance(Base):
    __tablename__ = "campaign_lances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    special_rules: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="lances")
    units: Mapped[list[CampaignUnit]] = relationship(
        "CampaignUnit",
        back_populates="lance",
        order_by="CampaignUnit.order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "order": self.order,
            "special_rules": self.special_rules,
        }
