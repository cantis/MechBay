from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign_pilot import CampaignPilot
    from .campaign_unit import CampaignUnit
    from .sortie import Sortie


class SortieUnit(Base):
    """Frozen pilot/unit/configuration used in a Sortie."""

    __tablename__ = "sortie_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sortie_id: Mapped[int] = mapped_column(Integer, ForeignKey("sorties.id"), nullable=False)
    campaign_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_units.id", ondelete="SET NULL"), nullable=True
    )
    campaign_lance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lance_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chassis: Mapped[str] = mapped_column(String(128), nullable=False)
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
    configuration_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reconfiguration_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    campaign_pilot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_pilots.id", ondelete="SET NULL"), nullable=True
    )
    pilot_name: Mapped[str] = mapped_column(String(128), nullable=False)
    pilot_callsign: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gunnery: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    piloting: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    alpha_strike_skill: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    is_generic_crew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    damage_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    needs_rearm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pilot_wounded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pilot_killed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sortie: Mapped[Sortie] = relationship("Sortie", back_populates="units")
    campaign_unit: Mapped[CampaignUnit | None] = relationship("CampaignUnit")
    campaign_pilot: Mapped[CampaignPilot | None] = relationship("CampaignPilot")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sortie_id": self.sortie_id,
            "campaign_unit_id": self.campaign_unit_id,
            "lance_name": self.lance_name,
            "chassis": self.chassis,
            "variant": self.variant,
            "point_value": self.point_value,
            "is_omni": self.is_omni,
            "configuration_changed": self.configuration_changed,
            "reconfiguration_cost": self.reconfiguration_cost,
            "campaign_pilot_id": self.campaign_pilot_id,
            "pilot_name": self.pilot_name,
            "is_generic_crew": self.is_generic_crew,
            "alpha_strike_skill": self.alpha_strike_skill,
            "order": self.order,
        }
