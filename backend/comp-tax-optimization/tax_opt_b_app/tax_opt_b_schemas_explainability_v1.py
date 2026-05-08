"""FR5 — structured explainability payloads (versioned ``*_v1``).

Template-based deterministic narratives derived from rule-engine outputs: not
generative AI. OpenAPI wording: *template-based deterministic narrative*; no LLM
fields (no model id, tokens, or confidence scores).

``detail_level`` records which verbosity tier was used when the bundle was built
(``summary`` ≈ short paragraphs + key bullets; ``detailed`` adds per-relief,
per-slab, and per-violation lines). List and string max lengths bound response
size defensively; slab lines are also capped when building narratives (see
template provider).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaxOptBExplainRequestFlagsV1(BaseModel):
    """Optional flags for embedding FR5 template narratives in the same HTTP response (no extra round-trip)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    include_explanations: bool = Field(
        default=False,
        description="When true, response includes ``explanations`` (template-based deterministic narrative).",
    )
    explanation_detail: Literal["summary", "detailed"] = Field(
        default="summary",
        description="summary: short paragraphs and key bullets; detailed: per-relief, per-slab, per-violation lines where applicable.",
    )
class TaxOptBExplanationDetailLevelV1(StrEnum):
    """Verbosity tier used to produce the bundle."""

    SUMMARY = "summary"
    DETAILED = "detailed"


class TaxOptBExplanationBulletKindV1(StrEnum):
    """Category of bullet for styling, filtering, and traceability."""

    SUMMARY = "summary"
    COMPLIANCE = "compliance"
    RELIEF = "relief"
    SLAB = "slab"
    COMPARISON = "comparison"
    DISCLAIMER = "disclaimer"


class TaxOptBExplanationBulletV1(BaseModel):
    """One user-facing line with optional drill-down text and trace ids."""

    model_config = ConfigDict(str_strip_whitespace=True)

    kind: TaxOptBExplanationBulletKindV1 = Field(
        description="Bullet category: summary, compliance, relief, slab, comparison, or disclaimer.",
    )
    text: str = Field(
        min_length=1,
        max_length=4_000,
        description="Primary template-filled sentence or paragraph fragment.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        max_length=32,
        description=(
            "Stable trace ids: YAML ``rule_id``, semantic keys (e.g. ``slab:0``, "
            "``relief:life_insurance_premium``, ``compare:variant_id``)."
        ),
    )
    detail_text: str | None = Field(
        default=None,
        max_length=8_000,
        description="Optional longer drill-down; used mainly in detailed tier.",
    )


class TaxOptBExplanationSectionV1(BaseModel):
    """Grouped bullets under a titled heading (e.g. Tax computation walk)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=256)
    bullets: list[TaxOptBExplanationBulletV1] = Field(
        default_factory=list,
        max_length=64,
        description="Capped defensively; slab bands are bounded by the rules pack size in practice.",
    )


class TaxOptBExplanationBundleV1(BaseModel):
    """FR5 payload: template-based deterministic narrative + trace metadata."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "description": (
                "User-facing explanations from the MVP rule engine and tax calculator. "
                "Template-based deterministic narrative; not an LLM output."
            ),
        },
    )

    summary: str = Field(
        max_length=16_000,
        description="Short top-level narrative (typically 1–3 paragraphs in summary tier).",
    )
    sections: list[TaxOptBExplanationSectionV1] = Field(
        default_factory=list,
        max_length=24,
        description="Grouped explanations; each section has capped bullets.",
    )
    detail_level: TaxOptBExplanationDetailLevelV1 = Field(
        default=TaxOptBExplanationDetailLevelV1.SUMMARY,
        description="Verbosity tier that was requested when this bundle was produced.",
    )
    provenance: dict[str, str | bool] = Field(
        default_factory=lambda: {"engine": "template_v1", "deterministic": True},
        description=(
            "e.g. ``engine`` (provider id), ``deterministic`` (bool). "
            "No LLM-specific keys; safe to extend with non-generative metadata."
        ),
    )
    rules_version_label: str | None = Field(
        default=None,
        description="Echo of ``COMP_OPTIMIZATION_RULES_VERSION`` when supplied to the engine run.",
    )
    ruleset_assessment_year: str | None = Field(
        default=None,
        description="Echo of rules pack ``assessment_year`` / profile tax year for traceability.",
    )


__all__ = [
    "TaxOptBExplainRequestFlagsV1",
    "TaxOptBExplanationBulletKindV1",
    "TaxOptBExplanationBulletV1",
    "TaxOptBExplanationBundleV1",
    "TaxOptBExplanationDetailLevelV1",
    "TaxOptBExplanationSectionV1",
]
