from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_unit import CampaignUnit


class CampaignPilot(Base):
    __tablename__ = "campaign_pilots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    callsign: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gunnery: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    piloting: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    alpha_strike_skill: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    edge_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_abilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wounded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="alive")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_units.id", ondelete="SET NULL"), nullable=True
    )

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="pilots")
    preferred_unit: Mapped[CampaignUnit | None] = relationship(
        "CampaignUnit",
        back_populates="preferred_by_pilots",
        foreign_keys=[preferred_unit_id],
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "callsign": self.callsign,
            "gunnery": self.gunnery,
            "piloting": self.piloting,
            "alpha_strike_skill": self.alpha_strike_skill,
            "edge_tokens": self.edge_tokens,
            "edge_abilities": self.edge_abilities,
            "improvement_sp": self.improvement_sp,
            "wounds": self.wounds,
            "wounded": self.wounded,
            "status": self.status,
            "notes": self.notes,
            "preferred_unit_id": self.preferred_unit_id,
        }
