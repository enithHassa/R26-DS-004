"""HTTP-facing compose models for ``POST /v1/transactions/analyze``."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.shared.schemas.confidence import ConfidenceReport
from backend.shared.schemas.enums import TxnDirection
from backend.shared.schemas.taxability import TaxabilityOutput


class NarrativeContextHit(BaseModel):
    class_key: str
    score: float = Field(..., ge=0.0, le=1.0)
    description: str
    default_taxability_status: str


class ClassificationFacts(BaseModel):
    """Optional facts for conditional IRA rules (gifts, reimbursements, etc.)."""

    counterparty_type: str | None = Field(
        default=None,
        description="e.g. relative, employer, unknown",
    )
    has_supporting_receipt: bool | None = None
    taxpayer_id: str | None = Field(
        default=None,
        description="Linked-account profile id, e.g. taxpayer_00001.",
    )
    auditor_evidence: str | None = Field(
        default=None,
        description="invoice, loan, gift, shared_expense, or own_transfer",
    )


class AnalyzeTransactionRequest(BaseModel):
    """Request body — subset of fields needed for a single-shot analysis."""

    raw_desc: str = Field(..., min_length=1)
    amount_lkr: Decimal = Field(..., decimal_places=2)
    tx_date: date
    direction: TxnDirection
    bank_code: str | None = Field(None, max_length=16)
    document_type: str | None = Field(None, max_length=64)
    facts: ClassificationFacts | None = None
    persist: bool = False


class AnalyzeTransactionResponse(BaseModel):
    """Full analysis envelope returned by the API."""

    transaction_id: UUID
    semantic_category: str = Field(..., description="Predicted semantic label.")
    economic_event: str | None = None
    tax_rule_code: str | None = Field(None, description="IRD-grounded rule code when mapped.")
    taxability: TaxabilityOutput
    confidence_report: ConfidenceReport
    taxonomy_version: str
    rulebook_version: str
    decision_mode: str
    rule_reference: str
    explanation: str
    review_reason: str | None = None
    condition_id_matched: str | None = None
    model_semantic_category: str | None = Field(
        default=None,
        description="Classifier label before narrative fusion or manual override.",
    )
    class_source: str = Field(
        default="model",
        description="model, narrative, deterministic, or manual.",
    )
    narrative_interpretation: str | None = None
    narrative_hits: list[NarrativeContextHit] = Field(default_factory=list)
    certainty_tier: str | None = Field(
        default=None,
        description="guaranteed_taxable, guaranteed_non_taxable, or indeterminate.",
    )
    intent_tag: str | None = None
    channel: str | None = None
    evidence_needed: str | None = None
    layer1_note: str | None = None
