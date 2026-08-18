from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign_lance import CampaignLance
    from .campaign_pilot import CampaignPilot
    from .campaign_unit import CampaignUnit
    from .contract import Contract
    from .damage_event import DamageEvent
    from .pilot_injury_event import PilotInjuryEvent
    from .rearm_order import RearmOrder
    from .repair_order import RepairOrder
    from .sortie import Sortie
    from .travel_event import TravelEvent
    from .unit_configuration_event import UnitConfigurationEvent
    from .warchest_transaction import WarchestTransaction


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planning")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_campaign_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    starting_bt_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starting_bt_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    warchest_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scale: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_force_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mul_faction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mul_era_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mul_faction_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mul_era_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    lances: Mapped[list[CampaignLance]] = relationship(
        "CampaignLance",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignLance.order",
    )
    units: Mapped[list[CampaignUnit]] = relationship(
        "CampaignUnit",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignUnit.order",
    )
    pilots: Mapped[list[CampaignPilot]] = relationship(
        "CampaignPilot",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignPilot.id",
    )
    transactions: Mapped[list[WarchestTransaction]] = relationship(
        "WarchestTransaction",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="WarchestTransaction.id",
    )
    travel_events: Mapped[list[TravelEvent]] = relationship(
        "TravelEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="TravelEvent.id",
    )
    contracts: Mapped[list[Contract]] = relationship(
        "Contract",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Contract.id",
    )
    sorties: Mapped[list[Sortie]] = relationship(
        "Sortie",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Sortie.id",
    )
    damage_events: Mapped[list[DamageEvent]] = relationship(
        "DamageEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="DamageEvent.id",
    )
    repair_orders: Mapped[list[RepairOrder]] = relationship(
        "RepairOrder",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="RepairOrder.id",
    )
    rearm_orders: Mapped[list[RearmOrder]] = relationship(
        "RearmOrder",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="RearmOrder.id",
    )
    injury_events: Mapped[list[PilotInjuryEvent]] = relationship(
        "PilotInjuryEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="PilotInjuryEvent.id",
    )
    configuration_events: Mapped[list[UnitConfigurationEvent]] = relationship(
        "UnitConfigurationEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="UnitConfigurationEvent.id",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "is_active": self.is_active,
            "current_campaign_month": self.current_campaign_month,
            "starting_bt_year": self.starting_bt_year,
            "starting_bt_month": self.starting_bt_month,
            "current_location": self.current_location,
            "warchest_balance": self.warchest_balance,
            "reputation": self.reputation,
            "scale": self.scale,
            "notes": self.notes,
            "source_force_name": self.source_force_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
