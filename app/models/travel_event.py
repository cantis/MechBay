from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .contract import Contract


class TravelEvent(Base):
    __tablename__ = "travel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    origin: Mapped[str] = mapped_column(String(128), nullable=False)
    destination: Mapped[str] = mapped_column(String(128), nullable=False)
    departure_campaign_month: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_campaign_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jump_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    covered_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_warchest_impact: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_transit")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="travel_events")
    contract: Mapped[Contract | None] = relationship("Contract", back_populates="travel_events")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_campaign_month": self.departure_campaign_month,
            "arrival_campaign_month": self.arrival_campaign_month,
            "jump_count": self.jump_count,
            "gross_cost": self.gross_cost,
            "covered_amount": self.covered_amount,
            "actual_warchest_impact": self.actual_warchest_impact,
            "status": self.status,
            "notes": self.notes,
        }
