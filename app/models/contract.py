from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign
    from .contract_unit import ContractUnit
    from .sortie import Sortie
    from .travel_event import TravelEvent


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(32), nullable=False)
    employer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type_of_action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scale: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    length_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_campaign_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    end_campaign_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_pay_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    support_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transportation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    salvage_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="contracts")
    roster_units: Mapped[list[ContractUnit]] = relationship(
        "ContractUnit",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractUnit.order",
    )
    sorties: Mapped[list[Sortie]] = relationship(
        "Sortie",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="Sortie.id",
    )
    travel_events: Mapped[list[TravelEvent]] = relationship(
        "TravelEvent", back_populates="contract"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "contract_number": self.contract_number,
            "employer": self.employer,
            "destination": self.destination,
            "type_of_action": self.type_of_action,
            "scale": self.scale,
            "length_months": self.length_months,
            "start_campaign_month": self.start_campaign_month,
            "end_campaign_month": self.end_campaign_month,
            "base_pay_percent": self.base_pay_percent,
            "support_percent": self.support_percent,
            "transportation_percent": self.transportation_percent,
            "salvage_rights": self.salvage_rights,
            "command_rights": self.command_rights,
            "status": self.status,
            "notes": self.notes,
        }
