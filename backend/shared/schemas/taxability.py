"""Taxability inference output — persists to ``taxability_outputs``."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.shared.schemas.enums import TaxabilityStatus
from backend.shared.schemas.evidence import EvidenceChain


class TaxabilityOutput(BaseModel):
    """Structured taxability decision + explainability payload."""

    model_config = ConfigDict(from_attributes=True)

    tx_id: UUID
    taxability_status: TaxabilityStatus
    taxable_amount: Decimal | None = Field(
        None,
        decimal_places=2,
        description="Taxable portion in LKR when estimable.",
    )
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    evidence: EvidenceChain | None = None
    model_version: str | None = Field(None, max_length=64)
    model_run_id: UUID | None = None
