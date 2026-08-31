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
    # Extra system context, loaded on demand per the turn's intent.
    transactions: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    behavioural: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    return_detail: dict[str, Any] | None = None
    adaptive_amendments: list[dict[str, Any]] = field(default_factory=list)
    fields_used: list[str] = field(default_factory=list)
    # Which intent-routed source keys were requested for this turn (transparency).
    sources_requested: list[str] = field(default_factory=list)


# Source keys the intent router may select. "profile" is always loaded.
CONTEXT_SOURCE_KEYS = (
    "profile",
    "snapshot",
    "monthly",
    "transactions",
    "recommendations",
    "behavioural",
    "history",
    "return_detail",
    "adaptive_amendments",
)


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
    "transaction_taxpayer_id, tax_return_detail, section_completion"
)


def _fetch_all(db: Any, sql: str, params: dict[str, Any], label: str) -> list[dict[str, Any]]:
    """Run a read query, degrading a missing table/column to an empty list."""
    try:
        rows = db.execute(text(sql), params).fetchall()
        return [_row_to_dict(r) for r in rows]
    except SQLAlchemyError as exc:  # pragma: no cover - deployment/schema dependent
        logger.debug("{} lookup skipped: {}", label, exc)
        return []


def load_taxpayer_facts(
    profile_id: str,
    *,
    monthly_lookback: int = 12,
    sources: set[str] | None = None,
    max_transactions: int = 15,
    max_recommendations: int = 8,
    history_lookback: int = 6,
) -> TaxpayerFacts | None:
    """Load the caller's own record plus whichever extra system context the turn needs.

    ``sources`` is the set of intent-routed source keys (see ``CONTEXT_SOURCE_KEYS``).
    ``None`` means "load everything". The base profile row is always loaded; every
    other source degrades to empty on a missing table rather than raising.
    """
    want = set(sources) if sources is not None else set(CONTEXT_SOURCE_KEYS)
    facts = TaxpayerFacts(profile_id=profile_id, sources_requested=sorted(want))
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

            if "snapshot" in want:
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

            if "monthly" in want:
                mrows = _fetch_all(
                    db,
                    "SELECT tax_year, calendar_month, class_key, taxable_amount_lkr, "
                    "transaction_count FROM profile_taxable_income_monthly "
                    "WHERE financial_profile_id = :pid "
                    "ORDER BY calendar_month DESC LIMIT :lim",
                    {"pid": profile_id, "lim": monthly_lookback},
                    "monthly rollup",
                )
                if mrows:
                    facts.monthly_rollup = mrows
                    facts.fields_used.append("profile_taxable_income_monthly")

            if "transactions" in want:
                trows = _fetch_all(
                    db,
                    "SELECT semantic_category, economic_event, tax_rule_code, taxability_status, "
                    "taxable_amount_lkr, gross_amount_lkr, certainty_tier, class_source, "
                    "decision_mode, model_semantic_category, analysis_payload, created_at "
                    "FROM classified_extracted_transactions "
                    "WHERE financial_profile_id = :pid AND is_current = true "
                    "ORDER BY created_at DESC LIMIT :lim",
                    {"pid": profile_id, "lim": max_transactions},
                    "transaction classifications",
                )
                if trows:
                    facts.transactions = trows
                    facts.fields_used.append("classified_extracted_transactions")

            if "recommendations" in want:
                rrows = _fetch_all(
                    db,
                    "SELECT ts.name AS strategy_name, ts.category, ts.legal_reference, "
                    "ri.rank, ri.estimated_annual_savings, ri.adoption_probability, "
                    "ri.risk_score, ri.confidence, ri.explanation_json, "
                    "rf.accepted, rf.dismissed_reason, rf.user_rating "
                    "FROM recommendations r "
                    "JOIN recommendation_items ri ON ri.recommendation_id = r.id "
                    "JOIN tax_strategies ts ON ts.id = ri.strategy_id "
                    "LEFT JOIN recommendation_feedback rf ON rf.recommendation_item_id = ri.id "
                    "WHERE r.profile_id = :pid AND r.created_at = ("
                    "  SELECT MAX(created_at) FROM recommendations WHERE profile_id = :pid) "
                    "ORDER BY ri.rank LIMIT :lim",
                    {"pid": profile_id, "lim": max_recommendations},
                    "recommendations",
                )
                if rrows:
                    facts.recommendations = rrows
                    facts.fields_used.append("recommendations")

            if "behavioural" in want:
                brows = _fetch_all(
                    db,
                    "SELECT question_key, answer_value FROM behavioural_answers "
                    "WHERE profile_id = :pid ORDER BY question_key",
                    {"pid": profile_id},
                    "behavioural answers",
                )
                if brows:
                    facts.behavioural = brows
                    facts.fields_used.append("behavioural_answers")

            if "history" in want:
                hrows = _fetch_all(
                    db,
                    "SELECT snapshot_month, gross_monthly_income, monthly_expenses, "
                    "liquid_savings, existing_investments, total_debt, epf_balance, "
                    "etf_balance, savings_rate FROM profile_history_snapshots "
                    "WHERE profile_id = :pid ORDER BY snapshot_month DESC LIMIT :lim",
                    {"pid": profile_id, "lim": history_lookback},
                    "profile history",
                )
                if hrows:
                    facts.history = hrows
                    facts.fields_used.append("profile_history_snapshots")

            if "return_detail" in want:
                detail = facts.profile.get("tax_return_detail")
                completion = facts.profile.get("section_completion")
                if detail or completion:
                    facts.return_detail = {
                        "tax_return_detail": detail,
                        "section_completion": completion,
                    }
                    facts.fields_used.append("financial_profiles.tax_return_detail")

            if "adaptive_amendments" in want:
                arows = _fetch_all(
                    db,
                    "SELECT section, paragraph, rule_type, concept_id, condition, formula, "
                    "threshold, maximum, effective_date, amends_section, source_quote "
                    "FROM rule_source WHERE status = 'approved' "
                    "ORDER BY effective_date DESC NULLS LAST, created_at DESC LIMIT 12",
                    {},
                    "adaptive tax amendments",
                )
                if arows:
                    facts.adaptive_amendments = arows
                    facts.fields_used.append("rule_source")
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

    if facts.transactions:
        lines.append("")
        lines.append(
            "CLASSIFIED TRANSACTIONS (Component 1 semantic reasoning, most recent first):"
        )
        for t in facts.transactions:
            reason = _short_reason(t.get("analysis_payload"))
            lines.append(
                f"- {t.get('semantic_category')} / {t.get('taxability_status')}"
                f" · gross LKR {t.get('gross_amount_lkr')}, taxable LKR {t.get('taxable_amount_lkr')}"
                f" · rule {t.get('tax_rule_code') or 'n/a'}"
                f" · certainty {t.get('certainty_tier') or 'n/a'} ({t.get('class_source') or '?'})"
                + (f"\n    why: {reason}" if reason else "")
            )

    if facts.recommendations:
        lines.append("")
        lines.append("PERSONALIZED RECOMMENDATIONS (latest set; C2/C3):")
        for r in facts.recommendations:
            status = (
                "accepted"
                if r.get("accepted") is True
                else "dismissed" if r.get("accepted") is False else "no response"
            )
            why = _short_reason(r.get("explanation_json"))
            lines.append(
                f"- #{r.get('rank')} {r.get('strategy_name')} [{r.get('category')}]"
                f" · est. saving LKR {r.get('estimated_annual_savings')}"
                f" · adoption p={r.get('adoption_probability')}, confidence={r.get('confidence')}"
                f" · ref {r.get('legal_reference') or 'n/a'} · {status}"
                + (f" · reason: {r.get('dismissed_reason')}" if r.get("dismissed_reason") else "")
                + (f"\n    rationale: {why}" if why else "")
            )

    if facts.behavioural:
        lines.append("")
        lines.append("BEHAVIOURAL / RISK PROFILE ANSWERS:")
        for b in facts.behavioural:
            lines.append(f"- {b.get('question_key')}: {b.get('answer_value')}")

    if facts.history:
        lines.append("")
        lines.append("FINANCIAL HISTORY SNAPSHOTS (most recent first):")
        for h in facts.history:
            lines.append(
                f"- {h.get('snapshot_month')}: income LKR {h.get('gross_monthly_income')},"
                f" expenses LKR {h.get('monthly_expenses')}, savings rate {h.get('savings_rate')},"
                f" debt LKR {h.get('total_debt')}, EPF LKR {h.get('epf_balance')}"
            )

    if facts.return_detail:
        lines.append("")
        lines.append("FILED TAX RETURN DETAIL (TaxWise wizard sections):")
        if facts.return_detail.get("section_completion"):
            lines.append(f"- Section completion: {facts.return_detail['section_completion']}")
        if facts.return_detail.get("tax_return_detail"):
            lines.append(f"- Return detail: {facts.return_detail['tax_return_detail']}")

    if facts.adaptive_amendments:
        lines.append("")
        lines.append(
            "ACTIVE ADAPTIVE-TAX RULE AMENDMENTS (approved config changes; system-wide):"
        )
        for a in facts.adaptive_amendments:
            lines.append(
                f"- s.{a.get('section')}"
                + (f"({a.get('paragraph')})" if a.get("paragraph") else "")
                + f" [{a.get('rule_type')}] effective {a.get('effective_date') or 'n/a'}"
                + (f", amends s.{a.get('amends_section')}" if a.get("amends_section") else "")
                + (f" · condition: {a.get('condition')}" if a.get("condition") else "")
                + (f" · formula: {a.get('formula')}" if a.get("formula") else "")
            )

    lines.append("")
    lines.append(
        "Use ONLY these figures for anything taxpayer-specific. If a needed figure is "
        "missing above, say it is not on file rather than estimating. When you rely on a "
        "classified transaction or a recommendation rationale, explain the reasoning it "
        "records rather than just repeating the label."
    )
    return "\n".join(lines)


def _short_reason(payload: Any, limit: int = 320) -> str:
    """Pull a human-readable rationale string out of a JSON analysis/explanation blob."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        text_val = payload
    elif isinstance(payload, dict):
        for key in (
            "reasoning",
            "rationale",
            "explanation",
            "reason",
            "summary",
            "narrative",
            "why",
        ):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                text_val = val
                break
        else:
            text_val = "; ".join(
                f"{k}={v}" for k, v in payload.items() if isinstance(v, (str, int, float))
            )
    else:
        text_val = str(payload)
    text_val = " ".join(text_val.split())
    return text_val[: limit - 1] + "…" if len(text_val) > limit else text_val
