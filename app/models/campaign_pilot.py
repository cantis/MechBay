from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_unit import CampaignUnit
    from .pilot_advancement_event import PilotAdvancementEvent


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
    # Aces Named Pilot fields (Chaos pilots leave these at their defaults).
    pilot_type: Mapped[str | None] = mapped_column(String(2), nullable=True)
    skill_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ability_sp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mvp_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preferred_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_units.id", ondelete="SET NULL"), nullable=True
    )

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="pilots")
    preferred_unit: Mapped[CampaignUnit | None] = relationship(
        "CampaignUnit",
        back_populates="preferred_by_pilots",
        foreign_keys=[preferred_unit_id],
    )

    advancements: Mapped[list[PilotAdvancementEvent]] = relationship(
        "PilotAdvancementEvent",
        back_populates="pilot",
        order_by="PilotAdvancementEvent.sequence",
    )

    @property
    def display_name(self) -> str:
        return self.callsign or self.name

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
            "pilot_type": self.pilot_type,
            "skill_sp": self.skill_sp,
            "edge_sp": self.edge_sp,
            "ability_sp": self.ability_sp,
            "total_sp_earned": self.total_sp_earned,
            "mvp_count": self.mvp_count,
        }
