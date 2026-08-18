from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .campaign_lance import CampaignLance
    from .campaign_pilot import CampaignPilot
    from .miniature import Miniature


class CampaignUnit(Base):
    __tablename__ = "campaign_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    campaign_lance_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_lances.id"), nullable=True
    )
    miniature_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("miniatures.id", ondelete="SET NULL"), nullable=True
    )
    series: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unique_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chassis: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    faction: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mul_unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tonnage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    point_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_type_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mul_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_omni: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    condition: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    miniature_missing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="units")
    lance: Mapped[CampaignLance | None] = relationship("CampaignLance", back_populates="units")
    miniature: Mapped[Miniature | None] = relationship("Miniature")
    preferred_by_pilots: Mapped[list[CampaignPilot]] = relationship(
        "CampaignPilot",
        back_populates="preferred_unit",
        foreign_keys="CampaignPilot.preferred_unit_id",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "campaign_lance_id": self.campaign_lance_id,
            "miniature_id": self.miniature_id,
            "series": self.series,
            "unique_id": self.unique_id,
            "prefix": self.prefix,
            "chassis": self.chassis,
            "type": self.type,
            "faction": self.faction,
            "mul_unit_id": self.mul_unit_id,
            "variant": self.variant,
            "class_name": self.class_name,
            "tonnage": self.tonnage,
            "point_value": self.point_value,
            "is_omni": self.is_omni,
            "condition": self.condition,
            "available": self.available,
            "miniature_missing": self.miniature_missing,
            "notes": self.notes,
            "order": self.order,
        }
