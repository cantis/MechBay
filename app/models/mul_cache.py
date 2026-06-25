from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import Base


class MulCache(Base):
    __tablename__ = "mul_cache"

    cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
