"""Graph context schemas returned alongside retrieval hits (Phase 4)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A single node returned from the knowledge graph."""

    label: str = Field(..., description="Neo4j node label (e.g. Concept, Relief, RateBand).")
    node_id: str = Field(..., description="Primary identifier property value.")
    display_name: str | None = Field(default=None, description="Human-readable name.")
    authority_class: str | None = Field(default=None, description="Lex specialis authority class.")
    tier: str | None = Field(default=None, description="A/B corpus tier when applicable.")
    extra: dict | None = Field(default=None, description="Additional node properties.")


class ConceptNode(BaseModel):
    concept_id: str
    canonical_name: str | None = None
    aliases: list[str] = []
    notes: str | None = None


class ReliefNode(BaseModel):
    relief_id: str
    display_name: str | None = None
    statutory_label: str | None = None
    description: str | None = None
    source_doc_id: str | None = None


class RateBandNode(BaseModel):
    rate_band_id: str
    band_label: str | None = None
    band_type: str | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    rate_percent: float | None = None
    currency: str | None = "LKR"
    effective_start_date: str | None = None
    effective_end_date: str | None = None


class ProcedureMilestoneNode(BaseModel):
    milestone_id: str
    milestone_kind: str | None = None
    display_name: str | None = None
    description: str | None = None
    due_day: int | None = None
    due_month: int | None = None
    recurrence: str | None = None
    applies_to: list[str] = []


class TaxpayerProfileNode(BaseModel):
    profile_type: str
    display_name: str | None = None
    description: str | None = None


class LexNote(BaseModel):
    """Describes a lex specialis override found during graph traversal."""

    winner_section_uid: str
    overridden_section_uid: str
    authority_class: str | None = None
    note: str | None = None


class GraphContext(BaseModel):
    """
    Graph-enriched context attached to NLU parse and query responses.
    All lists are empty (not null) when graph is connected but no matches found.
    The entire object is null when Neo4j is disabled or unreachable.
    """

    concepts: list[ConceptNode] = Field(
        default_factory=list,
        description="Tax concepts mentioned by the retrieved chunks.",
    )
    reliefs: list[ReliefNode] = Field(
        default_factory=list,
        description="Relief types covered by the retrieved sections.",
    )
    rate_bands: list[RateBandNode] = Field(
        default_factory=list,
        description="Tax slabs or relief ceilings linked to matched concepts.",
    )
    procedure_milestones: list[ProcedureMilestoneNode] = Field(
        default_factory=list,
        description="Filing or payment milestones derived from retrieved sections.",
    )
    taxpayer_profiles: list[TaxpayerProfileNode] = Field(
        default_factory=list,
        description="Taxpayer profiles relevant to the retrieved reliefs.",
    )
    superseded_by: list[str] = Field(
        default_factory=list,
        description="source_doc_ids of instruments that supersede the matched documents.",
    )
    lex_notes: list[LexNote] = Field(
        default_factory=list,
        description="Lex specialis override notes when conflicting sections are found.",
    )
    graph_model: str = Field(
        default="neo4j-phase4",
        description="Graph backend identifier for client display.",
    )
