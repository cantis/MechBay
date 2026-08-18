from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign import Campaign


class WarchestTransaction(Base):
    __tablename__ = "warchest_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    campaign_month: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    gross_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    covered_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="transactions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "campaign_month": self.campaign_month,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "gross_amount": self.gross_amount,
            "covered_amount": self.covered_amount,
            "actual_amount": self.actual_amount,
            "resulting_balance": self.resulting_balance,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
