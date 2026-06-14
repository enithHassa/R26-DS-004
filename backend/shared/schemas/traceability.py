"""Shared traceability contracts for evidence-backed answers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """One citation to a legal corpus chunk supporting an answer."""

    source_doc_id: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    excerpt: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TraceabilityMetadata(BaseModel):
    """Version metadata used to reproduce answer generation."""

    run_id: str = Field(..., min_length=1)
    corpus_version: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)
    rule_engine_version: str = Field(..., min_length=1)


class EvidenceBackedAnswer(BaseModel):
    """Standard API response envelope for legal answers."""

    answer_text: str = Field(..., min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    traceability: TraceabilityMetadata
