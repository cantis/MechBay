from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .lance import Lance
    from .miniature import Miniature


class ForceMiniature(Base):
    __tablename__ = "force_miniatures"
    __table_args__ = (UniqueConstraint("lance_id", "miniature_id", name="uix_lance_miniature"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lance_id: Mapped[int] = mapped_column(Integer, ForeignKey("lances.id"), nullable=False)
    miniature_id: Mapped[int] = mapped_column(Integer, ForeignKey("miniatures.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    lance: Mapped[Lance] = relationship("Lance", back_populates="miniatures")
    miniature: Mapped[Miniature] = relationship("Miniature")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lance_id": self.lance_id,
            "miniature_id": self.miniature_id,
            "order": self.order,
        }
