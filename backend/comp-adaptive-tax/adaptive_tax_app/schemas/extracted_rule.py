"""Pydantic schemas for GPT / fixture amendment rule extraction."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RuleTypeLiteral = Literal[
    "deduction",
    "exemption",
    "rate",
    "definition",
    "limit",
    "condition",
]

AssessmentYearLiteral = Literal["2024_25", "2025_26"]
TaxpayerScopeLiteral = Literal["resident_individual"]
EngineHandlerLiteral = Literal[
    "cap_absolute",
    "cap_percent_assessable",
    "slab_band",
    "personal_relief_resident",
    "carry_forward",
    "carry_forward_qp",
    "sum_assessable",
    "exemption",
    "exclude_if_final_wht",
    "exclude_investment_final_wht",
    "exclude_other_final_wht",
    "compute_business_net",
    "deduct_business_expenses",
    "deduct_capital_allowances",
    "tax_credit",
    "aggregate_employment_components",
    "exclude_employment_exempt_lines",
    "aggregate_investment_components",
    "aggregate_business_components",
    "aggregate_other_income_components",
    "aggregate_qualifying_payment_components",
    "aggregate_donation_components",
]

# Handlers the Python rule engine can execute (Phase 6 unsupported detection).
KNOWN_ENGINE_HANDLERS: frozenset[str] = frozenset(
    {
        "cap_absolute",
        "cap_percent_assessable",
        "slab_band",
        "personal_relief_resident",
        "carry_forward",
        "carry_forward_qp",
        "sum_assessable",
        "exemption",
        "exclude_if_final_wht",
        "exclude_investment_final_wht",
        "exclude_other_final_wht",
        "compute_business_net",
        "deduct_business_expenses",
        "deduct_capital_allowances",
        "tax_credit",
        "aggregate_employment_components",
        "exclude_employment_exempt_lines",
        "aggregate_investment_components",
        "aggregate_business_components",
        "aggregate_other_income_components",
        "aggregate_qualifying_payment_components",
        "aggregate_donation_components",
        # Composite / registry ids used by provenance gates:
        "cap_absolute:qualifying_payment_cap",
        "cap_percent_assessable:donation_cap",
        "deduct_qualifying_payment",
        "deduct_donation",
        "final_tax",
    }
)

_SOURCE_QUOTE_MIN_LEN = 20
_SECTION_MAX_LEN = 64
_PARAGRAPH_MAX_LEN = 64
_CONCEPT_MAX_LEN = 128
_EFFECTIVE_YEAR_MIN = 1900
_EFFECTIVE_YEAR_MAX = 2100


class RelationshipHint(BaseModel):
    """Optional calc-graph hint for admin review (not auto-applied)."""

    from_concept: str = Field(..., min_length=1, max_length=_CONCEPT_MAX_LEN)
    rel_type: str = Field(..., min_length=1, max_length=64)
    to_concept: str = Field(..., min_length=1, max_length=_CONCEPT_MAX_LEN)


class ExtractedRule(BaseModel):
    """One structured rule extracted from an amendment or section harvest window."""

    section: str = Field(..., min_length=1, description="Section identifier, e.g. '52'")
    paragraph: str | None = None
    rule_type: RuleTypeLiteral
    concept_id: str | None = None
    condition: str | None = None
    formula: str | None = None
    threshold: float | None = None
    maximum: float | None = None
    effective_date: date | None = None
    amends_section: str | None = Field(
        default=None,
        description="Principal-enactment section being amended, when named in the text.",
    )
    source_quote: str = Field(
        ...,
        min_length=_SOURCE_QUOTE_MIN_LEN,
        description="Verbatim quote from the provided amendment text (mandatory).",
    )
    # Phase 5.0 additive fields (stored on job JSONB / rule_versions.params).
    assessment_years: list[AssessmentYearLiteral] | None = Field(
        default=None,
        description="YA packs this rule applies to when approved (optional).",
    )
    executable: bool = Field(
        default=False,
        description="True only when the Python rule engine can consume this rule.",
    )
    engine_handler: str | None = Field(
        default=None,
        max_length=64,
        description="Handler id, e.g. cap_absolute, slab_band, carry_forward.",
    )
    schedule_ref: str | None = Field(
        default=None,
        max_length=128,
        description="Schedule label when relevant, e.g. First Schedule.",
    )
    cross_refs: list[str] = Field(default_factory=list)
    applies_to_taxpayer: TaxpayerScopeLiteral = "resident_individual"
    relationship_hints: list[RelationshipHint] = Field(default_factory=list)
    # Phase 6.0 — unsupported-rule detection hooks (UI surfaces in 6.8).
    engine_support: Literal["supported", "unsupported", "unknown"] = Field(
        default="unknown",
        description=(
            "supported = engine_handler known; unsupported = extracted but no handler "
            "(queued, never applied to tax); unknown = not classified yet."
        ),
    )

    @field_validator("source_quote")
    @classmethod
    def _strip_source_quote(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < _SOURCE_QUOTE_MIN_LEN:
            raise ValueError(
                f"source_quote must be at least {_SOURCE_QUOTE_MIN_LEN} characters"
            )
        return cleaned

    @field_validator("effective_date", mode="before")
    @classmethod
    def _coerce_effective_date(cls, value: Any) -> date | None:
        """Drop GPT placeholders like 0000-01-01 / year 1404 instead of failing extract."""
        if value is None or value == "":
            return None
        parsed: date | None
        if isinstance(value, date):
            parsed = value
        elif isinstance(value, str):
            text = value.strip()
            if not text or text.startswith("0000"):
                return None
            try:
                parsed = date.fromisoformat(text[:10])
            except ValueError:
                return None
        else:
            return None
        if parsed.year < _EFFECTIVE_YEAR_MIN or parsed.year > _EFFECTIVE_YEAR_MAX:
            return None
        return parsed

    @field_validator("section", "paragraph", "concept_id", "amends_section", mode="before")
    @classmethod
    def _strip_optional_ids(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("section")
    @classmethod
    def _cap_section(cls, value: str) -> str:
        return value[:_SECTION_MAX_LEN]

    @field_validator("paragraph")
    @classmethod
    def _cap_paragraph(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value[:_PARAGRAPH_MAX_LEN]

    @field_validator("concept_id")
    @classmethod
    def _cap_concept(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value[:_CONCEPT_MAX_LEN]


class ExtractedRulesPayload(BaseModel):
    """Top-level structured output for OpenAI parse / tool calling."""

    rules: list[ExtractedRule] = Field(default_factory=list)


def classify_engine_support(rule: ExtractedRule) -> ExtractedRule:
    """Stamp engine_support for unsupported-rule detection (does not change tax)."""
    if rule.engine_support in {"supported", "unsupported"}:
        return rule
    handler = (rule.engine_handler or "").strip()
    if not handler:
        if rule.executable:
            return rule.model_copy(update={"engine_support": "unsupported"})
        return rule.model_copy(update={"engine_support": "unknown"})
    if handler in KNOWN_ENGINE_HANDLERS or any(
        handler.startswith(prefix)
        for prefix in ("sum_assessable:", "cap_absolute:", "deduct_")
    ):
        return rule.model_copy(update={"engine_support": "supported"})
    return rule.model_copy(update={"engine_support": "unsupported"})


def classify_extracted_rules(rules: list[ExtractedRule]) -> list[ExtractedRule]:
    return [classify_engine_support(r) for r in rules]
