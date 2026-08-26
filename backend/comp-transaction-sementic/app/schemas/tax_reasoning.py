"""HTTP models for taxonomy catalog and taxable-income rollups."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.shared.schemas.analyze import (
    AnalyzeTransactionResponse,
    ClassificationFacts,
)
from backend.shared.schemas.enums import TxnDirection


class IncomeTypeCatalogItem(BaseModel):
    class_key: str
    group: str
    description: str
    tax_rule_code: str
    default_taxability_status: str
    default_taxable_fraction: float
    treatment: str | None = None
    rule_reference: str
    explanation: str
    is_conditional: bool


class IncomeTypeCatalogResponse(BaseModel):
    taxonomy_version: str
    rulebook_version: str
    items: list[IncomeTypeCatalogItem]
    by_taxability_status: dict[str, list[IncomeTypeCatalogItem]]


class TaxableIncomeLineItem(BaseModel):
    class_key: str
    tax_rule_code: str | None = None
    taxability_status: str
    transaction_count: int
    gross_amount_lkr: Decimal
    taxable_amount_lkr: Decimal


class TaxableIncomeSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    total_taxable_lkr: Decimal
    total_excluded_lkr: Decimal
    review_count: int
    transaction_count: int
    taxable_lines: list[TaxableIncomeLineItem]
    non_taxable_lines: list[TaxableIncomeLineItem]
    review_lines: list[TaxableIncomeLineItem]


class TaxableIncomeSummaryRequest(BaseModel):
    date_from: date
    date_to: date
    bank_code: str | None = Field(default=None, max_length=16)


class AnalyzeBatchItemRequest(BaseModel):
    row_id: str | None = Field(default=None, max_length=128)
    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    facts: ClassificationFacts | None = None


class AnalyzeBatchRequest(BaseModel):
    bank_code: str | None = Field(default=None, max_length=16)
    document_type: str | None = Field(default=None, max_length=64)
    document_id: UUID | None = None
    persist: bool = False
    taxpayer_id: str | None = Field(default="taxpayer_00001", max_length=64)
    items: list[AnalyzeBatchItemRequest] = Field(..., min_length=1, max_length=500)


class AnalyzeBatchItemResponse(BaseModel):
    row_id: str | None = None
    result: AnalyzeTransactionResponse


class InflowSummaryResponse(BaseModel):
    guaranteed_taxable_inflows_lkr: Decimal
    guaranteed_non_taxable_inflows_lkr: Decimal
    indeterminate_inflows_lkr: Decimal
    outflow_lkr: Decimal
    credit_count: int
    debit_count: int
    indeterminate_credit_count: int
    potential_assessable_if_indet_is_income_lkr: Decimal
    exceeds_annual_personal_relief_if_indet_is_income: bool
    exceeds_monthly_relief_equivalent_if_indet_is_income: bool
    personal_relief_annual_lkr: Decimal
    personal_relief_monthly_equivalent_lkr: Decimal
    relief_hint: str


class AnalyzeBatchResponse(BaseModel):
    results: list[AnalyzeBatchItemResponse]
    processed_count: int
    inflow_summary: InflowSummaryResponse | None = None


class ApplyClassBatchItemRequest(BaseModel):
    row_id: str | None = Field(default=None, max_length=128)
    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    class_key: str = Field(..., min_length=1, max_length=64)
    facts: ClassificationFacts | None = None
    model_semantic_category: str | None = Field(default=None, max_length=64)


class ApplyClassBatchRequest(BaseModel):
    bank_code: str | None = Field(default=None, max_length=16)
    document_type: str | None = Field(default=None, max_length=64)
    items: list[ApplyClassBatchItemRequest] = Field(..., min_length=1, max_length=500)


class ApplyClassBatchResponse(BaseModel):
    results: list[AnalyzeBatchItemResponse]
    processed_count: int


class ActivitySummaryItemRequest(BaseModel):
    row_id: str | None = Field(default=None, max_length=128)
    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date | None = None
    direction: TxnDirection


class ActivitySummaryRequest(BaseModel):
    items: list[ActivitySummaryItemRequest] = Field(..., min_length=1, max_length=1000)


class ActivitySummaryMember(BaseModel):
    row_id: str | None = None
    tx_date: date | None = None
    description: str
    direction: TxnDirection
    amount_lkr: Decimal


class ActivitySummaryGroup(BaseModel):
    group_key: str
    label: str
    hint: str
    direction: TxnDirection
    intent_tag: str
    merchant_family: str | None = None
    count: int
    total_lkr: Decimal
    members: list[ActivitySummaryMember]


class ActivitySummaryResponse(BaseModel):
    group_count: int
    transaction_count: int
    groups: list[ActivitySummaryGroup]
