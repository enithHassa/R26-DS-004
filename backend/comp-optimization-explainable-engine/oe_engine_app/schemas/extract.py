"""Extracted-entity schema Phase 4 will consume. Keep this file the contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ReviewStatus = Literal["pending", "accepted", "rejected", "needs_update"]
ChangeAction = Literal["add", "amend", "repeal"]
EngineScope = Literal["individual", "other"]
EntityKind = Literal["relief", "rate_band", "guide_help", "consolidated_fact"]
Tier = Literal["act", "guide", "consolidated"]
Terminus = Literal[
    "review_then_promote",
    "display_no_promote",
    "facts_and_mismatch_no_promote",
]


class Eligibility(BaseModel):
    text: str = ""
    review_status: ReviewStatus = "pending"
    quote: str = ""


class ReliefEntity(BaseModel):
    entity_kind: Literal["relief"] = "relief"
    entry_id: str
    source_doc_id: str = ""
    compare_group_id: str
    display_name: str
    paragraph_ref: str = ""
    section_ref: str = ""
    act_name: str = ""
    cap_amount: str | None = None
    unit: str = "lkr"
    quote: str
    eligibility: Eligibility = Field(default_factory=Eligibility)
    required_evidence: list[str] = Field(default_factory=list)
    filing_line: str = ""
    stacking: str = ""
    effective_from: str = ""
    effective_to: str = ""
    question_prompt: str = ""
    help: str = ""
    input_kind: str = "notice"
    auto_applied: bool = False
    engine_binding: dict[str, str] = Field(default_factory=lambda: {"kind": "none"})
    sort_order: int = 0
    change_action: ChangeAction = "add"
    review_status: ReviewStatus = "pending"
    year_kind: str = ""
    quote_ok_window: bool = False
    quote_ok_full_doc: bool = False
    quote_source: str = "none"
    pass2_verbatim: bool = False
    pass2_note: str = ""
    included: bool = False
    engine_scope: EngineScope = "individual"

    @field_validator("cap_amount", mode="before")
    @classmethod
    def _cap_str(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value).replace(",", "").strip()


class RateBandEntity(BaseModel):
    entity_kind: Literal["rate_band"] = "rate_band"
    entry_id: str
    source_doc_id: str = ""
    compare_group_id: str = "first_schedule_rates"
    band_index: int
    band_label: str = ""
    lower: str = ""
    upper: str | None = None
    rate_percent: str
    applies_to: str = ""
    section_ref: str = "First Schedule"
    act_name: str = ""
    effective_from: str = ""
    effective_to: str = ""
    quote: str
    change_action: ChangeAction = "add"
    review_status: ReviewStatus = "pending"
    year_kind: str = ""
    quote_ok_window: bool = False
    quote_ok_full_doc: bool = False
    quote_source: str = "none"
    pass2_verbatim: bool = False
    pass2_note: str = ""
    included: bool = False
    engine_scope: EngineScope = "individual"
    rule_family: str = ""
    employment_period_condition: str = ""
    qualifying_income_types: list[str] = Field(default_factory=list)
    base_act_name: str = ""
    amendment_act_name: str = ""
    period_from: str = ""
    period_to: str = ""


class GuideHelpEntity(BaseModel):
    """Guide-only: wording / eligibility / evidence. Never a cap."""

    entity_kind: Literal["guide_help"] = "guide_help"
    entry_id: str
    source_doc_id: str = ""
    compare_group_id: str = ""
    display_name: str
    help: str = ""
    eligibility: Eligibility = Field(default_factory=Eligibility)
    required_evidence: list[str] = Field(default_factory=list)
    section_ref: str = ""
    quote: str = ""
    review_status: ReviewStatus = "pending"
    quote_ok_window: bool = False
    quote_ok_full_doc: bool = False
    quote_source: str = "none"
    pass2_verbatim: bool = False
    pass2_note: str = ""
    included: bool = False

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _no_cap(self) -> GuideHelpEntity:
        extra = getattr(self, "model_extra", None) or {}
        if extra.get("cap_amount") not in (None, "", 0, "0"):
            raise ValueError("Guide entities must not carry cap_amount")
        return self


class ConsolidatedFactEntity(BaseModel):
    """Cross-check fact. Never promoted into year views."""

    entity_kind: Literal["consolidated_fact"] = "consolidated_fact"
    entry_id: str
    source_doc_id: str = ""
    compare_group_id: str
    year: str
    value: str
    quote: str = ""
    section_ref: str = ""
    review_status: ReviewStatus = "pending"
    quote_ok_window: bool = False
    quote_ok_full_doc: bool = False
    quote_source: str = "none"
    pass2_verbatim: bool = False
    pass2_note: str = ""
    included: bool = False


ExtractEntity = ReliefEntity | RateBandEntity | GuideHelpEntity | ConsolidatedFactEntity


class ExtractWindow(BaseModel):
    window_id: str
    heading: str
    char_count: int
    page_start: int | None = None
    page_end: int | None = None
    channel_hint: str = "text_stream"


class ExtractRun(BaseModel):
    spec_version: str = "1.0.0"
    extraction_run_id: str
    source_doc_id: str
    tier: Tier
    terminus: Terminus
    model: str
    dry_run: bool = False
    usd_this_run: float = 0.0
    usd_running_total: float = 0.0
    windows: list[ExtractWindow] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def terminus_for_tier(tier: str) -> Terminus:
    mapping: dict[str, Terminus] = {
        "act": "review_then_promote",
        "guide": "display_no_promote",
        "consolidated": "facts_and_mismatch_no_promote",
    }
    if tier not in mapping:
        raise ValueError(f"unknown tier: {tier}")
    return mapping[tier]
