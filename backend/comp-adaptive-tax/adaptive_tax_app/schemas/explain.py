"""Explain-tax request/response DTOs (Phase 4 RAG-grounded narrative)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
)
from adaptive_tax_app.schemas.evidence import EvidenceBundle

DISCLAIMER = "Research prototype — not legal advice."


class ExplainStepV1(BaseModel):
    """One step narrative grounded in evidence chunk / rule_source ids."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str
    narrative: str
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    rule_source_id: str | None = Field(
        default=None,
        description="Postgres rule_source UUID when a quote was used; else null.",
    )
    evidence_unavailable: bool = Field(
        default=False,
        description=(
            "True when this step lacks step-local Act-backed evidence "
            "(Phase 7b). Narrative is the unavailable message; GPT must not invent."
        ),
    )


class ExplainNarrativePayload(BaseModel):
    """Structured payload produced by fixture template or OpenAI (pre-envelope)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str
    sections_cited: list[str] = Field(default_factory=list)
    steps_explained: list[ExplainStepV1] = Field(default_factory=list)
    final_tax_lkr: str
    disclaimer: str = DISCLAIMER


class ExplainTaxRequestV1(BaseModel):
    """``POST /api/v1/explain`` body — prefer ``calc_id``; inline calc for tests."""

    model_config = ConfigDict(str_strip_whitespace=True)

    calc_id: str | None = Field(
        default=None,
        description="UUID from POST /calculate (preferred).",
    )
    calculation: CalculateTaxResponseV1 | None = Field(
        default=None,
        description="Inline calculate response for unit tests without disk store.",
    )
    request: CalculateTaxRequestV1 | None = Field(
        default=None,
        description="Optional original calculate request (unused by narrate; for audit).",
    )

    @model_validator(mode="after")
    def _require_calc_id_or_calculation(self) -> ExplainTaxRequestV1:
        if not (self.calc_id or "").strip() and self.calculation is None:
            raise ValueError("provide calc_id or calculation")
        return self


class ExplainTaxResponseV1(BaseModel):
    """RAG-grounded explanation envelope (Phase 4 contract)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str
    sections_cited: list[str] = Field(default_factory=list)
    steps_explained: list[ExplainStepV1] = Field(default_factory=list)
    final_tax_lkr: str
    disclaimer: str = DISCLAIMER
    insufficient_evidence: bool = False
    sections_retrieved: list[str] = Field(default_factory=list)
    calc_id: str = ""
    # Report UI panels (chunks / quotes / MODIFIES); empty when insufficient.
    evidence: EvidenceBundle | None = None
