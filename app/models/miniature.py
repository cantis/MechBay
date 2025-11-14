from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import Base


class Miniature(Base):
    __tablename__ = "miniatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Changed to Integer per new requirement
    unique_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    chassis: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=True)
    tray_id: Mapped[str] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "unique_id": self.unique_id,
            "prefix": self.prefix,
            "chassis": self.chassis,
            "type": self.type,
            "status": self.status,
            "tray_id": self.tray_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
