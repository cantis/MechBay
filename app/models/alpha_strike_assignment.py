from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .force_miniature import ForceMiniature


class AlphaStrikeAssignment(Base):
    __tablename__ = "alpha_strike_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    force_miniature_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("force_miniatures.id"), nullable=False, unique=True
    )
    mul_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant: Mapped[str] = mapped_column(String(64), nullable=False)
    class_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tonnage: Mapped[int] = mapped_column(Integer, nullable=False)
    point_value: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_type_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    mul_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    force_miniature: Mapped[ForceMiniature] = relationship(
        "ForceMiniature", back_populates="alpha_strike_assignment"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "force_miniature_id": self.force_miniature_id,
            "mul_unit_id": self.mul_unit_id,
            "variant": self.variant,
            "class_name": self.class_name,
            "tonnage": self.tonnage,
            "point_value": self.point_value,
            "unit_type_id": self.unit_type_id,
            "unit_type_name": self.unit_type_name,
            "display_name": self.display_name,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
        }
