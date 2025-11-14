from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .lance_template_miniature import LanceTemplateMiniature


class LanceTemplate(Base):
    __tablename__ = "lance_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    miniatures: Mapped[list[LanceTemplateMiniature]] = relationship(
        "LanceTemplateMiniature",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="LanceTemplateMiniature.order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
