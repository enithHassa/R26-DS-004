"""Symbolic rule engine for Think Twice validation (Phase 5)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from backend.shared.config.settings import PROJECT_ROOT

IssueSeverity = Literal["error", "warning"]

_RULES_PATH = PROJECT_ROOT / "reasoning" / "symbolic_rules_v1.json"

_LKR_AMOUNT = re.compile(
    r"(?:LKR|Rs\.?|rupees?)\s*([0-9][0-9,]*(?:\.[0-9]+)?|[0-9][0-9,]*)\b",
    re.IGNORECASE,
)
_PERSONAL_RELIEF_CLAIM = re.compile(
    r"personal relief.{0,40}?(?:LKR|Rs\.?|rupees?)\s*([0-9][0-9,]*(?:\.[0-9]+)?|[0-9][0-9,]*)\b",
    re.IGNORECASE,
)
_ASSESSMENT_YEAR = re.compile(r"\b(20[0-9]{2})[_/\-]([0-9]{2})\b")
_RATE_PERCENT = re.compile(r"\b([0-9]{1,2}(?:\.[0-9]+)?)\s*%\s*(?:tax|rate|marginal)?", re.IGNORECASE)
# WHT: "withholding tax of 14%" or "WHT rate 5%"
_WHT_RATE = re.compile(
    r"(?:withholding tax|WHT)[^%\n]{0,40}?([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str


@dataclass(frozen=True, slots=True)
class SymbolicValidationResult:
    passed: bool
    rule_engine_version: str
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    disclaimer: str = ""


@lru_cache
def load_symbolic_rules() -> dict[str, Any]:
    path = _RULES_PATH
    if not path.is_file():
        return {
            "rule_engine_version": "symbolic_rules_v1_missing",
            "personal_relief_lkr_by_assessment_year_start": {},
            "income_tax_slabs_by_assessment_year_start": {},
            "wht_rates_percent": {},
            "max_marginal_rate_percent": 36,
            "forbidden_phrases": [],
            "advisory_disclaimer": (
                "This response is decision-support guidance only, not legally binding advice."
            ),
        }
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_amount(raw: str) -> int:
    cleaned = raw.replace(",", "").split(".")[0]
    return int(cleaned)


def _all_valid_wht_rates(wht_rates: dict[str, float]) -> set[float]:
    return set(wht_rates.values())


def validate_advisory_text(
    text: str,
    *,
    assessment_year_hint: str | None = None,
) -> SymbolicValidationResult:
    """Check generated advisory text against hard-coded Sri Lankan tax rules."""
    rules = load_symbolic_rules()
    version = str(rules.get("rule_engine_version") or "symbolic_rules_v1")
    disclaimer = str(rules.get("advisory_disclaimer") or "")
    issues: list[ValidationIssue] = []

    lowered = text.lower()

    # ── Forbidden phrases ───────────────────────────────────────────────────
    for phrase in rules.get("forbidden_phrases") or []:
        if phrase and phrase.lower() in lowered:
            issues.append(
                ValidationIssue(
                    code="forbidden_phrase",
                    severity="error",
                    message=f"Response contains disallowed phrase: {phrase!r}",
                )
            )

    # ── Max marginal rate cap ───────────────────────────────────────────────
    max_rate = float(rules.get("max_marginal_rate_percent") or 36)
    for match in _RATE_PERCENT.finditer(text):
        rate = float(match.group(1))
        if rate > max_rate + 0.01:
            issues.append(
                ValidationIssue(
                    code="rate_exceeds_cap",
                    severity="error",
                    message=f"Stated tax rate {rate}% exceeds configured max {max_rate}%.",
                )
            )

    # ── Personal relief check ───────────────────────────────────────────────
    relief_schedule: dict[str, int] = {
        str(k): int(v)
        for k, v in (rules.get("personal_relief_lkr_by_assessment_year_start") or {}).items()
    }
    year_start: str | None = None
    if assessment_year_hint:
        parts = assessment_year_hint.replace("/", "_").split("_")
        if parts and parts[0].isdigit():
            year_start = parts[0]
    if year_start is None:
        ym = _ASSESSMENT_YEAR.search(text)
        if ym:
            year_start = ym.group(1)

    for match in _PERSONAL_RELIEF_CLAIM.finditer(text):
        claimed = _parse_amount(match.group(1))
        if year_start and year_start in relief_schedule:
            expected = relief_schedule[year_start]
            if claimed != expected:
                issues.append(
                    ValidationIssue(
                        code="personal_relief_mismatch",
                        severity="error",
                        message=(
                            f"Personal relief LKR {claimed:,} does not match symbolic schedule "
                            f"LKR {expected:,} for assessment year starting {year_start}."
                        ),
                    )
                )

    # ── WHT rate plausibility ───────────────────────────────────────────────
    wht_rates: dict[str, float] = {
        str(k): float(v)
        for k, v in (rules.get("wht_rates_percent") or {}).items()
    }
    if wht_rates:
        valid_wht = _all_valid_wht_rates(wht_rates)
        for match in _WHT_RATE.finditer(text):
            stated = float(match.group(1))
            if stated not in valid_wht:
                issues.append(
                    ValidationIssue(
                        code="wht_rate_unrecognised",
                        severity="warning",
                        message=(
                            f"WHT rate {stated}% is not in the configured schedule "
                            f"{sorted(valid_wht)}. Verify the payment type."
                        ),
                    )
                )

    # ── Implausibly large LKR amounts (soft warning) ────────────────────────
    known_amounts = set(relief_schedule.values()) if relief_schedule else set()
    for match in _LKR_AMOUNT.finditer(text):
        amount = _parse_amount(match.group(1))
        if amount > 50_000_000:
            issues.append(
                ValidationIssue(
                    code="amount_outlier",
                    severity="warning",
                    message=f"Large LKR amount {amount:,} — verify against sources.",
                )
            )
        if (
            "personal relief" in lowered
            and known_amounts
            and amount in known_amounts
            and year_start
            and year_start in relief_schedule
            and amount != relief_schedule[year_start]
        ):
            issues.append(
                ValidationIssue(
                    code="personal_relief_ambiguous",
                    severity="warning",
                    message=(
                        f"Personal relief amount LKR {amount:,} mentioned; confirm assessment year."
                    ),
                )
            )

    has_errors = any(i.severity == "error" for i in issues)
    return SymbolicValidationResult(
        passed=not has_errors,
        rule_engine_version=version,
        issues=tuple(issues),
        disclaimer=disclaimer,
    )
