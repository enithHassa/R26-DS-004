"""Monthly taxable income rollup per financial profile (auditor hub)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.shared.config.database import Base


class ProfileTaxableIncomeMonthly(Base):
    __tablename__ = "profile_taxable_income_monthly"
    __table_args__ = (
        UniqueConstraint(
            "financial_profile_id",
            "tax_year",
            "calendar_month",
            "class_key",
            name="uq_profile_taxable_income_monthly_bucket",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    financial_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tax_year: Mapped[str | None] = mapped_column(String(8), nullable=True)
    calendar_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    class_key: Mapped[str] = mapped_column(String(64), nullable=False)
    taxable_amount_lkr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
