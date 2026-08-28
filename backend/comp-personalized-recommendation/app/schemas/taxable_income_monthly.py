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


class ProfileTaxableIncomeMonthlyResponse(ORMBase):
    financial_profile_id: str
    tax_year: str | None = None
    total_taxable_lkr: Decimal
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
