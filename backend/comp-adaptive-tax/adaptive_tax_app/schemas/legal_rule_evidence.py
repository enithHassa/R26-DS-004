"""LegalRuleEvidence — structured legal evidence from RAG (Phase 11a).

This is **not** RAG calculation and **not** an executable Rule Engine command.

CURRENT: RAG → evidence + explain | Rule Engine → calculate
FUTURE:  RAG → LegalRuleEvidence → human approval → Rule Engine

In this phase:
- ``executable`` is always ``False``
- numeric slots (cap/threshold/maximum) stay ``null`` unless literally present
  in the Act ``source_quote`` (deterministic parse) — never invent numbers
- default ``status`` is ``candidate``
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from adaptive_tax_app.schemas.extracted_rule import AssessmentYearLiteral

# Descriptive provision kinds — NOT Rule Engine handler ids / commands.
LegalEvidenceRuleType = Literal[
    "CAP",
    "carry_forward",
    "rate_band",
    "relief",
    "deduction",
    "exemption",
    "definition",
    "limit",
    "condition",
    "tax_credit",
    "other",
]

LegalEvidenceStatus = Literal[
    "candidate",
    "needs_review",
    "approved",
    "rejected",
]

_SOURCE_QUOTE_MIN_LEN = 20
_SECTION_MAX_LEN = 64
_PARAGRAPH_MAX_LEN = 64

# Loose patterns used only to *validate* that a claimed number appears in the quote.
_NUMBER_IN_QUOTE_RE = re.compile(
    r"(?<![\d.])(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d.])"
)


def _normalize_number_token(value: float) -> set[str]:
    """Comparable string forms of a numeric slot (whole LKR / plain float)."""
    forms: set[str] = set()
    as_int = int(value) if float(value).is_integer() else None
    if as_int is not None:
        forms.add(str(as_int))
        forms.add(f"{as_int:,}")
    forms.add(str(value))
    # Drop trailing .0
    if float(value).is_integer():
        forms.add(f"{int(value)}.0")
    return forms


def number_literally_in_quote(value: float | None, source_quote: str | None) -> bool:
    """True when ``value`` appears as a literal numeral in ``source_quote``."""
    if value is None:
        return True
    quote = source_quote or ""
    if not quote.strip():
        return False
    forms = _normalize_number_token(float(value))
    # Also accept unpunctuated matches from quote tokens
    found = {m.group(1).replace(",", "") for m in _NUMBER_IN_QUOTE_RE.finditer(quote)}
    found_raw = {m.group(1) for m in _NUMBER_IN_QUOTE_RE.finditer(quote)}
    for form in forms:
        compact = form.replace(",", "")
        if form in quote or compact in found or form in found_raw:
            return True
        if compact in found_raw:
            return True
    # Percent-style: 6 vs 6%
    if float(value).is_integer() and f"{int(value)}%" in quote.replace(" ", ""):
        return True
    return False


class LegalRuleEvidence(BaseModel):
    """Structured legal evidence extracted from RAG (non-executable).

    Prefer aligning field names with :class:`ExtractedRule` where they overlap
    (``section``, ``paragraph``, ``condition``, ``formula``, ``threshold``,
    ``maximum``, ``effective_date``, ``source_quote``).

    ``paragraph_ref`` is an alias-friendly retrieval key (e.g. ``52(4)``) in
    addition to free-text ``paragraph``.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    section: str = Field(
        ...,
        min_length=1,
        max_length=_SECTION_MAX_LEN,
        description="Statutory section label, e.g. '52' or 'Section 52'.",
    )
    paragraph: str | None = Field(
        default=None,
        max_length=_PARAGRAPH_MAX_LEN,
        description="Optional paragraph / subsection text label from the Act.",
    )
    paragraph_ref: str | None = Field(
        default=None,
        max_length=_PARAGRAPH_MAX_LEN,
        description="Retrieval key, e.g. '52(4)' (may mirror paragraph).",
    )
    assessment_year: AssessmentYearLiteral | None = Field(
        default=None,
        description="YA pack this evidence is scoped to, when known.",
    )

    rule_type: LegalEvidenceRuleType | None = Field(
        default=None,
        description=(
            "Descriptive provision kind (CAP, carry_forward, rate_band, …). "
            "Not an engine command / handler id."
        ),
    )
    condition: str | None = None
    formula: str | None = None

    cap_value: float | None = Field(
        default=None,
        description="Absolute cap when literally present in source_quote; else null.",
    )
    threshold: float | None = Field(
        default=None,
        description="Threshold when literally present in source_quote; else null.",
    )
    maximum: float | None = Field(
        default=None,
        description="Maximum when literally present in source_quote; else null.",
    )

    allowed: bool | None = Field(
        default=None,
        description="Optional applicability flag when explicitly supported by the quote.",
    )
    applicability_note: str | None = Field(
        default=None,
        description="Optional human-readable applicability note (not executable).",
    )

    effective_date: date | None = None
    source_doc_id: str | None = Field(
        default=None,
        description="Official IRD source_doc_id (never Guide/Master as SoT).",
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Chroma / corpus chunk ids grounding this evidence.",
    )
    parent_provision_id: str | None = Field(
        default=None,
        description="Continuity id from section-aware corpus (e.g. sec52_4).",
    )

    source_quote: str | None = Field(
        default=None,
        description=(
            "Verbatim Act text. Mandatory when structured numeric/formula fields "
            "are filled; do not invent wording."
        ),
    )

    status: LegalEvidenceStatus = Field(
        default="candidate",
        description="Review lifecycle; default candidate (not approved for engine).",
    )
    executable: Literal[False] = Field(
        default=False,
        description="Always false in Phase 11 — evidence only, never calculates tax.",
    )

    @field_validator("section", "paragraph", "paragraph_ref", mode="before")
    @classmethod
    def _strip_ids(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("section")
    @classmethod
    def _require_section(cls, value: str | None) -> str:
        if not value:
            raise ValueError("section is required")
        return value[:_SECTION_MAX_LEN]

    @field_validator("source_quote", mode="before")
    @classmethod
    def _normalize_quote(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @field_validator("effective_date", mode="before")
    @classmethod
    def _coerce_effective_date(cls, value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text or text.startswith("0000"):
                return None
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
        return None

    @field_validator("executable", mode="before")
    @classmethod
    def _force_non_executable(cls, value: Any) -> Literal[False]:
        # Phase 11a hard rule — ignore any attempt to mark executable.
        return False

    @model_validator(mode="after")
    def _structured_fields_require_quote_and_literal_numbers(self) -> Self:
        structured = any(
            [
                self.condition,
                self.formula,
                self.cap_value is not None,
                self.threshold is not None,
                self.maximum is not None,
                self.allowed is not None,
                self.rule_type is not None,
            ]
        )
        if structured:
            quote = self.source_quote or ""
            if len(quote) < _SOURCE_QUOTE_MIN_LEN:
                raise ValueError(
                    "source_quote (verbatim Act text, "
                    f">={_SOURCE_QUOTE_MIN_LEN} chars) is mandatory when "
                    "structured legal-evidence fields are filled"
                )
            for label, num in (
                ("cap_value", self.cap_value),
                ("threshold", self.threshold),
                ("maximum", self.maximum),
            ):
                if num is not None and not number_literally_in_quote(num, quote):
                    raise ValueError(
                        f"{label}={num} is not literally present in source_quote; "
                        "do not invent numbers (leave null)"
                    )
        # Status approved does not imply executable in this phase.
        if self.executable is not False:
            raise ValueError("executable must be false for LegalRuleEvidence")
        return self

    def model_dump_public(self) -> dict[str, Any]:
        """JSON-ready dump with explicit non-calculation disclaimer fields."""
        data = self.model_dump(mode="json")
        data["is_rag_calculation"] = False
        data["role"] = "structured_legal_evidence"
        return data


def legal_rule_evidence_from_extracted_rule(
    rule: Any,
    *,
    assessment_year: AssessmentYearLiteral | None = None,
    source_doc_id: str | None = None,
    source_chunk_ids: list[str] | None = None,
    parent_provision_id: str | None = None,
    paragraph_ref: str | None = None,
    status: LegalEvidenceStatus = "candidate",
) -> LegalRuleEvidence:
    """Map overlapping :class:`ExtractedRule` fields into non-executable evidence.

    Numeric slots are copied only when they pass the literal-in-quote check;
    otherwise they are nullified (never invent).
    """
    quote = getattr(rule, "source_quote", None)
    threshold = getattr(rule, "threshold", None)
    maximum = getattr(rule, "maximum", None)
    if not number_literally_in_quote(threshold, quote):
        threshold = None
    if not number_literally_in_quote(maximum, quote):
        maximum = None

    rule_type_raw = getattr(rule, "rule_type", None)
    mapped_type: LegalEvidenceRuleType | None
    if rule_type_raw is None:
        mapped_type = None
    else:
        text = str(rule_type_raw).strip().lower()
        mapping: dict[str, LegalEvidenceRuleType] = {
            "deduction": "deduction",
            "exemption": "exemption",
            "rate": "rate_band",
            "definition": "definition",
            "limit": "limit",
            "condition": "condition",
            "cap": "CAP",
            "carry_forward": "carry_forward",
            "relief": "relief",
            "tax_credit": "tax_credit",
        }
        mapped_type = mapping.get(text, "other")

    years = getattr(rule, "assessment_years", None) or []
    ya = assessment_year
    if ya is None and years:
        ya = years[0]

    return LegalRuleEvidence(
        section=str(getattr(rule, "section")),
        paragraph=getattr(rule, "paragraph", None),
        paragraph_ref=paragraph_ref or getattr(rule, "paragraph", None),
        assessment_year=ya,
        rule_type=mapped_type,
        condition=getattr(rule, "condition", None),
        formula=getattr(rule, "formula", None),
        cap_value=None,  # ExtractedRule has no cap_value; keep null unless quote-backed later
        threshold=threshold,
        maximum=maximum,
        allowed=None,
        applicability_note=None,
        effective_date=getattr(rule, "effective_date", None),
        source_doc_id=source_doc_id,
        source_chunk_ids=list(source_chunk_ids or []),
        parent_provision_id=parent_provision_id,
        source_quote=quote,
        status=status,
        executable=False,
    )
