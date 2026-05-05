"""Schemas for document upload and transaction extraction endpoints."""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.shared.schemas.enums import TxnDirection
from backend.shared.schemas.transaction import Transaction


class ExtractedTransactionInput(BaseModel):
    """Normalized transaction extracted from an uploaded file."""

    row_index: int = Field(..., ge=1)
    tx_date: str = Field(..., description="ISO date string (YYYY-MM-DD).")
    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    direction: TxnDirection
    bank_code: str | None = Field(default=None, max_length=16)
    parse_confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class DocumentExtractResponse(BaseModel):
    """Response for extraction endpoint with persisted rows."""

    document_name: str
    content_type: str | None = None
    file_type: str
    bank_code_hint: str | None = None
    ocr_pending: bool = False
    extracted_count: int
    persisted_count: int
    warnings: list[str] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
