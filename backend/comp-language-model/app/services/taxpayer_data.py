"""Read-only taxpayer grounding from the shared Azure DB.

The chat may answer questions about a *specific* taxpayer's income-tax
situation. Those answers must be grounded on real rows, never guessed.

Access rule (see AskUserQuestion decision): a chat request must carry the
caller's own ``financial_profiles.id``. If the message also names a person,
that name must match the caller's own profile — otherwise we refuse rather
than reveal another taxpayer's data.

We use raw SQL against the shared engine instead of importing Component 3's
ORM graph (per ``backend/shared/db/__init__.py`` guidance). Every query is
wrapped defensively: a missing table/column on a given DB deployment
degrades to "no facts" rather than a 500.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.shared.config.database import SessionLocal
from backend.shared.utils.logging import logger

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Words that signal the user is asking about a concrete taxpayer / their own case.
_PERSONAL_MARKERS = (
    "my ", "my_", "i earn", "i pay", "i am", "i'm", "for me", "my tax",
    "my income", "my salary", "my profile", "my situation", "my liability",
    "my epf", "my etf", "my relief", "my return", "how much do i",
    "how much will i", "what is my", "am i eligible", "do i qualify",
    "my assessable", "my taxable",
)


def looks_taxpayer_specific(message: str) -> bool:
    """Cheap heuristic: does this turn ask about a concrete taxpayer's numbers?"""
    low = f" {message.lower().strip()} "
    return any(marker in low for marker in _PERSONAL_MARKERS)


def extract_name_hint(message: str) -> str | None:
    """Pull a candidate person name out of phrasings like 'for John Silva' / "Silva's tax"."""
    patterns = [
        r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b",
        r"\babout\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b",
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})'s\s+(?:tax|income|return|liability|profile)\b",
    ]
    for pat in patterns:
        m = re.search(pat, message)
        if m:
            return m.group(1).strip()
    return None


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z]+", name.lower()) if len(t) > 1}


def name_matches(hint: str, full_name: str) -> bool:
    """True when the hint plausibly refers to the same person as ``full_name``."""
    h, f = _name_tokens(hint), _name_tokens(full_name)
    if not h or not f:
        return False
    return bool(h & f)


@dataclass(frozen=True, slots=True)
class TaxpayerResolution:
    status: str  # "ok" | "forbidden" | "not_found" | "disabled"
    profile_id: str | None = None
    full_name: str | None = None
    message: str | None = None


@dataclass(slots=True)
class TaxpayerFacts:
    profile_id: str
    full_name: str | None = None
    tax_year: str | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    latest_snapshot: dict[str, Any] | None = None
    monthly_rollup: list[dict[str, Any]] = field(default_factory=list)
    fields_used: list[str] = field(default_factory=list)


