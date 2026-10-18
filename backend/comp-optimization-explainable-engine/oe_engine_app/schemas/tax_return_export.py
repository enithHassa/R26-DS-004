"""Request payload for multi-sheet tax return Excel export."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaxpayerHeader(BaseModel):
    full_name: str = ""
    tin: str = ""
    assessment_year_label: str = ""
    reference_code: str = ""


class InterestLine(BaseModel):
    bank: str = ""
    source_type: str = ""
    withholding_agent_tin: str = ""
    wht_certificate_no: str = ""
    date: str = ""
    account_or_fd_no: str = ""
    type: str = ""  # SAVINGS | FD
    fd_amount: float | None = None
    gross_interest: float = 0
    wht: float = 0


class PensionLine(BaseModel):
    pen_date: str = ""
    bpen: float = 0
    cla: float = 0
    ota: float = 0
    spa: float = 0
    dsa: float = 0
    maa: float = 0
    sur: float = 0
    tded: float = 0
    tpen: float = 0
    pnet: float = 0


class PensionSchedule(BaseModel):
    pensioner_name: str = ""
    status_note: str = ""
    pension_number: str = ""
    lines: list[PensionLine] = Field(default_factory=list)


class TaxableSummaryLine(BaseModel):
    class_key: str = ""
    calendar_month: str = ""
    taxable_amount_lkr: float = 0
    transaction_count: int = 0


class TaxableIncomeSummary(BaseModel):
    """Transaction Semantic (Comp1) taxable income rollup."""

    total_taxable_lkr: float = 0
    covered_month_count: int = 0
    missing_month_count: int = 0
    lines: list[TaxableSummaryLine] = Field(default_factory=list)


class IncomeBreakdown(BaseModel):
    employment: float = 0
    interest: float = 0
    business: float = 0
    rents: float = 0
    other: float = 0
    investment: float = 0


class TaxReturnExportRequest(BaseModel):
    """Assembled export payload from Profile + Comp1 + OE calculate."""

    header: TaxpayerHeader
    income_breakdown: IncomeBreakdown = Field(default_factory=IncomeBreakdown)
    calculate_result: dict[str, Any]
    interest_lines: list[InterestLine] = Field(default_factory=list)
    pension: PensionSchedule | None = None
    taxable_summary: TaxableIncomeSummary | None = None
