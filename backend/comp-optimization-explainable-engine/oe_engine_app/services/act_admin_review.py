"""Review, validation, impact preview, and activation for act-admin drafts."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from db.year_views import OeEnginePromotedEntity, OeEngineYearRelief
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.act_admin_store import (
    ActAdminPaths,
    act_admin_paths,
    load_decisions,
    load_draft,
    load_job,
    list_jobs,
    now_iso,
    save_decisions,
    save_draft,
    save_job,
)
from oe_engine_app.services.compiler import (
    BASE_ASSESSMENT_YEARS,
    assessment_year_label,
    compile_maps,
    load_promoted_entities,
    recompile_year_views,
    resolved_effective_from,
    validate_rate_band_set,
    validate_rate_ladder_key,
)
from oe_engine_app.services.engine_scope import is_promotable_scope, resolve_engine_scope
from oe_engine_app.services.extract_dedupe import (
    collapse_duplicate_extract_entities,
    scrub_interview_fields,
)
from oe_engine_app.services.hash_match import canonical_payload_hash
from oe_engine_app.services.terminus import ChunkCoverageError, promote_act_run
from oe_engine_app.services.windows import load_doc_text, named_schedule_windows
from oe_engine_app.services.year_store import present_relief

ReviewStatus = str
ChangeAction = str

RELIEF_KINDS = frozenset({"relief"})
RATE_KINDS = frozenset({"rate_band"})
_INTERVIEW_KEYS = ("question_prompt", "help", "input_kind", "display_name")
YEAR_KIND_VALUES = frozenset({"UPDATE", "NEW_YEAR"})


class ReviewValidationError(ValueError):
    """Blocking issue before activation."""


def _entry_id(entity: dict[str, Any]) -> str:
    return str(entity.get("entry_id") or "")


def draft_entities(draft: dict[str, Any]) -> list[dict[str, Any]]:
    entities = draft.get("entities") or []
    return [e for e in entities if isinstance(e, dict)]


def review_entities(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows shown in review: reprints from overlapping windows are collapsed."""
    rows = [dict(entity) for entity in collapse_duplicate_extract_entities(draft_entities(draft))]
    for row in rows:
        scrub_interview_fields(row)
    return rows


