"""Agentic Think Twice loop — validate draft answers before delivery."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import LanguageModelSettings
from app.services.symbolic_engine import SymbolicValidationResult, validate_advisory_text


@dataclass(frozen=True, slots=True)
class ThinkTwiceResult:
    answer_text: str | None
    validation: SymbolicValidationResult | None
    corrected: bool
    validation_status: str


_SAFE_FALLBACK = (
    "I cannot provide a verified plain-language summary because symbolic validation "
    "flagged issues in the draft answer. Please review the cited legal passages below "
    "or rephrase your question with a specific assessment year."
)


def apply_think_twice(
    settings: LanguageModelSettings,
    draft_answer: str | None,
    *,
    assessment_year_hint: str | None = None,
) -> ThinkTwiceResult:
    """Validate draft answer; replace with safe fallback when symbolic checks fail."""
    if not settings.COMP_LLM_THINK_TWICE_ENABLED or not draft_answer:
        return ThinkTwiceResult(
            answer_text=draft_answer,
            validation=None,
            corrected=False,
            validation_status="skipped",
        )

    validation = validate_advisory_text(draft_answer, assessment_year_hint=assessment_year_hint)
    if validation.passed:
        suffix = ""
        if validation.disclaimer and validation.disclaimer not in draft_answer:
            suffix = f"\n\n{validation.disclaimer}"
        return ThinkTwiceResult(
            answer_text=draft_answer + suffix,
            validation=validation,
            corrected=False,
            validation_status="passed",
        )

    return ThinkTwiceResult(
        answer_text=_SAFE_FALLBACK,
        validation=validation,
        corrected=True,
        validation_status="corrected",
    )
