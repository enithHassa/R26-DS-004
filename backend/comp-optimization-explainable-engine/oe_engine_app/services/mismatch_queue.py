"""Bidirectional Consolidated vs Act year-view compare. Never writes year tables."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from db.mismatch import OeEngineMismatchFlag
from db.models import OeEngineConsolidatedFact
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.compiler import ASSESSMENT_YEARS
from oe_engine_app.services.year_store import RATE_COMPARE_GROUPS, lookup_act_value

MISMATCH_OPEN = "open"
MISMATCH_DISMISSED = "dismissed"
MISMATCH_ESCALATED = "escalated"
MISMATCH_RESOLVED = "resolved"

_THOUSANDS_AMOUNT_RE = re.compile(r"^\d{1,3}(?:,\d{3})+$")
_DIGITS_RE = re.compile(r"^\d+$")
_RATE_LADDER_RE = re.compile(r"^\d{1,2}(?:,\d{1,2})+$")


def normalize_consolidated_value(value: str) -> str:
    """Digits-only for rupee amounts; leave joined rate ladders untouched."""
    text = (value or "").strip().replace(" ", "")
    if _THOUSANDS_AMOUNT_RE.fullmatch(text) or _DIGITS_RE.fullmatch(text):
        return text.replace(",", "")
    return text


def canonical_compare_group_id(group: str, value: str) -> str:
    """Map GPT schedule aliases onto the year-table rate group."""
    if group in RATE_COMPARE_GROUPS or _RATE_LADDER_RE.fullmatch(value):
        return "first_schedule_rates"
    return group


def normalize_consolidated_value(value: str) -> str:
    """Digits-only for rupee amounts; leave joined rate ladders untouched."""
    text = (value or "").strip().replace(" ", "")
    if _THOUSANDS_AMOUNT_RE.fullmatch(text) or _DIGITS_RE.fullmatch(text):
        return text.replace(",", "")
    return text


def next_status(
    *,
    old_status: str | None,
    old_consolidated: str | None,
    old_act: str | None,
    new_consolidated: str,
    new_act: str | None,
) -> str:
    values_match = new_act is not None and new_act == new_consolidated
    if values_match:
        return MISMATCH_RESOLVED
    pair_changed = old_consolidated != new_consolidated or old_act != new_act
    if old_status == MISMATCH_DISMISSED:
        return MISMATCH_OPEN if pair_changed else MISMATCH_DISMISSED
    if old_status == MISMATCH_ESCALATED:
        return MISMATCH_ESCALATED
    return MISMATCH_OPEN


def upsert_flag(
    session: Session,
    *,
    compare_group_id: str,
    year: str,
    value_consolidated: str,
    value_act: str | None,
    consolidated_source_doc_id: str,
    note: str | None = None,
) -> OeEngineMismatchFlag:
    flag = (
        session.query(OeEngineMismatchFlag)
        .filter_by(
            compare_group_id=compare_group_id,
            year=year,
            consolidated_source_doc_id=consolidated_source_doc_id,
        )
        .one_or_none()
    )
    status = next_status(
        old_status=None if flag is None else flag.status,
        old_consolidated=None if flag is None else flag.value_consolidated,
        old_act=None if flag is None else flag.value_act,
        new_consolidated=value_consolidated,
        new_act=value_act,
    )
    if flag is None:
        flag = OeEngineMismatchFlag(
            compare_group_id=compare_group_id,
            year=year,
            value_consolidated=value_consolidated,
            value_act=value_act,
            status=status,
            consolidated_source_doc_id=consolidated_source_doc_id,
            note=note,
        )
        session.add(flag)
        return flag
    flag.value_consolidated = value_consolidated
    flag.value_act = value_act
    flag.status = status
    if note:
        flag.note = note
    return flag


def recompare_all_facts(session: Session) -> int:
    """Act-promote direction: read stored Consolidated facts, never re-extract."""
    count = 0
    facts = session.query(OeEngineConsolidatedFact).all()
    for fact in facts:
        if fact.year not in ASSESSMENT_YEARS:
            continue
        act_value = lookup_act_value(session, fact.compare_group_id, fact.year)
        upsert_flag(
            session,
            compare_group_id=fact.compare_group_id,
            year=fact.year,
            value_consolidated=fact.value,
            value_act=act_value,
            consolidated_source_doc_id=fact.consolidated_source_doc_id,
            note="recompare after Act promote",
        )
        count += 1
    return count


def write_consolidated_facts(session: Session, run: ExtractRun) -> dict[str, Any]:
    written = 0
    flags = 0
    for entity in run.entities:
        if entity.get("entity_kind") != "consolidated_fact":
            continue
        if entity.get("included") is False:
            continue
        group = str(entity["compare_group_id"])
        year = str(entity["year"])
        value = normalize_consolidated_value(str(entity.get("value") or ""))
        if not group or not year or not value:
            continue
        if year not in ASSESSMENT_YEARS:
            continue
        canonical = canonical_compare_group_id(group, value)
        if canonical != group:
            stale_fact = (
                session.query(OeEngineConsolidatedFact)
                .filter_by(
                    compare_group_id=group,
                    year=year,
                    consolidated_source_doc_id=run.source_doc_id,
                )
                .one_or_none()
            )
            if stale_fact is not None:
                session.delete(stale_fact)
            stale_flag = (
                session.query(OeEngineMismatchFlag)
                .filter_by(
                    compare_group_id=group,
                    year=year,
                    consolidated_source_doc_id=run.source_doc_id,
                )
                .one_or_none()
            )
            if stale_flag is not None:
                session.delete(stale_flag)
            group = canonical
        row = (
            session.query(OeEngineConsolidatedFact)
            .filter_by(
                compare_group_id=group,
                year=year,
                consolidated_source_doc_id=run.source_doc_id,
            )
            .one_or_none()
        )
        if row is None:
            row = OeEngineConsolidatedFact(
                compare_group_id=group,
                year=year,
                value=value,
                consolidated_source_doc_id=run.source_doc_id,
            )
            session.add(row)
        else:
            row.value = value
        written += 1
        act_value = lookup_act_value(session, group, year)
        upsert_flag(
            session,
            compare_group_id=group,
            year=year,
            value_consolidated=value,
            value_act=act_value,
            consolidated_source_doc_id=run.source_doc_id,
            note="compare on Consolidated extract",
        )
        flags += 1
    session.flush()
    return {"facts_upserted": written, "flags_upserted": flags}


def list_flags(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.query(OeEngineMismatchFlag)
        .order_by(OeEngineMismatchFlag.compare_group_id, OeEngineMismatchFlag.year)
        .all()
    )
    return [
        {
            "id": row.id,
            "compare_group_id": row.compare_group_id,
            "year": row.year,
            "value_consolidated": row.value_consolidated,
            "value_act": row.value_act,
            "status": row.status,
            "consolidated_source_doc_id": row.consolidated_source_doc_id,
            "note": row.note,
        }
        for row in rows
    ]


def set_flag_status(session: Session, flag_id: int, status: str) -> OeEngineMismatchFlag:
    allowed = {MISMATCH_OPEN, MISMATCH_DISMISSED, MISMATCH_ESCALATED}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    flag = session.get(OeEngineMismatchFlag, flag_id)
    if flag is None:
        raise KeyError(flag_id)
    flag.status = status
    session.flush()
    return flag