def promotable_entities(draft: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entity in draft_entities(draft):
        if entity.get("entity_kind") not in {"relief", "rate_band"}:
            continue
        if entity.get("included") is False:
            continue
        if entity.get("change_action") == "repeal":
            continue
        if not is_promotable_scope(entity):
            continue
        out.append(entity)
    return out


def _is_review_entity(entity: dict[str, Any]) -> bool:
    return str(entity.get("entity_kind") or "") in {"relief", "rate_band"}


def _in_individual_engine(entity: dict[str, Any]) -> bool:
    return _is_review_entity(entity) and is_promotable_scope(entity)


def _review_scope_entities(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows the individual income-tax engine can promote."""
    return [e for e in review_entities(draft) if _in_individual_engine(e)]


def _accepted_for_promote(
    draft: dict[str, Any],
    session: Session | None = None,
) -> list[dict[str, Any]]:
    prior = _prior_interview_cache(session)
    out: list[dict[str, Any]] = []
    for entity in _review_scope_entities(draft):
        if entity.get("included") is False:
            continue
        if str(entity.get("review_status") or "") != "accepted":
            continue
        if entity.get("entity_kind") == "relief":
            group = str(entity.get("compare_group_id") or "")
            out.append(_fill_interview_fields(dict(entity), prior.get(group)))
        else:
            out.append(dict(entity))
    return out


def _prior_interview_cache(session: Session | None) -> dict[str, dict[str, str]]:
    """Latest live interview wording per compare_group_id from year views / promoted rows."""
    if session is None:
        return {}
    cache: dict[str, dict[str, str]] = {}
    year_rows = (
        session.query(OeEngineYearRelief)
        .order_by(OeEngineYearRelief.assessment_year.desc())
        .all()
    )
    for row in year_rows:
        group = str(row.compare_group_id or "")
        if not group or group in cache:
            continue
        payload = dict(row.payload_json or {})
        prompt = str(payload.get("question_prompt") or "")
        if not prompt:
            continue
        cache[group] = {
            "question_prompt": prompt,
            "help": str(payload.get("help") or ""),
            "input_kind": str(payload.get("input_kind") or row.input_kind or ""),
            "display_name": str(payload.get("display_name") or row.display_name or ""),
        }
    for row in load_promoted_entities(session):
        if row.entity_kind != "relief":
            continue
        group = str(row.compare_group_id or "")
        if not group or group in cache:
            continue
        payload = dict(row.payload_json or {})
        prompt = str(payload.get("question_prompt") or "")
        if not prompt:
            continue
        cache[group] = {
            "question_prompt": prompt,
            "help": str(payload.get("help") or ""),
            "input_kind": str(payload.get("input_kind") or ""),
            "display_name": str(payload.get("display_name") or ""),
        }
    return cache


def _fill_interview_fields(
    entity: dict[str, Any],
    prior: dict[str, str] | None,
    *,
    prefer_prior: bool = False,
) -> dict[str, Any]:
    out = dict(entity)
    prior_prompt = str((prior or {}).get("question_prompt") or "").strip()
    draft_prompt_empty = not str(out.get("question_prompt") or "").strip()
    if prior and prior_prompt:
        for key in _INTERVIEW_KEYS:
            prior_val = str((prior or {}).get(key) or "").strip()
            if not prior_val:
                continue
            if prefer_prior or not str(out.get(key) or "").strip():
                out[key] = prior_val
        if (
            (prefer_prior or draft_prompt_empty)
            and str(entity.get("input_kind") or "").strip() in {"", "notice"}
            and prior.get("input_kind")
        ):
            out["input_kind"] = prior["input_kind"]
        out["has_prior_catalog"] = True
        out["prior_question_prompt"] = prior_prompt
    else:
        out["has_prior_catalog"] = False
        out["prior_question_prompt"] = ""
    return out


def _apply_prior_to_draft(draft: dict[str, Any], session: Session | None) -> None:
    prior = _prior_interview_cache(session)
    for entity in draft_entities(draft):
        if entity.get("entity_kind") != "relief":
            continue
        group = str(entity.get("compare_group_id") or "")
        filled = _fill_interview_fields(entity, prior.get(group))
        for key in _INTERVIEW_KEYS:
            if filled.get(key):
                entity[key] = filled[key]


def _open_top_accepted_rate_bands(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """After auditors reject a top slab, leave the highest accepted band open-ended.

    Rejected rows are already excluded from `entities`. Without this, validating the
    remaining ladder fails with "Top band should have blank upper bound" and activate
    is blocked even though the auditor intentionally dropped the top extract row.
    """
    by_ladder: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        if entity.get("entity_kind") != "rate_band":
            continue
        key = validate_rate_ladder_key(entity)
        by_ladder.setdefault(key, []).append(entity)
    opened_ids: set[str] = set()
    for bands in by_ladder.values():
        if not bands:
            continue
        top = max(bands, key=lambda row: int(row.get("band_index") or 0))
        entry = _entry_id(top)
        if entry:
            opened_ids.add(entry)
    out: list[dict[str, Any]] = []
    for entity in entities:
        if (
            entity.get("entity_kind") == "rate_band"
            and _entry_id(entity) in opened_ids
            and str(entity.get("upper") or "").strip()
        ):
            patched = dict(entity)
            patched["upper"] = ""
            out.append(patched)
        else:
            out.append(entity)
    return out


def _sync_rate_uppers_into_draft(
    draft: dict[str, Any],
    accepted: list[dict[str, Any]],
) -> None:
    """Write normalized rate uppers (open top band) back into the draft entities."""
    by_id = {
        _entry_id(entity): entity
        for entity in accepted
        if entity.get("entity_kind") == "rate_band" and _entry_id(entity)
    }
    for entity in draft_entities(draft):
        entry = _entry_id(entity)
        if entry in by_id:
            entity["upper"] = by_id[entry].get("upper") or ""


def blocking_issues(draft: dict[str, Any], session: Session | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    ctx = _year_context(session)
    accepted = _accepted_for_promote(draft, session)
    for entity in accepted:
        kind = str(entity.get("entity_kind") or "")
        entry = _entry_id(entity)
        if not entry:
            issues.append({"entry_id": "", "code": "missing_entry_id", "message": "Row missing entry_id."})
            continue
        if _needs_year_kind(entity, ctx) and not _year_kind(entity):
            issues.append(
                {
                    "entry_id": entry,
                    "code": "missing_year_kind",
                    "message": (
                        "Choose Create a new year or Update existing year "
                        "(this Act date is not in the live catalog yet)."
                    ),
                }
            )
        if not (
            (entity.get("quote_ok_window") and entity.get("quote_ok_full_doc"))
            or entity.get("pass2_verbatim")
        ):
            issues.append(
                {
                    "entry_id": entry,
                    "code": "quote_gate",
                    "message": "Quote gate failed — fix or reject this row.",
                }
            )
        if kind == "relief" and entity.get("change_action") != "repeal":
            if not str(entity.get("compare_group_id") or "").strip():
                issues.append(
                    {
                        "entry_id": entry,
                        "code": "missing_compare_group",
                        "message": "Relief missing compare_group_id.",
                    }
                )
            if not str(entity.get("effective_from") or "").strip() and not str(
                entity.get("source_doc_id") or ""
            ).startswith("oee-act-"):
                issues.append(
                    {
                        "entry_id": entry,
                        "code": "missing_effective_from",
                        "message": "Relief missing effective_from.",
                    }
                )
        if kind == "rate_band":
            if not str(entity.get("rate_percent") or "").strip():
                issues.append(
                    {
                        "entry_id": entry,
                        "code": "missing_rate",
                        "message": "Rate band missing rate_percent.",
                    }
                )
    rate_errors = validate_rate_band_set(
        [
            e
            for e in _open_top_accepted_rate_bands(accepted)
            if e.get("entity_kind") == "rate_band"
        ]
    )
    for err in rate_errors:
        issues.append({"entry_id": "", "code": "rate_band_validation", "message": err})
    return issues


def review_ready(draft: dict[str, Any], session: Session | None = None) -> dict[str, Any]:
    scope_rows = _review_scope_entities(draft)
    out_of_scope = [
        e
        for e in draft_entities(draft)
        if _is_review_entity(e) and not _in_individual_engine(e)
    ]
    pending = [e for e in scope_rows if str(e.get("review_status") or "pending") == "pending"]
    rejected = [e for e in scope_rows if str(e.get("review_status") or "") == "rejected"]
    accepted = [e for e in scope_rows if str(e.get("review_status") or "") == "accepted"]
    issues = blocking_issues(draft, session=session)
    reliefs = [e for e in scope_rows if e.get("entity_kind") == "relief"]
    rates = [e for e in scope_rows if e.get("entity_kind") == "rate_band"]
    activate_allowed = len(pending) == 0 and len(issues) == 0 and len(accepted) > 0
    activate_block_reason: str | None = None
    if not activate_allowed:
        if len(accepted) == 0:
            activate_block_reason = "Approve at least one row before activate."
        elif len(pending) > 0:
            activate_block_reason = f"{len(pending)} row(s) still need approve or reject."
        elif len(issues) > 0:
            if any(issue.get("code") == "missing_year_kind" for issue in issues):
                activate_block_reason = (
                    "Choose Create a new year or Update existing year on approved "
                    "rows before activate."
                )
            else:
                activate_block_reason = (
                    f"{len(issues)} issue(s) on approved rows — reject those rows or "
                    "fix quotes/caps."
                )
    return {
        "included_count": len(scope_rows),
        "pending_count": len(pending),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "blocking_issue_count": len(issues),
        "blocking_issues": issues,
        "relief_count": len(reliefs),
        "rate_count": len(rates),
        "out_of_scope_count": len(out_of_scope),
        "activate_allowed": activate_allowed,
        "activate_block_reason": activate_block_reason,
    }


def _ya_start_containing(value: date) -> date:
    if value.month >= 4:
        return date(value.year, 4, 1)
    return date(value.year - 1, 4, 1)


def _year_kind(entity: dict[str, Any]) -> str:
    kind = str(entity.get("year_kind") or "").strip().upper()
    return kind if kind in YEAR_KIND_VALUES else ""


def _year_context(session: Session | None) -> dict[str, Any]:
    live: list[str] = list(BASE_ASSESSMENT_YEARS)
    if session is not None:
        from oe_engine_app.services.year_store import list_years

        listed = [str(row["assessment_year"]) for row in list_years(session)]
        if listed:
            live = listed
    update_ya = live[-1]
    return {
        "live_years": live,
        "update_assessment_year": update_ya,
    }


def _suggest_year_kind(derived_ya: str | None, ctx: dict[str, Any]) -> str:
    update_ya = str(ctx.get("update_assessment_year") or BASE_ASSESSMENT_YEARS[-1])
    live = set(ctx.get("live_years") or [])
    if derived_ya and derived_ya not in live and derived_ya > update_ya:
        return "NEW_YEAR"
    return "UPDATE"


def _needs_year_kind(entity: dict[str, Any], ctx: dict[str, Any]) -> bool:
    return _suggest_year_kind(derived_assessment_year(entity), ctx) == "NEW_YEAR"


def derived_assessment_year(entity: dict[str, Any]) -> str | None:
    try:
        effective = resolved_effective_from(entity)
        return assessment_year_label(_ya_start_containing(effective))
    except (TypeError, ValueError):
        return None


def section_label_from_entity(entity: dict[str, Any]) -> str:
    entry_id = str(entity.get("entry_id") or "")
    parts = entry_id.split(":")
    if len(parts) >= 2:
        slug = parts[1]
        if slug == "fifth_schedule":
            return "Fifth Schedule"
        if slug == "first_schedule":
            return "First Schedule"
    section = str(entity.get("section_ref") or "").strip()
    if section:
        lowered = section.lower()
        if lowered.endswith(" schedule"):
            return section.title()
        if section.isdigit():
            return f"Section {section}"
        if lowered.startswith("section "):
            return section
        return section
    if len(parts) >= 2:
        slug = parts[1]
        return slug.replace("_", " ").title()
    return "Act text"


def _entry_window_id(entity: dict[str, Any]) -> str:
    entry_id = str(entity.get("entry_id") or "")
    parts = entry_id.split(":")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    section = str(entity.get("section_ref") or "").strip().lower()
    if "first schedule" in section:
        return "first_schedule"
    if "fifth schedule" in section:
        return "fifth_schedule"
    return ""


def _section_act_prose_cache(session: Session | None, source_doc_id: str) -> dict[str, str]:
    if session is None or not source_doc_id:
        return {}
    try:
        doc = load_doc_text(session, source_doc_id)
    except ValueError:
        return {}
    return {window.window_id: window.text for window in named_schedule_windows(doc)}


def _enrich_entity(
    entity: dict[str, Any],
    *,
    section_prose_cache: dict[str, str] | None = None,
    prior_cache: dict[str, dict[str, str]] | None = None,
    year_ctx: dict[str, Any] | None = None,
    prefer_prior: bool = False,
) -> dict[str, Any]:
    enriched = dict(entity)
    derived_ya = derived_assessment_year(entity)
    ctx = year_ctx or _year_context(None)
    enriched["derived_assessment_year"] = derived_ya
    enriched["section_label"] = section_label_from_entity(entity)
    enriched["year_kind"] = _year_kind(entity) or None
    enriched["year_kind_suggested"] = _suggest_year_kind(derived_ya, ctx)
    enriched["new_assessment_year"] = derived_ya
    enriched["update_assessment_year"] = ctx.get("update_assessment_year")
    if _is_review_entity(entity):
        scope = resolve_engine_scope(entity)
        enriched["engine_scope"] = scope
        enriched["in_individual_engine"] = scope == "individual"
    if entity.get("entity_kind") == "relief":
        group = str(enriched.get("compare_group_id") or "")
        prior = (prior_cache or {}).get(group)
        enriched = _fill_interview_fields(enriched, prior, prefer_prior=prefer_prior)
        enriched["interview_preview"] = present_relief(enriched)
    if entity.get("entity_kind") == "rate_band":
        from oe_engine_app.services.terminal_benefit import (
            is_terminal_rate_group,
            stamp_terminal_rate_payload,
        )

        if is_terminal_rate_group(str(enriched.get("compare_group_id") or "")):
            enriched = stamp_terminal_rate_payload(enriched)
        window_id = _entry_window_id(entity)
        prose = (section_prose_cache or {}).get(window_id, "")
        if prose:
            enriched["section_act_prose"] = prose
    return enriched


def _job_context(draft: dict[str, Any], *, paths: ActAdminPaths, session: Session | None = None) -> dict[str, Any]:
    job_id = str(draft.get("job_id") or "").strip()
    job = load_job(job_id, paths) if job_id else None
    identity = (job or {}).get("act_identity") or {}
    sid = str(draft.get("source_doc_id") or "").strip()
    reused = ""
    ingest_note: str | None = None
    if job is not None:
        reused = str(job.get("ingest_reused_from") or "").strip()
        if reused or str(job.get("ingest_status") or "") == "skipped_sha256":
            canonical = reused or "an existing corpus entry"
            ingest_note = (
                f"This PDF was already ingested in the engine corpus ({canonical}). "
                "Activate merges your approved rows into year views; rejected rows are ignored."
            )
    already_in_system = False
    if reused or (job is not None and str(job.get("ingest_status") or "") == "skipped_sha256"):
        already_in_system = True
    if session is not None and sid:
        try:
            from db.year_views import OeEnginePromotedRun

            if session.get(OeEnginePromotedRun, sid) is not None:
                already_in_system = True
            if reused and session.get(OeEnginePromotedRun, reused) is not None:
                already_in_system = True
        except Exception:  # noqa: BLE001
            pass
    return {
        "job_id": job_id or None,
        "act_title": identity.get("label"),
        "act_no": identity.get("act_no"),
        "act_year": identity.get("act_year"),
        "pdf_file_name": (job or {}).get("original_filename"),
        "extracted_at": (job or {}).get("extract_finished_at") or draft.get("extract_finished_at"),
        "extraction_usd": draft.get("usd_this_run"),
        "entity_count": len(draft_entities(draft)),
        "ingest_note": ingest_note,
        "already_in_system": already_in_system,
        "note": (
            "This Act is already in the live engine catalog. Approved rows match prior "
            "auditor decisions / live promote (read-only). Previously rejected rows stay "
            "rejected and out of year views."
            if already_in_system
            else (
                "Extract ran as a new draft. Live year views are unchanged until you activate. "
                "This engine promotes individual income tax only — entity and other taxpayer rows "
                "stay in the extract for audit but are not shown in review or RAG preview."
            )
        ),
    }


def _as_rejected_noise(entity: dict[str, Any], *, reason: str) -> dict[str, Any]:
    out = dict(entity)
    out["review_status"] = "rejected"
    out["included"] = False
    out["in_individual_engine"] = False
    out["engine_scope"] = out.get("engine_scope") or "other"
    out["noise_kind"] = out.get("noise_kind") or "entity_business"
    out["reject_reason"] = str(out.get("reject_reason") or reason).strip() or reason
    return out


def _apply_persisted_decisions(
    draft: dict[str, Any],
    *,
    paths: ActAdminPaths,
    session: Session | None = None,
) -> bool:
    """Re-apply auditor accept/reject from decisions.json onto a fresh extract draft.

    Re-extract resets rows to pending. Without this, a previously rejected relief
    looks pending — and the already-in-system UI was painting those as Approved.
    Rejected decisions always win; live promoted rows without a decision are marked
    accepted for continuity.
    """
    sid = str(draft.get("source_doc_id") or "").strip()
    if not sid:
        return False
    ledger = load_decisions(paths)
    rows = ledger.get("rows") or {}
    by_entry: dict[str, dict[str, Any]] = {}
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        entry = str(row.get("entry_id") or "").strip()
        row_sid = str(row.get("source_doc_id") or "").strip()
        if not entry:
            continue
        if row_sid and row_sid != sid and not str(key).startswith(f"{sid}::"):
            continue
        if not row_sid and not str(key).startswith(f"{sid}::"):
            continue
        by_entry[entry] = row

    live_entries: set[str] = set()
    if session is not None:
        try:
            for promoted in load_promoted_entities(session):
                if str(promoted.source_doc_id or "") != sid:
                    continue
                eid = str(promoted.entry_id or "").strip()
                if eid:
                    live_entries.add(eid)
        except Exception:  # noqa: BLE001
            live_entries = set()

    changed = False
    for entity in draft_entities(draft):
        if not _is_review_entity(entity):
            continue
        entry = _entry_id(entity)
        if not entry:
            continue
        decision = by_entry.get(entry)
        status = str((decision or {}).get("review_status") or "").strip()
        if status in {"accepted", "rejected"}:
            if str(entity.get("review_status") or "") != status:
                entity["review_status"] = status
                changed = True
            if decision.get("year_kind") and not str(entity.get("year_kind") or "").strip():
                entity["year_kind"] = decision["year_kind"]
                changed = True
            if decision.get("reviewer") and not str(entity.get("reviewed_by") or "").strip():
                entity["reviewed_by"] = decision["reviewer"]
                changed = True
            if decision.get("reviewed_at") and not str(entity.get("reviewed_at") or "").strip():
                entity["reviewed_at"] = decision["reviewed_at"]
                changed = True
            if status == "rejected" and entity.get("included") is not False:
                entity["included"] = False
                changed = True
            continue
        if entry in live_entries and str(entity.get("review_status") or "pending") == "pending":
            entity["review_status"] = "accepted"
            changed = True
    return changed


def review_payload(
    source_doc_id: str,
    *,
    paths: ActAdminPaths | None = None,
    session: Session | None = None,
    enrich_prose: bool = True,
) -> dict[str, Any]:
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    if _apply_persisted_decisions(draft, paths=root, session=session):
        save_draft(draft, root)
    readiness = review_ready(draft, session=session)
    section_prose_cache = (
        _section_act_prose_cache(session, source_doc_id) if enrich_prose else {}
    )
    prior_cache = _prior_interview_cache(session)
    year_ctx = _year_context(session)
    job_ctx = _job_context(draft, paths=root, session=session)
    prefer_prior = bool(job_ctx.get("already_in_system"))
    entities = [
        _enrich_entity(
            e,
            section_prose_cache=section_prose_cache,
            prior_cache=prior_cache,
            year_ctx=year_ctx,
            prefer_prior=prefer_prior,
        )
        for e in review_entities(draft)
    ]
    in_scope = [e for e in entities if e.get("in_individual_engine")]
    reliefs = [e for e in in_scope if e.get("entity_kind") == "relief"]
    rates = [e for e in in_scope if e.get("entity_kind") == "rate_band"]
    out_of_scope = [
        _as_rejected_noise(
            e,
            reason=(
                "Out of scope for this engine — entity / other taxpayer rule. "
                "Individual income tax only."
            ),
        )
        for e in entities
        if _is_review_entity(e) and not e.get("in_individual_engine")
    ]
    rejected_noise: list[dict[str, Any]] = list(out_of_scope)
    # Only real out-of-scope rows from this extract — do not inject hardcoded
    # company/trust demo samples (those quotes looked like 2017 Act text and were
    # never auditor-rejected decisions).
    derived = next(
        (
            str(e.get("derived_assessment_year") or "")
            for e in in_scope
            if e.get("derived_assessment_year")
        ),
        "",
    )
    year_ctx = {
        **year_ctx,
        "new_assessment_year": derived or None,
        "year_kind_suggested": _suggest_year_kind(derived or None, year_ctx),
    }
    return {
        "source_doc_id": source_doc_id,
        "tier": draft.get("tier") or "act",
        "terminus": draft.get("terminus") or "review_then_promote",
        "extraction_run_id": draft.get("extraction_run_id"),
        **job_ctx,
        "year_context": year_ctx,
        "entities": entities,
        "reliefs": reliefs,
        "rates": rates,
        "rejected_noise": rejected_noise,
        "entity_count": len(in_scope),
        "extracted_entity_count": len([e for e in entities if _is_review_entity(e)]),
        "promote_allowed": True,
        **readiness,
    }


def _find_entity(draft: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for entity in draft_entities(draft):
        if _entry_id(entity) == entry_id:
            return entity
    raise KeyError(f"entry {entry_id} not found")


def patch_row(
    source_doc_id: str,
    entry_id: str,
    *,
    reviewer: str,
    patch: dict[str, Any],
    paths: ActAdminPaths | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    entity = _find_entity(draft, entry_id)
    allowed = {
        "review_status",
        "included",
        "change_action",
        "compare_group_id",
        "display_name",
        "cap_amount",
        "effective_from",
        "effective_to",
        "input_kind",
        "question_prompt",
        "help",
        "engine_binding",
        "engine_scope",
        "eligibility",
        "required_evidence",
        "sort_order",
        "year_kind",
    }
    if "year_kind" in patch:
        kind = str(patch.get("year_kind") or "").strip().upper()
        if kind not in YEAR_KIND_VALUES:
            raise ValueError("year_kind must be UPDATE or NEW_YEAR")
        patch = {**patch, "year_kind": kind}
    for key, value in patch.items():
        if key not in allowed:
            continue
        entity[key] = value
    if "year_kind" in patch:
        entity["year_kind_set_by"] = reviewer
        entity["year_kind_set_at"] = now_iso()
    entity["reviewed_by"] = reviewer
    entity["reviewed_at"] = now_iso()
    save_draft(draft, root)
    ledger = load_decisions(root)
    rows = ledger.setdefault("rows", {})
    rows[f"{source_doc_id}::{entry_id}"] = {
        "source_doc_id": source_doc_id,
        "entry_id": entry_id,
        "review_status": entity.get("review_status"),
        "change_action": entity.get("change_action"),
        "year_kind": entity.get("year_kind"),
        "reviewer": reviewer,
        "reviewed_at": entity["reviewed_at"],
    }
    save_decisions(ledger, root)
    return review_payload(source_doc_id, paths=root, session=session, enrich_prose=False)


def set_year_kind_all(
    source_doc_id: str,
    *,
    reviewer: str,
    year_kind: str,
    paths: ActAdminPaths | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Stamp UPDATE or NEW_YEAR on every in-scope included row (Catalog Admin pattern)."""
    kind = str(year_kind or "").strip().upper()
    if kind not in YEAR_KIND_VALUES:
        raise ValueError("year_kind must be UPDATE or NEW_YEAR")
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    stamped_at = now_iso()
    for entity in draft_entities(draft):
        if not _in_individual_engine(entity):
            continue
        if entity.get("included") is False:
            continue
        entity["year_kind"] = kind
        entity["year_kind_set_by"] = reviewer
        entity["year_kind_set_at"] = stamped_at
        entity["reviewed_by"] = reviewer
        entity["reviewed_at"] = stamped_at
    save_draft(draft, root)
    return review_payload(source_doc_id, paths=root, session=session, enrich_prose=False)


def _entity_fingerprint(entities: list[dict[str, Any]]) -> str:
    canonical = sorted(
        [
            {
                "entry_id": e.get("entry_id"),
                "entity_kind": e.get("entity_kind"),
                "compare_group_id": e.get("compare_group_id"),
                "change_action": e.get("change_action"),
                "review_status": e.get("review_status"),
                "included": e.get("included"),
                "cap_amount": e.get("cap_amount"),
                "effective_from": e.get("effective_from"),
                "effective_to": e.get("effective_to"),
                "band_index": e.get("band_index"),
                "lower": e.get("lower"),
                "upper": e.get("upper"),
                "rate_percent": e.get("rate_percent"),
                "applies_to": e.get("applies_to"),
                "year_kind": e.get("year_kind"),
            }
            for e in entities
        ],
        key=lambda row: str(row.get("entry_id") or ""),
    )
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _snapshot_year_views(session: Session) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    rows = load_promoted_entities(session)
    return compile_maps(rows)


def _rows_from_entities(
    entities: list[dict[str, Any]],
    *,
    source_doc_id: str,
    extraction_run_id: str,
) -> list[OeEnginePromotedEntity]:
    now = datetime.now(timezone.utc)
    out: list[OeEnginePromotedEntity] = []
    for entity in entities:
        payload = dict(entity)
        payload["source_doc_id"] = source_doc_id
        payload["extraction_run_id"] = extraction_run_id
        out.append(
            OeEnginePromotedEntity(
                source_doc_id=source_doc_id,
                extraction_run_id=extraction_run_id,
                entity_kind=str(entity.get("entity_kind") or ""),
                compare_group_id=str(entity.get("compare_group_id") or ""),
                entry_id=str(entity.get("entry_id") or ""),
                payload_json=payload,
                payload_hash="preview",
                promoted_at=now,
            )
        )
    return out


def _merge_promoted_rows(
    session: Session,
    draft: dict[str, Any],
) -> list[OeEnginePromotedEntity]:
    sid = str(draft.get("source_doc_id") or "")
    # Rejected rows are never merged; open the highest accepted band per ladder.
    accepted = _open_top_accepted_rate_bands(_accepted_for_promote(draft, session))
    repeal_rows = [e for e in accepted if e.get("change_action") == "repeal"]
    promote_rows = [e for e in accepted if e.get("change_action") != "repeal"]
    existing = [
        row
        for row in load_promoted_entities(session)
        if row.source_doc_id != sid
    ]
    merged = list(existing)
    run_id = str(draft.get("extraction_run_id") or "")
    merged.extend(_rows_from_entities(promote_rows, source_doc_id=sid, extraction_run_id=run_id))
    merged.extend(_rows_from_entities(repeal_rows, source_doc_id=sid, extraction_run_id=run_id))
    return merged


def _diff_maps(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    *,
    key_fn,
) -> dict[str, Any]:
    years = sorted(set(before) | set(after))
    by_year: dict[str, Any] = {}
    for ya in years:
        old_map = {key_fn(item): item for item in before.get(ya, [])}
        new_map = {key_fn(item): item for item in after.get(ya, [])}
        changes: list[dict[str, Any]] = []
        for key in sorted(set(old_map) | set(new_map)):
            old = old_map.get(key)
            new = new_map.get(key)
            if old is None and new is not None:
                changes.append({"key": key, "change": "added"})
            elif old is not None and new is None:
                changes.append({"key": key, "change": "removed"})
            elif old is not None and new is not None and old != new:
                changes.append({"key": key, "change": "changed"})
            elif old is not None and new is not None:
                changes.append({"key": key, "change": "unchanged"})
        by_year[ya] = changes
    return by_year


def _preview_cell(ya: str, item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {
            "assessment_year": ya,
            "cap_amount": None,
            "source_doc_id": None,
            "entry_id": None,
            "display_name": None,
            "rate_percent": None,
        }
    return {
        "assessment_year": ya,
        "cap_amount": item.get("cap_amount"),
        "source_doc_id": item.get("source_doc_id"),
        "entry_id": item.get("entry_id"),
        "display_name": item.get("display_name"),
        "rate_percent": item.get("rate_percent"),
    }


def _find_relief_item(items: list[dict[str, Any]], group_id: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("compare_group_id") or "") == group_id:
            return item
    return None


def _find_rate_item(items: list[dict[str, Any]], band_index: int) -> dict[str, Any] | None:
    for item in items:
        if int(item.get("band_index") or 0) == band_index:
            return item
    return None


def _build_relief_groups(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    group_ids: set[str],
) -> list[dict[str, Any]]:
    years = sorted(set(before) | set(after))
    groups: list[dict[str, Any]] = []
    for group_id in sorted(group_ids):
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        display_name = group_id.replace("_", " ").title()
        for ya in years:
            b_item = _find_relief_item(before.get(ya, []), group_id)
            a_item = _find_relief_item(after.get(ya, []), group_id)
            if a_item and a_item.get("display_name"):
                display_name = str(a_item["display_name"])
            elif b_item and b_item.get("display_name"):
                display_name = str(b_item["display_name"])
            before_rows.append(_preview_cell(ya, b_item))
            after_rows.append(_preview_cell(ya, a_item))
        groups.append(
            {
                "compare_group_id": group_id,
                "display_name": display_name,
                "entity_kind": "relief",
                "before": before_rows,
                "after": after_rows,
            }
        )
    return groups


def _build_rate_groups(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    accepted_rates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    years = sorted(set(before) | set(after))
    groups: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for entity in accepted_rates:
        group_id = str(entity.get("compare_group_id") or "rate_rules")
        band_index = int(entity.get("band_index") or 0)
        key = (group_id, band_index)
        if key in seen:
            continue
        seen.add(key)
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        display_name = str(entity.get("band_label") or entity.get("display_name") or group_id)
        for ya in years:
            b_item = _find_rate_item(before.get(ya, []), band_index)
            a_item = _find_rate_item(after.get(ya, []), band_index)
            before_rows.append(_preview_cell(ya, b_item))
            after_rows.append(_preview_cell(ya, a_item))
        groups.append(
            {
                "compare_group_id": group_id,
                "band_index": band_index,
                "display_name": display_name,
                "entity_kind": "rate_band",
                "before": before_rows,
                "after": after_rows,
            }
        )
    groups.sort(key=lambda row: (str(row.get("compare_group_id")), int(row.get("band_index") or 0)))
    return groups


def _compile_draft_preview(
    session: Session,
    draft: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    merged_rows = _merge_promoted_rows(session, draft)
    return compile_maps(merged_rows)


def catalog_preview(
    session: Session,
    source_doc_id: str,
    *,
    assessment_year: str | None = None,
    paths: ActAdminPaths | None = None,
) -> dict[str, Any]:
    """Compiled year views as they would appear after activation (accepted rows only).

    When this Act is already live (re-upload / demo), show current year views instead
    of a draft merge that drops this source's promoted rows while accepted_count is 0.
    """
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    job_ctx = _job_context(draft, paths=root, session=session)
    already_in_system = bool(job_ctx.get("already_in_system"))
    live_relief, live_rates = _snapshot_year_views(session)
    if already_in_system:
        draft_relief, draft_rates = live_relief, live_rates
        accepted_count = len(
            [e for e in review_entities(draft) if resolve_engine_scope(e) == "individual"]
        )
    else:
        draft_relief, draft_rates = _compile_draft_preview(session, draft)
        accepted_count = len(_accepted_for_promote(draft, session))
    live_years = sorted(set(live_relief) | set(live_rates))
    preview_years = sorted(set(draft_relief) | set(draft_rates) | set(live_years))
    payload: dict[str, Any] = {
        "source_doc_id": source_doc_id,
        "live_years": live_years,
        "preview_years": preview_years,
        "accepted_count": accepted_count,
        "already_in_system": already_in_system,
    }
    if assessment_year:
        ya = assessment_year.strip()
        relief_rows = live_relief.get(ya, []) if already_in_system else draft_relief.get(ya, [])
        rate_rows = live_rates.get(ya, []) if already_in_system else draft_rates.get(ya, [])
        payload.update(
            {
                "assessment_year": ya,
                "live_reliefs": [present_relief(r) for r in live_relief.get(ya, [])],
                "live_rates": live_rates.get(ya, []),
                "preview_reliefs": [present_relief(r) for r in relief_rows],
                "preview_rates": rate_rows,
                "relief_count": len(relief_rows),
                "band_count": len(rate_rows),
            }
        )
        return payload
    payload["reliefs_by_year"] = draft_relief
    payload["rates_by_year"] = draft_rates
    return payload


def impact_preview(session: Session, source_doc_id: str, *, paths: ActAdminPaths | None = None) -> dict[str, Any]:
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    readiness = review_ready(draft, session=session)
    accepted = _open_top_accepted_rate_bands(_accepted_for_promote(draft, session))
    fingerprint = _entity_fingerprint(accepted)
    before_relief, before_rates = _snapshot_year_views(session)
    after_relief, after_rates = _compile_draft_preview(session, draft)
    relief_impact = _diff_maps(
        before_relief,
        after_relief,
        key_fn=lambda item: str(item.get("compare_group_id") or ""),
    )
    rate_impact = _diff_maps(
        before_rates,
        after_rates,
        key_fn=lambda item: (validate_rate_ladder_key(item), int(item.get("band_index") or 0)),
    )
    relief_group_ids = {
        str(e.get("compare_group_id") or "")
        for e in accepted
        if e.get("entity_kind") == "relief" and str(e.get("compare_group_id") or "")
    }
    accepted_rates = [e for e in accepted if e.get("entity_kind") == "rate_band"]
    groups = _build_relief_groups(before_relief, after_relief, relief_group_ids)
    groups.extend(_build_rate_groups(before_rates, after_rates, accepted_rates))
    affected_years = sorted(
        ya
        for ya in set(before_relief) | set(after_relief)
        if before_relief.get(ya) != after_relief.get(ya) or before_rates.get(ya) != after_rates.get(ya)
    )
    changed_groups = [
        group
        for group in groups
        if any(
            before.get("cap_amount") != after.get("cap_amount")
            or before.get("source_doc_id") != after.get("source_doc_id")
            or before.get("rate_percent") != after.get("rate_percent")
            for before, after in zip(group["before"], group["after"], strict=True)
        )
    ]
    return {
        "source_doc_id": source_doc_id,
        "fingerprint": fingerprint,
        "affected_years": affected_years,
        "impact": {"reliefs": relief_impact, "rates": rate_impact},
        "groups": groups,
        "changed_group_count": len(changed_groups),
        **readiness,
    }


def activate_draft(
    session: Session,
    source_doc_id: str,
    *,
    fingerprint: str,
    reviewer: str,
    paths: ActAdminPaths | None = None,
) -> dict[str, Any]:
    root = paths or act_admin_paths()
    draft = load_draft(source_doc_id, root)
    if draft is None:
        raise FileNotFoundError(f"no draft extract for {source_doc_id}")
    readiness = review_ready(draft, session=session)
    if not readiness["activate_allowed"]:
        raise ReviewValidationError(
            f"activation blocked: pending={readiness['pending_count']} "
            f"issues={readiness['blocking_issue_count']}"
        )
    _apply_prior_to_draft(draft, session)
    # Only accepted rows promote; rejected never enter year views. Open the top
    # accepted band so rejecting a bad top slab does not leave a closed ladder.
    accepted = _open_top_accepted_rate_bands(_accepted_for_promote(draft, session))
    _sync_rate_uppers_into_draft(draft, accepted)
    save_draft(draft, root)
    current_fp = _entity_fingerprint(accepted)
    if current_fp != fingerprint:
        raise ReviewValidationError("Stale impact preview — re-run preview after edits.")
    run = ExtractRun.model_validate(draft)
    try:
        result = promote_act_run(session, run, require_review_accepted=True)
    except ChunkCoverageError as exc:
        raise ReviewValidationError(str(exc)) from exc
    session.flush()
    job_id = str(draft.get("job_id") or "")
    if job_id:
        job = load_job(job_id, root)
        if job is not None:
            job["status"] = "activated"
            job["activated_at"] = now_iso()
            job["activated_by"] = reviewer
            save_job(job, root)
    draft["review_status"] = "activated"
    draft["activated_at"] = now_iso()
    draft["activated_by"] = reviewer
    save_draft(draft, root)
    result["fingerprint"] = current_fp
    result["reviewer"] = reviewer
    return result


def reset_activation(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: ActAdminPaths | None = None,
) -> dict[str, Any]:
    """Clear activate markers so the same draft can be activated again for a demo.

    Does not change row decisions, year_kind, ingest, or extract files.
    """
    root = paths or act_admin_paths()
    sid = (source_doc_id or "").strip()
    draft = load_draft(sid, root)
    job_id = ""
    if draft is not None:
        job_id = str(draft.get("job_id") or "")
        draft.pop("review_status", None)
        draft.pop("activated_at", None)
        draft.pop("activated_by", None)
        save_draft(draft, root)
    if not job_id:
        for job_row in list_jobs(root):
            if str(job_row.get("source_doc_id") or "") == sid:
                job_id = str(job.get("id") or "")
                break
    job = load_job(job_id, root) if job_id else None
    if job is not None and str(job.get("status") or "") == "activated":
        job["status"] = "extracted"
        job.pop("activated_at", None)
        job.pop("activated_by", None)
        job["activation_reset_by"] = reviewer
        job["activation_reset_at"] = now_iso()
        save_job(job, root)
    return {
        "source_doc_id": sid,
        "draft_reset": draft is not None,
        "job_id": job_id or None,
        "job_reset": job is not None,
        "reset_by": reviewer,
        "reset_at": now_iso(),
    }
