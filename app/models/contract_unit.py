"""Association of a Campaign Unit committed to a Contract force."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import Base

if TYPE_CHECKING:
    from .campaign_unit import CampaignUnit
    from .contract import Contract


class ContractUnit(Base):
    __tablename__ = "contract_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    campaign_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_units.id"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    contract: Mapped[Contract] = relationship("Contract", back_populates="roster_units")
    campaign_unit: Mapped[CampaignUnit] = relationship("CampaignUnit")
