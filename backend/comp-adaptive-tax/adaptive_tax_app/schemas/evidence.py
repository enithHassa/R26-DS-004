"""Evidence bundle schemas for Phase 4 RAG-grounded explanation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceChunk(BaseModel):
    """One Chroma hit used as legal evidence."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chunk_id: str
    text: str
    section_ref: str | None = None
    source_doc_id: str | None = None
    page: int | None = None
    score: float | None = None


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

    @property
    def insufficient_evidence(self) -> bool:
        """True when neither RAG chunks nor Postgres quotes are available."""
        return not self.chunks and not self.source_quotes

    def model_dump_public(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["insufficient_evidence"] = self.insufficient_evidence
        return data
