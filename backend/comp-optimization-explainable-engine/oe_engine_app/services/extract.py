"""Two-pass extract + deterministic quote gate. Full-doc live seed is Phase 6."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.schemas.extract import (
    ConsolidatedFactEntity,
    ExtractRun,
    GuideHelpEntity,
    RateBandEntity,
    ReliefEntity,
    terminus_for_tier,
)
from oe_engine_app.services.archive import archive_previous_and_diff
from oe_engine_app.services.effective_dates import fill_effective_dates
from oe_engine_app.services.engine_scope import infer_engine_scope
from oe_engine_app.services.extract_llm import ExtractLLM, QuoteCheck
from oe_engine_app.services.quote_gate import quote_gate
from oe_engine_app.services.split_period import expand_split_period_relief
from oe_engine_app.services.spend import (
    PHASE6_HARD_STOP_USD,
    PHASE6_SOFT_CAP_USD,
    SpendLedger,
)
from oe_engine_app.services.windows import (
    DocText,
    FocusWindow,
    extract_focus_windows,
    load_doc_text,
)
from oe_engine_app.services.terminus import apply_extract_terminus

MIN_QUOTE_CHARS = 15

GUIDE_COMPARE_GROUPS = frozenset(
    {
        "personal_relief",
        "employment_income_relief",
        "rental_income_relief",
        "senior_citizen_interest_income_relief",
        "foreign_currency_income_relief",
        "donation_to_charitable_institution",
        "donation_to_government_or_approved_fund",
        "solar_panel_relief",
        "qualifying_payment_carry_forward",
        "capital_allowance",
    }
)
_GUIDE_GROUP_ALIASES = {
    "personal": "personal_relief",
    "basic_relief": "personal_relief",
    "tax_free_threshold": "personal_relief",
    "employment_relief": "employment_income_relief",
    "employment_income": "employment_income_relief",
    "rent_relief": "rental_income_relief",
    "rental_relief": "rental_income_relief",
    "senior_citizen_interest_relief": "senior_citizen_interest_income_relief",
    "senior_citizen_relief": "senior_citizen_interest_income_relief",
    "foreign_currency_relief": "foreign_currency_income_relief",
    "charitable_donation": "donation_to_charitable_institution",
    "donations": "donation_to_charitable_institution",
    "solar": "solar_panel_relief",
    "solar_panel": "solar_panel_relief",
}


def canonical_guide_compare_group(group: str) -> str:
    key = (group or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in GUIDE_COMPARE_GROUPS:
        return key
    return _GUIDE_GROUP_ALIASES.get(key, key)


def _normalize_unit(value: str) -> str:
    unit = (value or "lkr").strip().lower()
    if unit in {"currency", "rs", "rs.", "rupees", "lkr"}:
        return "lkr"
    if unit in {"percent", "%", "pct"}:
        return "percent"
    if unit == "text":
        return "text"
    return "lkr"


def _now_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]


def _gate_fields(quote: str, window: FocusWindow, doc: DocText) -> dict[str, Any]:
    gated = quote_gate(quote, window.text, doc.stream, doc.tables_blob)
    long_enough = len((quote or "").strip()) >= MIN_QUOTE_CHARS
    included = bool(gated["quote_ok_window"] and gated["quote_ok_full_doc"] and long_enough)
    return {
        "quote_ok_window": gated["quote_ok_window"],
        "quote_ok_full_doc": gated["quote_ok_full_doc"],
        "quote_source": gated["quote_source"],
        "included": included,
    }


def _pass2_or_skip(llm: ExtractLLM | None, quote: str, focus_text: str) -> QuoteCheck:
    if llm is None:
        return QuoteCheck(verbatim=False, closest_quote="", note="dry-run")
    if not (quote or "").strip():
        return QuoteCheck(verbatim=False, closest_quote="", note="empty quote")
    return llm.pass2(quote=quote, focus_text=focus_text)


def _relief_entity(
    row: Any,
    *,
    source_doc_id: str,
    window_id: str,
    idx: int,
    window: FocusWindow,
    doc: DocText,
    check: QuoteCheck,
) -> dict[str, Any]:
    elig = row.eligibility
    entity = ReliefEntity(
        entry_id=f"{source_doc_id}:{window_id}:relief:{idx}",
        source_doc_id=source_doc_id,
        compare_group_id=row.compare_group_id,
        display_name=row.display_name,
        paragraph_ref=row.paragraph_ref,
        section_ref=row.section_ref,
        act_name=row.act_name,
        cap_amount=row.cap_amount or None,
        unit=_normalize_unit(row.unit),
        quote=row.quote,
        eligibility={
            "text": elig.text,
            "review_status": "pending",
            "quote": elig.quote,
        },
        required_evidence=list(row.required_evidence or []),
        filing_line=row.filing_line,
        stacking=row.stacking,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        engine_scope=infer_engine_scope(
            applies_to="",
            display_name=row.display_name,
            eligibility_text=elig.text,
            compare_group_id=row.compare_group_id,
        ),
        pass2_verbatim=check.verbatim,
        pass2_note=check.note,
        **_gate_fields(row.quote, window, doc),
    )
    return fill_effective_dates(entity.model_dump(mode="json"))


def _rate_entity(
    row: Any,
    *,
    source_doc_id: str,
    window_id: str,
    idx: int,
    window: FocusWindow,
    doc: DocText,
    check: QuoteCheck,
) -> dict[str, Any]:
    entity = RateBandEntity(
        entry_id=f"{source_doc_id}:{window_id}:band:{idx}",
        source_doc_id=source_doc_id,
        compare_group_id=row.compare_group_id or "first_schedule_rates",
        band_index=row.band_index,
        band_label=row.band_label,
        lower=row.lower,
        upper=row.upper or None,
        rate_percent=row.rate_percent,
        applies_to=row.applies_to,
        section_ref=row.section_ref or "First Schedule",
        act_name=row.act_name,
        effective_from=row.effective_from,
        effective_to=row.effective_to or "",
        quote=row.quote,
        engine_scope=infer_engine_scope(
            applies_to=row.applies_to,
            display_name=row.band_label,
            compare_group_id=row.compare_group_id or "first_schedule_rates",
            band_label=row.band_label,
        ),
        pass2_verbatim=check.verbatim,
        pass2_note=check.note,
        **_gate_fields(row.quote, window, doc),
    )
    return fill_effective_dates(entity.model_dump(mode="json"))


def _guide_entity(
    row: Any,
    *,
    source_doc_id: str,
    window_id: str,
    idx: int,
    window: FocusWindow,
    doc: DocText,
    check: QuoteCheck,
) -> dict[str, Any]:
    elig = row.eligibility
    entity = GuideHelpEntity(
        entry_id=f"{source_doc_id}:{window_id}:guide:{idx}",
        source_doc_id=source_doc_id,
        compare_group_id=canonical_guide_compare_group(row.compare_group_id),
        display_name=row.display_name,
        help=row.help,
        eligibility={
            "text": elig.text,
            "review_status": "pending",
            "quote": elig.quote,
        },
        required_evidence=list(row.required_evidence or []),
        section_ref=row.section_ref,
        quote=row.quote,
        pass2_verbatim=check.verbatim,
        pass2_note=check.note,
        **_gate_fields(row.quote, window, doc),
    )
    return entity.model_dump(mode="json")


def _fact_entity(
    row: Any,
    *,
    source_doc_id: str,
    window_id: str,
    idx: int,
    window: FocusWindow,
    doc: DocText,
    check: QuoteCheck,
) -> dict[str, Any]:
    entity = ConsolidatedFactEntity(
        entry_id=f"{source_doc_id}:{window_id}:fact:{idx}",
        source_doc_id=source_doc_id,
        compare_group_id=row.compare_group_id,
        year=row.year,
        value=row.value,
        quote=row.quote,
        section_ref=row.section_ref,
        pass2_verbatim=check.verbatim,
        pass2_note=check.note,
        **_gate_fields(row.quote, window, doc),
    )
    return entity.model_dump(mode="json")


def extract_window(
    *,
    doc: DocText,
    window: FocusWindow,
    llm: ExtractLLM | None,
    dry_run: bool,
) -> list[dict[str, Any]]:
    if dry_run or llm is None:
        return []
    entities: list[dict[str, Any]] = []
    target = window.heading
    if doc.tier == "guide":
        payload = llm.pass1_guide(
            act_title=doc.title,
            source_doc_id=doc.source_doc_id,
            target=target,
            focus_text=window.text,
        )
        for idx, row in enumerate(payload.guide_help):
            check = _pass2_or_skip(llm, row.quote, window.text)
            entities.append(
                _guide_entity(
                    row,
                    source_doc_id=doc.source_doc_id,
                    window_id=window.window_id,
                    idx=idx,
                    window=window,
                    doc=doc,
                    check=check,
                )
            )
        return entities
    if doc.tier == "consolidated":
        payload = llm.pass1_consolidated(
            act_title=doc.title,
            source_doc_id=doc.source_doc_id,
            target=target,
            focus_text=window.text,
        )
        for idx, row in enumerate(payload.consolidated_facts):
            check = _pass2_or_skip(llm, row.quote, window.text)
            entities.append(
                _fact_entity(
                    row,
                    source_doc_id=doc.source_doc_id,
                    window_id=window.window_id,
                    idx=idx,
                    window=window,
                    doc=doc,
                    check=check,
                )
            )
        return entities
    payload = llm.pass1_act(
        act_title=doc.title,
        source_doc_id=doc.source_doc_id,
        target=target,
        focus_text=window.text,
    )
    for idx, row in enumerate(payload.reliefs):
        check = _pass2_or_skip(llm, row.quote, window.text)
        entities.extend(
            expand_split_period_relief(
                _relief_entity(
                    row,
                    source_doc_id=doc.source_doc_id,
                    window_id=window.window_id,
                    idx=idx,
                    window=window,
                    doc=doc,
                    check=check,
                )
            )
        )
    for idx, row in enumerate(payload.rate_bands):
        check = _pass2_or_skip(llm, row.quote, window.text)
        entities.append(
            _rate_entity(
                row,
                source_doc_id=doc.source_doc_id,
                window_id=window.window_id,
                idx=idx,
                window=window,
                doc=doc,
                check=check,
            )
        )
    return entities


def write_extract_run(run: ExtractRun, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run.source_doc_id}__{run.extraction_run_id}.json"
    path.write_text(json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    if not run.dry_run:
        archive_previous_and_diff(run.model_dump(mode="json"))
    return path


def run_extract(
    session: Session,
    *,
    source_doc_id: str,
    llm: ExtractLLM | None,
    ledger: SpendLedger,
    dry_run: bool,
    schema_validate: bool,
    seed: bool = False,
    apply_terminus: bool = True,
) -> ExtractRun:
    if not dry_run and not schema_validate and not seed:
        raise RuntimeError(
            "Full-document live extract is Phase 6. Use --dry-run, --schema-validate, or --seed."
        )
    if seed:
        ledger.assert_phase6_caps()
        notes_seed = (
            f"Phase 6 seed. Soft ${PHASE6_SOFT_CAP_USD:.0f} / "
            f"hard ${PHASE6_HARD_STOP_USD:.0f}. "
            f"Prior spend ${ledger.prior_usd:.4f}."
        )
    else:
        notes_seed = ""
    doc = load_doc_text(session, source_doc_id)
    windows = extract_focus_windows(doc, schema_validate=schema_validate)
    entities: list[dict[str, Any]] = []
    notes: list[str] = []
    if notes_seed:
        notes.append(notes_seed)
    if schema_validate:
        notes.append(
            "Schema-validation windows only (Fifth Schedule + First Schedule). "
            "Not full-Act coverage; Phase 6 still extracts 24/2017 on-budget."
        )
    if dry_run:
        notes.append("dry-run: windows listed, no GPT calls, $0")
    for window in windows:
        ledger.assert_phase6_caps()
        entities.extend(
            extract_window(doc=doc, window=window, llm=None if dry_run else llm, dry_run=dry_run)
        )
    run = ExtractRun(
        extraction_run_id=_now_run_id(),
        source_doc_id=source_doc_id,
        tier=doc.tier,  # type: ignore[arg-type]
        terminus=terminus_for_tier(doc.tier),
        model=get_oe_engine_settings().OE_ENGINE_EXTRACT_MODEL,
        dry_run=dry_run,
        usd_this_run=round(ledger.this_run_usd, 6),
        usd_running_total=round(ledger.total_usd, 6),
        windows=[w.to_schema() for w in windows],
        entities=entities,
        notes=notes,
    )
    if apply_terminus and not dry_run:
        apply_extract_terminus(session, run)
        session.commit()
    settings = get_oe_engine_settings()
    write_extract_run(run, settings.OE_ENGINE_EXTRACT_OUT)
    ledger.dump()
    return run
