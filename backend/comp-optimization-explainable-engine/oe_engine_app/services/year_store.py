"""Read compiled year views for catalog and calculate."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from db.models import OeEngineDocument
from db.year_views import OeEngineYearRate, OeEngineYearRelief
from oe_engine_app.services.claim_conditions import derive_claim_conditions, derive_proof
from oe_engine_app.services.compiler import (
    BASE_ASSESSMENT_YEARS,
    default_question_prompt,
    derive_assessment_years,
    load_promoted_entities,
    recompile_year_views,
    relief_interview_visible,
)
from oe_engine_app.services.extract_dedupe import (
    canonical_compare_group_id,
    collapse_year_relief_aliases,
)
from oe_engine_app.services.terminal_benefit import (
    group_terminal_ladders,
    is_terminal_rate_group,
)


def _interview_reliefs(
    rows: list[dict[str, Any]],
    assessment_year: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if relief_interview_visible(row, assessment_year)
    ]


def present_relief(payload: dict[str, Any]) -> dict[str, Any]:
    """Fill interview fields the stepper expects (prompt, eligibility, evidence)."""
    out = dict(payload)
    sub_items = out.get("sub_items")
    out["sub_items"] = sub_items if isinstance(sub_items, list) else []
    covers = out.get("covers")
    out["covers"] = covers if isinstance(covers, dict) and covers.get("items") else None
    terms = out.get("definitions")
    out["definitions"] = terms if isinstance(terms, list) else []
    if not str(out.get("question_prompt") or "").strip():
        out["question_prompt"] = default_question_prompt(out)
    eligibility = out.get("eligibility")
    if isinstance(eligibility, dict):
        text = str(eligibility.get("text") or "").strip()
        out["eligibility_text"] = text
        out["eligibility_status"] = str(eligibility.get("review_status") or "pending")
        out["eligibility_quote"] = str(eligibility.get("quote") or "")
    else:
        out.setdefault("eligibility_text", "")
        out.setdefault("eligibility_status", "pending")
        out.setdefault("eligibility_quote", "")
    evidence = out.get("required_evidence")
    if not isinstance(evidence, list):
        out["required_evidence"] = []
    else:
        out["required_evidence"] = [str(item) for item in evidence if str(item).strip()]
    out["claim_conditions"] = derive_claim_conditions(out)
    out["proof"] = derive_proof(out)
    return out


def list_years(session: Session) -> list[dict[str, Any]]:
    relief_years = {
        row[0]
        for row in session.query(OeEngineYearRelief.assessment_year).distinct().all()
    }
    rate_years = {
        row[0] for row in session.query(OeEngineYearRate.assessment_year).distinct().all()
    }
    allowed = set(derive_assessment_years(load_promoted_entities(session))) or set(
        BASE_ASSESSMENT_YEARS
    )
    years = sorted(ya for ya in (relief_years | rate_years) if ya in allowed)
    return [{"assessment_year": ya} for ya in years]


def reliefs_for_year(
    session: Session,
    assessment_year: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]] | None:
    skip = (exclude_source_doc_id or "").strip() or None
    if skip:
        reliefs, _rates = recompile_year_views(
            session, exclude_source_doc_id=skip, persist=False
        )
        raw = reliefs.get(assessment_year)
        if raw is None:
            return None
        presented = [present_relief(row) for row in raw]
        return collapse_year_relief_aliases(
            _interview_reliefs(presented, assessment_year),
        )
    rows = (
        session.query(OeEngineYearRelief)
        .filter(OeEngineYearRelief.assessment_year == assessment_year)
        .all()
    )
    if not rows:
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload_json or {})
        payload.setdefault("entry_id", row.entry_id)
        payload.setdefault("compare_group_id", row.compare_group_id)
        payload.setdefault("source_doc_id", row.source_doc_id)
        payload.setdefault("cap_amount", row.cap_amount)
        payload.setdefault("display_name", row.display_name)
        payload.setdefault("unit", row.unit)
        payload.setdefault("input_kind", row.input_kind)
        out.append(present_relief(payload))
    return collapse_year_relief_aliases(_interview_reliefs(out, assessment_year))


def rates_for_year(
    session: Session,
    assessment_year: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]] | None:
    skip = (exclude_source_doc_id or "").strip() or None
    if skip:
        _reliefs, rates = recompile_year_views(
            session, exclude_source_doc_id=skip, persist=False
        )
        return rates.get(assessment_year)
    rows = (
        session.query(OeEngineYearRate)
        .filter(OeEngineYearRate.assessment_year == assessment_year)
        .order_by(
            OeEngineYearRate.compare_group_id,
            OeEngineYearRate.ladder_key,
            OeEngineYearRate.band_index,
        )
        .all()
    )
    if not rows:
        return None
    return [dict(row.payload_json or {}) for row in rows]


def split_year_rates(
    bands: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordinary: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []
    for row in bands or []:
        if is_terminal_rate_group(str(row.get("compare_group_id") or "")):
            terminal.append(row)
        else:
            ordinary.append(row)
    return ordinary, terminal


def ordinary_rates_for_year(
    session: Session,
    assessment_year: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]] | None:
    bands = rates_for_year(session, assessment_year, exclude_source_doc_id)
    if bands is None:
        return None
    ordinary, _terminal = split_year_rates(bands)
    return ordinary


def terminal_ladders_for_year(
    session: Session,
    assessment_year: str,
    exclude_source_doc_id: str | None = None,
) -> list[dict[str, Any]]:
    bands = rates_for_year(session, assessment_year, exclude_source_doc_id) or []
    _ordinary, terminal = split_year_rates(bands)
    return group_terminal_ladders(terminal)


RATE_COMPARE_GROUPS = frozenset(
    {
        "first_schedule_rates",
        "rate_band",
        "individual_income_tax",
        "individual_income_tax_slab",
        "individual_progressive_rates",
    }
)


def lookup_act_value(session: Session, compare_group_id: str, year: str) -> str | None:
    canonical = canonical_compare_group_id(compare_group_id, entity_kind="relief")
    listed = reliefs_for_year(session, year) or []
    match = next((row for row in listed if row.get("compare_group_id") == canonical), None)
    if match is not None:
        cap = match.get("cap_amount")
        return None if cap in (None, "") else str(cap)
    if compare_group_id not in RATE_COMPARE_GROUPS:
        return None
    rates = (
        session.query(OeEngineYearRate)
        .filter(OeEngineYearRate.assessment_year == year)
        .order_by(
            OeEngineYearRate.compare_group_id,
            OeEngineYearRate.ladder_key,
            OeEngineYearRate.band_index,
        )
        .all()
    )
    ordinary = [
        row
        for row in rates
        if not is_terminal_rate_group(
            str((row.payload_json or {}).get("compare_group_id") or row.compare_group_id or "")
        )
    ]
    if not ordinary:
        return None
    return ",".join(r.rate_percent for r in ordinary)


def acts_for_year(session: Session, assessment_year: str) -> list[dict[str, Any]]:
    reliefs = reliefs_for_year(session, assessment_year) or []
    rates = rates_for_year(session, assessment_year) or []
    ids = sorted(
        {
            str(row.get("source_doc_id") or "")
            for row in reliefs + rates
            if row.get("source_doc_id")
        }
    )
    acts: list[dict[str, Any]] = []
    for sid in ids:
        doc = session.get(OeEngineDocument, sid)
        acts.append(
            {
                "source_doc_id": sid,
                "title": doc.title if doc is not None else sid,
                "relief_count": sum(1 for row in reliefs if row.get("source_doc_id") == sid),
                "rate_band_count": sum(1 for row in rates if row.get("source_doc_id") == sid),
            }
        )
    return acts
