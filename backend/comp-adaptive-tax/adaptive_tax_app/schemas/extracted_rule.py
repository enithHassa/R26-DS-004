"""Pydantic schemas for GPT / fixture amendment rule extraction."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RuleTypeLiteral = Literal[
    "deduction",
    "exemption",
    "rate",
    "definition",
    "limit",
    "condition",
]

_SOURCE_QUOTE_MIN_LEN = 20


class ExtractedRule(BaseModel):
    """One structured rule extracted from an amendment PDF."""

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

    @field_validator("source_quote")
    @classmethod
    def _strip_source_quote(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < _SOURCE_QUOTE_MIN_LEN:
            raise ValueError(
                f"source_quote must be at least {_SOURCE_QUOTE_MIN_LEN} characters"
            )
        return cleaned

    @field_validator("section", "amends_section", "paragraph", "concept_id")
    @classmethod
    def _strip_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ExtractedRulesPayload(BaseModel):
    """Top-level structured output for OpenAI parse / tool calling."""

    rules: list[ExtractedRule] = Field(default_factory=list)
