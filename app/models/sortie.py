from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .contract import Contract
    from .sortie_unit import SortieUnit


class Sortie(Base):
    """One tabletop battle. Equivalent to a Track in Hot Spots / Chaos Campaign."""

    __tablename__ = "sorties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    campaign_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scale: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scenario_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planning")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="sorties")
    contract: Mapped[Contract] = relationship("Contract", back_populates="sorties")
    units: Mapped[list[SortieUnit]] = relationship(
        "SortieUnit",
        back_populates="sortie",
        cascade="all, delete-orphan",
        order_by="SortieUnit.order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "contract_id": self.contract_id,
            "name": self.name,
            "campaign_month": self.campaign_month,
            "scale": self.scale,
            "scenario_type": self.scenario_type,
            "location": self.location,
            "notes": self.notes,
            "outcome": self.outcome,
            "status": self.status,
        }
