"""Evidence bundle schemas for Phase 4 RAG-grounded explanation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adaptive_tax_app.schemas.legal_rule_evidence import LegalRuleEvidence


class EvidenceChunk(BaseModel):
    """One Chroma hit used as legal evidence."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chunk_id: str
    text: str
    section_ref: str | None = None
    source_doc_id: str | None = None
    page: int | None = None
    score: float | None = None
    paragraph_ref: str | None = None
    instrument_type: str | None = None
    legal_precedence_tier: int | None = Field(
        default=None,
        description="Lower is better; legal authority rank (not similarity).",
    )
    is_operative_provision: bool | None = Field(
        default=None,
        description="True when chunk is tagged as operative Act text (not TOC).",
    )
    is_toc: bool | None = None
    is_header_footer: bool | None = None
    is_cross_reference: bool | None = None


class EvidenceSourceQuote(BaseModel):
    """Approved Postgres ``rule_source`` quote tied to a cited section."""

    model_config = ConfigDict(str_strip_whitespace=True)

    rule_source_id: str
    section: str
    amends_section: str | None = None
    source_quote: str
    concept_id: str | None = None
    maximum: float | None = None
    status: str
    amendment_job_id: str | None = None


class GraphModifiesEdge(BaseModel):
    """Neo4j ``(LawInstrument)-[:MODIFIES]->(Section)`` enrichment for the report."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amendment_source_doc_id: str
    section_uid: str
    section_label: str | None = None
    source_note: str | None = None
    effective_from: str | None = None


class StepEvidenceStatus(BaseModel):
    """Per-step evidence gate result (Phase 7b)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str
    evidence_available: bool
    section_labels: list[str] = Field(default_factory=list)
    paragraph_ref: str | None = None
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    rule_source_id: str | None = None
    reason: str | None = Field(
        default=None,
        description="Why evidence is unavailable when evidence_available is False.",
    )


class EvidenceBundle(BaseModel):
    """Structured evidence for GPT/fixture explanation (Phase 4)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chunks: list[EvidenceChunk] = Field(default_factory=list)
    source_quotes: list[EvidenceSourceQuote] = Field(default_factory=list)
    sections_retrieved: list[str] = Field(
        default_factory=list,
        description="Normalized section labels that yielded at least one chunk or quote.",
    )
    sections_queried: list[str] = Field(
        default_factory=list,
        description="Normalized labels derived from trace section_uids (attempted).",
    )
    graph_modifies: list[GraphModifiesEdge] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    step_evidence: list[StepEvidenceStatus] = Field(
        default_factory=list,
        description="Per-step local evidence gate (Phase 7b).",
    )
    legal_rule_evidence: list[LegalRuleEvidence] = Field(
        default_factory=list,
        description=(
            "Phase 11c: optional LegalRuleEvidence candidates from operative RAG "
            "chunks (structured legal evidence — not RAG calculation; "
            "executable always false)."
        ),
    )

    @property
    def insufficient_evidence(self) -> bool:
        """True when neither RAG chunks nor Postgres/bootstrap quotes are available."""
        return not self.chunks and not self.source_quotes

    def model_dump_public(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["insufficient_evidence"] = self.insufficient_evidence
        return data
