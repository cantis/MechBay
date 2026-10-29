from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign_unit import CampaignUnit
    from .sortie import Sortie


class SortieReconAction(Base):
    """One Aces reconnaissance action entered during Sortie Setup.

    The SP cost is not charged when the action is entered; the Sortie's After-Sortie
    settlement includes the total of all its actions in that Sortie's expenses.
    """

    __tablename__ = "sortie_recon_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sortie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sorties.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    campaign_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign_units.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot so history still names the unit after it is sold, retired or destroyed.
    unit_label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sp_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    sortie: Mapped[Sortie] = relationship("Sortie")
    campaign_unit: Mapped[CampaignUnit | None] = relationship("CampaignUnit")
