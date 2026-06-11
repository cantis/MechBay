from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .force import Force


class AlphaStrikeForce(Base):
    __tablename__ = "alpha_strike_forces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    force_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("forces.id"), nullable=False, unique=True
    )
    mul_faction_id: Mapped[int] = mapped_column(Integer, nullable=False)
    mul_era_id: Mapped[int] = mapped_column(Integer, nullable=False)
    faction_name: Mapped[str] = mapped_column(String(128), nullable=False)
    era_name: Mapped[str] = mapped_column(String(128), nullable=False)
    point_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fudge_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    force: Mapped[Force] = relationship("Force", back_populates="alpha_strike")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "force_id": self.force_id,
            "mul_faction_id": self.mul_faction_id,
            "mul_era_id": self.mul_era_id,
            "faction_name": self.faction_name,
            "era_name": self.era_name,
            "point_budget": self.point_budget,
            "fudge_percent": self.fudge_percent,
        }
