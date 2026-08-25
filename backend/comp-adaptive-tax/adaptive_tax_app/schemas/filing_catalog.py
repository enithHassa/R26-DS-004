"""Phase 6 — filing component catalog DTOs (UI + explain metadata)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LegalConfidence = Literal["high", "medium", "low", "pending"]
ConfidenceBasis = Literal[
    "direct_section",
    "schedule",
    "amendment_pending",
    "interpretive",
]
DefaultTreatment = Literal[
    "include",
    "exempt",
    "final_withholding",
    "deduct",
    "credit",
]
EngineSupport = Literal["supported", "unsupported", "unknown"]
CatalogStatus = Literal["approved", "pending_review", "pending_unsupported", "inactive"]
InputKind = Literal["money_line", "custom_list", "scalar_compat"]
AssessmentYear = Literal["2024_25", "2025_26"]


class FilingCatalogCardMeta(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    card_id: str
    display_name: str
    sort_order: int = 0
    section: str | None = None
    section_uid: str | None = None


class FilingCatalogComponent(BaseModel):
    """One catalog row — drives UI labels, defaults, confidence, and engine keys."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    card_id: str
    display_name: str
    sort_order: int = 0
    input_kind: InputKind = "money_line"
    default_treatment: DefaultTreatment = "include"
    user_overridable: bool = False
    ya_effective: list[AssessmentYear] = Field(default_factory=list)
    ya_inactive: list[AssessmentYear] = Field(default_factory=list)
    section: str | None = None
    paragraph: str | None = None
    section_uid: str | None = None
    concept_id: str | None = None
    engine_handler: str | None = None
    engine_support: EngineSupport = "unknown"
    status: CatalogStatus = "pending_review"
    legal_confidence: LegalConfidence = "pending"
    confidence_basis: ConfidenceBasis | None = None
    confidence_reason: str | None = None
    reason_short: str | None = None
    source_doc_id: str | None = None
    rule_source_id: str | None = None
    source_quote: str | None = None
    ui_group: str | None = Field(
        default=None,
        description="Optional UI grouping key (donations, special, film_cinema, review).",
    )
    effective_from: str | None = Field(
        default=None,
        description="ISO date when the provision took effect (from Act), if known.",
    )
    effective_to: str | None = Field(
        default=None,
        description="ISO end date if the provision sunset, if known.",
    )
    sec52_4_carry_forward: bool = Field(
        default=False,
        description="True when Fifth Sch 1(b)(i) or 1(b)(v) — Sec 52(4) CF eligible for YA 2025/26.",
    )
    statutory_scope: str | None = Field(
        default=None,
        description="Plain-language statutory scope note for Why? panels.",
    )


class FilingCatalogDocument(BaseModel):
    """Root document for ``filing_component_catalog_v1.json``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    spec_version: str = "1.0.0"
    catalog_version: str = "v1"
    component: str = "adaptive-tax"
    phase: str | None = None
    act_version: str | None = None
    act_version_label: str | None = None
    base_source_doc_id: str | None = None
    amendment_source_doc_ids: list[str] = Field(default_factory=list)
    extraction_version: str | None = None
    knowledge_graph_version: str | None = None
    taxpayer_scope: str | None = None
    assessment_years: list[AssessmentYear] = Field(default_factory=list)
    notes: str | None = None
    cards: list[FilingCatalogCardMeta] = Field(default_factory=list)
    components: list[FilingCatalogComponent] = Field(default_factory=list)


class FilingCatalogFieldOut(BaseModel):
    """Wire shape for one field inside a catalog card."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    sort_order: int
    input_kind: InputKind
    default_treatment: DefaultTreatment
    user_overridable: bool
    section: str | None = None
    paragraph: str | None = None
    legal_confidence: LegalConfidence
    confidence_basis: ConfidenceBasis | None = None
    confidence_reason: str | None = None
    reason_short: str | None = None
    source_doc_id: str | None = None
    engine_support: EngineSupport = "unknown"
    status: CatalogStatus = "approved"
    ui_group: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    applicable_assessment_years: list[AssessmentYear] = Field(default_factory=list)
    rule_source_id: str | None = None
    engine_handler: str | None = None
    sec52_4_carry_forward: bool = False
    statutory_scope: str | None = None


class FilingCatalogCardOut(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    card_id: str
    display_name: str
    sort_order: int
    section: str | None = None
    section_uid: str | None = None
    fields: list[FilingCatalogFieldOut] = Field(default_factory=list)


class FilingCatalogResponseV1(BaseModel):
    """``GET /api/v1/filing-catalog`` response."""

    model_config = ConfigDict(str_strip_whitespace=True)

    catalog_version: str
    act_version: str | None = None
    act_version_label: str | None = None
    extraction_version: str | None = None
    knowledge_graph_version: str | None = None
    assessment_year: AssessmentYear
    cards: list[FilingCatalogCardOut]


class FilingCatalogExplainResponseV1(BaseModel):
    """``GET /api/v1/filing-catalog/{component_id}/explain``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    treatment: DefaultTreatment
    section: str | None = None
    paragraph: str | None = None
    section_uid: str | None = None
    concept_id: str | None = None
    reason_short: str | None = None
    source_quote: str | None = None
    source_doc_id: str | None = None
    rule_source_id: str | None = None
    engine_handler: str | None = None
    legal_confidence: LegalConfidence
    confidence_basis: ConfidenceBasis | None = None
    confidence_reason: str | None = None
    act_version_label: str | None = None
    assessment_year: AssessmentYear | None = None
    applicable_assessment_years: list[AssessmentYear] = Field(default_factory=list)
    sec52_4_status: str | None = None
    source_label: str | None = None
    statutory_scope: str | None = None
    sec52_4_carry_forward: bool = False
    effective_from: str | None = None
    effective_to: str | None = None
    kg_nodes: list[dict[str, str]] = Field(
        default_factory=list,
        description="Knowledge-graph anchors: Concept / Section node ids.",
    )
    evidence_chunks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional Chroma hits for the field section (Act-backed corpus).",
    )
    evidence_warnings: list[str] = Field(default_factory=list)


class UnsupportedCatalogItemV1(BaseModel):
    """One row in the Phase 6.8 unsupported-rule queue."""

    model_config = ConfigDict(str_strip_whitespace=True)

    component_id: str
    display_name: str
    section: str | None = None
    paragraph: str | None = None
    engine_handler: str | None = None
    engine_support: EngineSupport
    status: CatalogStatus
    source_doc_id: str | None = None
    source_quote: str | None = None
    action_required: str = "Requires new Rule Engine handler"
    approve_blocked_reason: str = (
        "Approve only after engine handler, provenance, and catalog executable flag are complete."
    )


class UnsupportedCatalogResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    count: int
    items: list[UnsupportedCatalogItemV1] = Field(default_factory=list)