def _jsonify(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {k: _jsonify(v) for k, v in dict(row._mapping).items()}


def resolve_taxpayer(*, caller_profile_id: str | None, name_hint: str | None) -> TaxpayerResolution:
    """Decide whether we may load facts, and for which profile."""
    if not caller_profile_id or not _UUID_RE.match(caller_profile_id):
        return TaxpayerResolution(
            status="forbidden",
            message=(
                "To answer questions about a specific taxpayer's details I need your own "
                "profile id on the request. I will not look up other taxpayers."
            ),
        )

    try:
        with SessionLocal() as db:
            row = db.execute(
                text(
                    "SELECT id, full_name FROM financial_profiles WHERE id = :pid"
                ),
                {"pid": caller_profile_id},
            ).first()
    except SQLAlchemyError as exc:  # pragma: no cover - deployment/schema dependent
        logger.warning("resolve_taxpayer DB error: {}", exc)
        return TaxpayerResolution(
            status="not_found",
            message="I could not reach the taxpayer records to verify your profile.",
        )

    if row is None:
        return TaxpayerResolution(
            status="not_found",
            message="I could not find a taxpayer profile for the id on this request.",
        )

    full_name = row._mapping.get("full_name")
    if name_hint and full_name and not name_matches(name_hint, full_name):
        return TaxpayerResolution(
            status="forbidden",
            profile_id=caller_profile_id,
            full_name=full_name,
            message=(
                f"I can only answer about your own taxpayer profile ({full_name}). "
                f"I will not disclose details for '{name_hint}'."
            ),
        )

    return TaxpayerResolution(status="ok", profile_id=caller_profile_id, full_name=full_name)


_PROFILE_COLUMNS = (
    "full_name, date_of_birth, gender, district, marital_status, residency_status, "
    "nationality, occupation, employment_type, employer_sector, dependents, years_employed, "
    "gross_monthly_income, annual_bonus_lkr, monthly_expenses, monthly_debt_service, "
    "liquid_savings, existing_investments, total_debt, epf_balance, etf_balance, "
    "vehicle_value, property_value, health_insurance, life_insurance_premium_annual, "
    "home_loan_interest_annual, donations_annual, income_sources, tax_year, "
    "transaction_taxpayer_id"
)


def load_taxpayer_facts(profile_id: str, *, monthly_lookback: int = 12) -> TaxpayerFacts | None:
    """Load profile row + latest computation snapshot + recent monthly rollup."""
    facts = TaxpayerFacts(profile_id=profile_id)
    try:
        with SessionLocal() as db:
            prow = db.execute(
                text(f"SELECT {_PROFILE_COLUMNS} FROM financial_profiles WHERE id = :pid"),
                {"pid": profile_id},
            ).first()
            if prow is None:
                return None
            facts.profile = _row_to_dict(prow)
            facts.full_name = facts.profile.get("full_name")
            facts.tax_year = facts.profile.get("tax_year")
            facts.fields_used.append("financial_profiles")

            try:
                srow = db.execute(
                    text(
                        "SELECT assessment_year, status, taxpayer_name, tin, income_state, "
                        "relief_answers, calculate_result, explain_narrative, created_at "
                        "FROM tax_computation_snapshots WHERE financial_profile_id = :pid "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"pid": profile_id},
                ).first()
                if srow is not None:
                    facts.latest_snapshot = _row_to_dict(srow)
                    facts.fields_used.append("tax_computation_snapshots")
            except SQLAlchemyError as exc:  # pragma: no cover
                logger.debug("snapshot lookup skipped: {}", exc)

            try:
                mrows = db.execute(
                    text(
                        "SELECT tax_year, calendar_month, class_key, taxable_amount_lkr, "
                        "transaction_count FROM profile_taxable_income_monthly "
                        "WHERE financial_profile_id = :pid "
                        "ORDER BY calendar_month DESC LIMIT :lim"
                    ),
                    {"pid": profile_id, "lim": monthly_lookback},
                ).fetchall()
                if mrows:
                    facts.monthly_rollup = [_row_to_dict(r) for r in mrows]
                    facts.fields_used.append("profile_taxable_income_monthly")
            except SQLAlchemyError as exc:  # pragma: no cover
                logger.debug("monthly rollup lookup skipped: {}", exc)
    except SQLAlchemyError as exc:  # pragma: no cover
        logger.warning("load_taxpayer_facts DB error: {}", exc)
        return None

    return facts


def format_taxpayer_block(facts: TaxpayerFacts) -> str:
    """Render facts as a compact, LLM-friendly evidence block."""
    lines: list[str] = ["TAXPAYER RECORD (from the shared tax-advisory database):"]
    p = facts.profile
    if facts.full_name:
        lines.append(f"- Name: {facts.full_name}")
    for label, key in [
        ("Assessment/tax year", "tax_year"),
        ("Residency status", "residency_status"),
        ("Occupation", "occupation"),
        ("Employment type", "employment_type"),
        ("Employer sector", "employer_sector"),
        ("Marital status", "marital_status"),
        ("Dependents", "dependents"),
        ("Gross monthly income (LKR)", "gross_monthly_income"),
        ("Annual bonus (LKR)", "annual_bonus_lkr"),
        ("EPF balance (LKR)", "epf_balance"),
        ("ETF balance (LKR)", "etf_balance"),
        ("Life insurance premium / yr (LKR)", "life_insurance_premium_annual"),
        ("Home loan interest / yr (LKR)", "home_loan_interest_annual"),
        ("Donations / yr (LKR)", "donations_annual"),
        ("Health insurance", "health_insurance"),
    ]:
        if p.get(key) is not None:
            lines.append(f"- {label}: {p[key]}")
    if p.get("income_sources"):
        lines.append(f"- Declared income sources: {p['income_sources']}")

    snap = facts.latest_snapshot
    if snap:
        lines.append("")
        lines.append("LATEST TAX COMPUTATION SNAPSHOT:")
        for label, key in [
            ("Assessment year", "assessment_year"),
            ("Status", "status"),
            ("TIN", "tin"),
        ]:
            if snap.get(key) is not None:
                lines.append(f"- {label}: {snap[key]}")
        if snap.get("calculate_result"):
            lines.append(f"- Calculation result: {snap['calculate_result']}")
        if snap.get("income_state"):
            lines.append(f"- Income state: {snap['income_state']}")

    if facts.monthly_rollup:
        lines.append("")
        lines.append("RECENT MONTHLY TAXABLE-INCOME ROLLUP (most recent first):")
        for r in facts.monthly_rollup:
            lines.append(
                f"- {r.get('calendar_month')} [{r.get('class_key')}]: "
                f"LKR {r.get('taxable_amount_lkr')} over {r.get('transaction_count')} txns"
            )

    lines.append("")
    lines.append(
        "Use ONLY these figures for anything taxpayer-specific. If a needed figure is "
        "missing above, say it is not on file rather than estimating."
    )
    return "\n".join(lines)
