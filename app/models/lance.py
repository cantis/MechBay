from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .force import Force
    from .force_miniature import ForceMiniature


class Lance(Base):
    __tablename__ = "lances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    force_id: Mapped[int] = mapped_column(Integer, ForeignKey("forces.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    force: Mapped[Force] = relationship("Force", back_populates="lances")
    miniatures: Mapped[list[ForceMiniature]] = relationship(
        "ForceMiniature",
        back_populates="lance",
        cascade="all, delete-orphan",
        order_by="ForceMiniature.order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "force_id": self.force_id,
            "name": self.name,
            "order": self.order,
        }
