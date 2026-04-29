"""Canonical transaction payloads — raw ingestion and preprocessor output."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.shared.schemas.enums import TxnDirection


class Transaction(BaseModel):
    """Bank transaction as ingested from CSV/API or read from ``transactions``.

    ``id`` is omitted when creating a new row; present when returning persisted rows.
    """

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: UUID | None = None
    raw_desc: str = Field(..., min_length=1)
    normalized_desc: str | None = None
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    bank_code: str | None = Field(None, max_length=16)
    source_type: str | None = Field(None, max_length=32)
    raw_payload: dict[str, Any] | None = None


class NormalizedTransaction(BaseModel):
    """Output of preprocessing / normalization (WP4).

    Deterministic, idempotent representation fed to the semantic classifier.
    """

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    transaction_id: UUID | None = None
    normalized_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    bank_code: str | None = Field(None, max_length=16)
    extras: dict[str, Any] | None = Field(
        None,
        description="Optional NLP hints, detected language codes, masking metadata, etc.",
    )
