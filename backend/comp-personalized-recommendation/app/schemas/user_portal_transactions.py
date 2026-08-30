"""Pydantic contracts for TaxWise taxpayer transaction portal."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from backend.shared.schemas.common import ORMBase

from app.schemas.taxable_income_monthly import ProfileTaxableIncomeMonthCoverage


class ProfileTransactionSummaryResponse(ORMBase):
    financial_profile_id: str
    tax_year: str | None = None
    assessment_year_label: str | None = None
    total_extracted_credits_lkr: Decimal
    total_taxable_lkr: Decimal
    total_non_taxable_lkr: Decimal
    review_count: int = 0
    visible_transaction_count: int = 0
    analyzed_transaction_count: int = 0
    compliance_score_pct: int | None = None
    submitted_statement_count: int = 0
    pending_statement_count: int = 0
    covered_month_count: int = 0
    missing_month_count: int = 0
    month_coverage: list[ProfileTaxableIncomeMonthCoverage] = Field(default_factory=list)


class UserPortalTransactionItem(ORMBase):
    extracted_transaction_id: str
    document_id: str
    tx_date: date
    description: str
    amount_lkr: Decimal
    direction: str
    semantic_category: str
    economic_event: str | None = None
    taxability_status: str
    taxable_amount_lkr: Decimal
    confidence: float | None = None
    certainty_tier: str | None = None
    needs_review: bool = False


class UserPortalTransactionsResponse(ORMBase):
    financial_profile_id: str
    tax_year: str | None = None
    items: list[UserPortalTransactionItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    include_all: bool = False


class UserPortalStatementItem(ORMBase):
    document_id: str
    filename: str
    submitted_by: str
    uploaded_at: datetime
    portal_status: str
    extracted_row_count: int = 0
    user_visible: bool = False


class UserPortalReasoningStep(ORMBase):
    step_key: str
    title: str
    detail: str
    is_decision: bool = False


class UserPortalNarrativeHit(ORMBase):
    class_key: str
    score: float
    description: str
    default_taxability_status: str


class UserPortalTransactionDetailResponse(ORMBase):
    extracted_transaction_id: str
    document_id: str
    tx_date: date
    description: str
    amount_lkr: Decimal
    direction: str
    bank_detected: str | None = None
    document_filename: str | None = None
    semantic_category: str
    economic_event: str | None = None
    tax_rule_code: str | None = None
    rule_reference: str | None = None
    explanation: str | None = None
    taxability_status: str
    taxable_amount_lkr: Decimal
    certainty_tier: str | None = None
    confidence: float | None = None
    class_source: str | None = None
    model_semantic_category: str | None = None
    review_reason: str | None = None
    evidence_needed: str | None = None
    decision_mode: str | None = None
    treatment: str | None = None
    narrative_hits: list[UserPortalNarrativeHit] = Field(default_factory=list)
    reasoning_steps: list[UserPortalReasoningStep] = Field(default_factory=list)
    taxonomy_version: str | None = None
    rulebook_version: str | None = None
    model_version: str | None = None
    flagged_for_adviser: bool = False
    flag_message: str | None = None


class UserPortalActivityGroup(ORMBase):
    class_key: str
    label: str
    transaction_count: int
    total_amount_lkr: Decimal
    taxable_amount_lkr: Decimal
    review_count: int = 0


class UserPortalActivityGroupsResponse(ORMBase):
    financial_profile_id: str
    tax_year: str | None = None
    groups: list[UserPortalActivityGroup] = Field(default_factory=list)


class UserTransactionFlagRequest(ORMBase):
    message: str | None = Field(default=None, max_length=2000)


class UserTransactionFlagResponse(ORMBase):
    extracted_transaction_id: str
    flagged: bool = True
    message: str | None = None
    created_at: datetime
