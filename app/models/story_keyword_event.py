from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .sortie import Sortie

STORY_KEYWORD_ACTIONS = ("acquired", "removed")


class StoryKeywordEvent(Base):
    """Immutable Aces Story Keyword history; the current set is derived from these rows."""

    __tablename__ = "story_keyword_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    sortie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="SET NULL"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    sortie: Mapped[Sortie | None] = relationship("Sortie")


@event.listens_for(StoryKeywordEvent, "before_update")
def _reject_update(mapper, connection, target) -> None:  # noqa: ARG001
    raise ValueError("Story Keyword history is immutable")
