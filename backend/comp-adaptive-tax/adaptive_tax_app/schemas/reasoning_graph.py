"""Phase 6.8 — deterministic legal reasoning graph for report viva panel."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReasoningGraphNodeV1(BaseModel):
    """One box in the Salary → … → Payable pipeline."""

    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str
    label: str
    amount: str | None = None
    step_ids: list[str] = Field(default_factory=list)
    section_uids: list[str] = Field(default_factory=list)
    rule_source_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    kg_node_ids: list[str] = Field(default_factory=list)
    legal_confidence: str | None = None
    source_quote: str | None = None
    section: str | None = None
    present: bool = True


class ReasoningGraphEdgeV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    from_node: str
    to_node: str
    label: str | None = None


class ReasoningGraphResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    calc_id: str
    assessment_year: str
    nodes: list[ReasoningGraphNodeV1] = Field(default_factory=list)
    edges: list[ReasoningGraphEdgeV1] = Field(default_factory=list)
    display_order: list[str] = Field(default_factory=list)
