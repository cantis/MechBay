from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .lance_template import LanceTemplate


class LanceTemplateMiniature(Base):
    __tablename__ = "lance_template_miniatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lance_templates.id"), nullable=False
    )
    chassis_pattern: Mapped[str] = mapped_column(String(128), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    template: Mapped[LanceTemplate] = relationship("LanceTemplate", back_populates="miniatures")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "chassis_pattern": self.chassis_pattern,
            "order": self.order,
        }
