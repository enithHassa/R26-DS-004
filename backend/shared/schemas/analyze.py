"""HTTP-facing compose models for ``POST /v1/transactions/analyze``."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.shared.schemas.confidence import ConfidenceReport
from backend.shared.schemas.enums import TxnDirection
from backend.shared.schemas.taxability import TaxabilityOutput


class AnalyzeTransactionRequest(BaseModel):
    """Request body — subset of fields needed for a single-shot analysis."""

    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    bank_code: str | None = Field(None, max_length=16)


class AnalyzeTransactionResponse(BaseModel):
    """Full analysis envelope returned by the API (stub until WP9)."""

    transaction_id: UUID
    semantic_category: str = Field(..., description="Predicted semantic label.")
    economic_event: str | None = None
    tax_rule_code: str | None = Field(None, description="IRD-grounded rule code when mapped.")
    taxability: TaxabilityOutput
    confidence_report: ConfidenceReport
