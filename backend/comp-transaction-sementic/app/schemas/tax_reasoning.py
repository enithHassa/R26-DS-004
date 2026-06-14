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
    items: list[AnalyzeBatchItemRequest] = Field(..., min_length=1, max_length=500)


class AnalyzeBatchItemResponse(BaseModel):
    row_id: str | None = None
    result: AnalyzeTransactionResponse


class AnalyzeBatchResponse(BaseModel):
    results: list[AnalyzeBatchItemResponse]
    processed_count: int


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
