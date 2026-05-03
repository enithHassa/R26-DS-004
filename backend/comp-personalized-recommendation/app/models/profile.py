"""Financial profile ORM model (FR1, FR2).

Mirrors ``app.schemas.profile.FinancialProfileBase``. Phase 2 extends the
table with demographics, EPF/ETF balances, debt servicing, insurance
contributions, and a snapshot of the tax year so we can re-derive features
deterministically.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class FinancialProfile(TimestampMixin, Base):
    __tablename__ = "financial_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="other", nullable=False)
    district: Mapped[str] = mapped_column(String(64), default="Colombo", nullable=False, index=True)
    marital_status: Mapped[str] = mapped_column(String(16), default="single", nullable=False)
    occupation: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dependents: Mapped[int] = mapped_column(default=0, nullable=False)
    years_employed: Mapped[int] = mapped_column(default=0, nullable=False)

    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_debt_service: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    liquid_savings: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    existing_investments: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_debt: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    epf_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    etf_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    health_insurance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    life_insurance_premium_annual: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    home_loan_interest_annual: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    donations_annual: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    risk_tolerance: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    investment_horizon_years: Mapped[int] = mapped_column(default=10, nullable=False)
    income_sources: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    tax_year: Mapped[str] = mapped_column(String(8), default="2024_25", nullable=False, index=True)
