"""Pydantic contracts for profile-scoped monthly taxable income rollups."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from backend.shared.schemas.common import ORMBase


class ProfileTaxableIncomeMonthlyLine(ORMBase):
    tax_year: str | None = None
    calendar_month: date
    class_key: str
    taxable_amount_lkr: Decimal
    transaction_count: int
    source_document_ids: list[str] = Field(default_factory=list)
    computed_at: datetime


class ProfileTaxableIncomeMonthCoverage(ORMBase):
    """One calendar month within a Sri Lanka YA (Apr–Mar)."""

    calendar_month: date
    month_label: str
    status: str = Field(
        description="covered = extracted bank rows exist; missing = no extracted activity",
    )
    extracted_transaction_count: int = 0
    classified_transaction_count: int = 0
    taxable_credit_count: int = 0
    taxable_amount_lkr: Decimal = Decimal("0.00")


class ProfileTaxableIncomeMonthlyResponse(ORMBase):
    financial_profile_id: str
    tax_year: str | None = None
    assessment_year_label: str | None = None
    ya_period_start: date | None = None
    ya_period_end: date | None = None
    total_taxable_lkr: Decimal
    covered_month_count: int = 0
    missing_month_count: int = 0
    month_coverage: list[ProfileTaxableIncomeMonthCoverage] = Field(default_factory=list)
    lines: list[ProfileTaxableIncomeMonthlyLine]


class ProfileTaxableIncomeMonthDetailLine(ORMBase):
    extracted_transaction_id: str
    document_id: str
    tx_date: date
    description: str
    gross_amount_lkr: Decimal
    taxable_amount_lkr: Decimal
    class_key: str
    taxability_status: str


class ProfileTaxableIncomeMonthDetailResponse(ORMBase):
    financial_profile_id: str
    calendar_month: date
    tax_year: str | None = None
    total_taxable_lkr: Decimal
    lines: list[ProfileTaxableIncomeMonthDetailLine]
