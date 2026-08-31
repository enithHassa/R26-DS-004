"""Synthetic monthly financial history per profile.

Real historical statements don't exist for these (synthetic) profiles — this
table holds a deterministically-generated backward trend (income, expenses,
balances) used to evidence whether a profile's trajectory supports adopting
a recommended strategy. See ``services.history_service`` for the generator.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class ProfileHistorySnapshot(TimestampMixin, Base):
    __tablename__ = "profile_history_snapshots"
    __table_args__ = (UniqueConstraint("profile_id", "snapshot_month", name="uq_profile_snapshot_month"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    liquid_savings: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    existing_investments: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_debt: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    epf_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    etf_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    savings_rate: Mapped[float] = mapped_column(nullable=False)
