"""Catalog-admin Step 4: harvest_act on this PDF only, then per-row suggestions.

Suggestions are never a selected decision. Humans set ``kind_human``.
Never overwrites ``harvest/commencement_records.json``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

from adaptive_tax_app.services.catalog_admin_store import (
    APPROVED_DIR,
    HARVEST_CORPUS_JSON,
    CatalogAdminPaths,
    catalog_admin_paths,
    load_job,
    now_iso,
)
from adaptive_tax_app.services.catalog_duplicate import CatalogDuplicateError, _load_module
from adaptive_tax_app.services.catalog_stage import (
    apply_staging_schema,
    copy_human_attribution,
    ensure_provision_attribution,
    save_staged_proposal,
)
from backend.shared.config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

PHASE1_SCRIPT = PROJECT_ROOT / "scripts" / "relief_interview_phase1_commencement.py"
HARVEST_MAX_PAGES = 16
KIND_HUMAN_VALUES = frozenset({"UPDATE", "NEW_YEAR"})
_BLANKET_KINDS = ("whole_act", "short_title_clause", "table_blanket")
_SECTION_NUM_RE = re.compile(r"\d+")
_YA_STEM_RE = re.compile(r"^\d{4}_\d{2}$")

HarvestFn = Callable[..., Any]
harvest_act_impl: HarvestFn | None = None


def p1() -> Any:
    return _load_module(PHASE1_SCRIPT, "relief_interview_phase1_commencement")


def _harvest_act(source_doc_id: str, pdf_path: Path, max_pages: int) -> Any:
    fn = harvest_act_impl
    if fn is not None:
        return fn(source_doc_id, pdf_path, max_pages)
    return p1().harvest_act(source_doc_id, pdf_path, max_pages=max_pages)


def live_confirmed_yas() -> list[str]:
    """YAs with an ``approved/{ya}.json`` that are in the live confirmed set."""
    max_ya = str(p1().MAX_IN_SCOPE_YA)
    if not APPROVED_DIR.is_dir():
        return []
    yas: list[str] = []
    for path in APPROVED_DIR.glob("*.json"):
        ya = path.stem
        if _YA_STEM_RE.fullmatch(ya) and ya <= max_ya:
            yas.append(ya)
    return sorted(yas)


def _norm_ref(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip().lower())
    text = text.replace("section ", "s.")
    return text


def _record_dict(rec: Any) -> dict[str, Any]:
    if hasattr(rec, "__dataclass_fields__"):
        return asdict(rec)
    if isinstance(rec, dict):
        return dict(rec)
    return {
        "source_doc_id": getattr(rec, "source_doc_id", ""),
        "act_title_hint": getattr(rec, "act_title_hint", ""),
        "section_ref": getattr(rec, "section_ref", ""),
        "operation_date": getattr(rec, "operation_date", ""),
        "derived_assessment_year": getattr(rec, "derived_assessment_year", ""),
        "quote": getattr(rec, "quote", ""),
        "parse_kind": getattr(rec, "parse_kind", ""),
    }


def harvest_as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        records = [_record_dict(r) for r in (raw.get("records") or [])]
        return {
            "source_doc_id": raw.get("source_doc_id") or "",
            "file_name": raw.get("file_name") or "",
            "pages_scanned": int(raw.get("pages_scanned") or 0),
            "notes": list(raw.get("notes") or []),
            "records": records,
        }
    records = [_record_dict(r) for r in (getattr(raw, "records", None) or [])]
    return {
        "source_doc_id": getattr(raw, "source_doc_id", "") or "",
        "file_name": getattr(raw, "file_name", "") or "",
        "pages_scanned": int(getattr(raw, "pages_scanned", 0) or 0),
        "notes": list(getattr(raw, "notes", None) or []),
        "records": records,
    }


def parse_operation_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    mod = p1()
    dotted = mod.parse_dotted_date(text)
    if dotted is not None:
        return dotted
    return mod.parse_month_name_date(text)


def _match_score(section_ref: str, record: dict[str, Any]) -> int:
    needle = _norm_ref(section_ref)
    hay = _norm_ref(str(record.get("section_ref") or ""))
    if not needle or not hay:
        return 0
    if needle == hay or needle in hay or hay in needle:
        return 3
    nums_n = set(_SECTION_NUM_RE.findall(needle))
    nums_h = set(_SECTION_NUM_RE.findall(hay))
    if nums_n and nums_n & nums_h:
        return 2
    return 0


def match_harvest_record(section_ref: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Column III / section_ref first; otherwise a blanket commencement clause."""
    if not records:
        return None
    column = [r for r in records if r.get("parse_kind") == "column_iii_row"]
    scored = sorted(column, key=lambda r: _match_score(section_ref, r), reverse=True)
    if scored and _match_score(section_ref, scored[0]) > 0:
        return scored[0]
    others = [r for r in records if r.get("parse_kind") != "column_iii_row"]
    scored_o = sorted(others, key=lambda r: _match_score(section_ref, r), reverse=True)
    if scored_o and _match_score(section_ref, scored_o[0]) > 0:
        return scored_o[0]
    by_kind = {str(r.get("parse_kind") or ""): r for r in records}
    for kind in _BLANKET_KINDS:
        if kind in by_kind:
            return by_kind[kind]
    return None


def suggest_kind(derived_ya: str | None, live_yas: set[str], max_in_scope_ya: str) -> str | None:
    if not derived_ya:
        return None
    if derived_ya in live_yas and derived_ya <= max_in_scope_ya:
        return "UPDATE"
    return "NEW_YEAR"


def included_rows(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(proposal.get("rows") or [])
    if rows:
        return [r for r in rows if r.get("included")]
    out: list[dict[str, Any]] = []
    for section in proposal.get("sections") or []:
        for row in section.get("rows") or []:
            if row.get("included"):
                out.append(row)
    return out


def suggest_provision(
    row: dict[str, Any],
    *,
    harvest_records: list[dict[str, Any]],
    live_yas: set[str],
    max_in_scope_ya: str,
) -> dict[str, Any]:
    """One included row → suggestion only. ``kind_human`` stays unset."""
    row_id = str(row.get("entry_id") or row.get("row_id") or "")
    section_ref = str(row.get("section_ref") or "")
    row_quote = str(row.get("quote") or "")
    effective_raw = str(row.get("effective_from") or "").strip()
    op = parse_operation_date(effective_raw)
    parse_kind = None
    commencement_quote = row_quote
    commencement_section = section_ref
    operation_date = None
    derived_ya = None
    note = None

    if op is not None:
        parse_kind = "row_effective_from"
        operation_date = op.isoformat()
        derived_ya = p1().ya_for_operation_date(op)
        commencement_quote = row_quote or effective_raw
    else:
        matched = match_harvest_record(section_ref, harvest_records)
        if matched is not None:
            parse_kind = str(matched.get("parse_kind") or "") or None
            commencement_quote = str(matched.get("quote") or row_quote)
            commencement_section = str(matched.get("section_ref") or section_ref)
            operation_date = str(matched.get("operation_date") or "") or None
            derived_ya = str(matched.get("derived_assessment_year") or "") or None
            if not derived_ya and operation_date:
                parsed = parse_operation_date(operation_date)
                if parsed is not None:
                    derived_ya = p1().ya_for_operation_date(parsed)
        else:
            note = (
                "No row effective_from and no matching harvest record. "
                "Classify from the row quote."
            )

    payload = {
        "row_id": row_id,
        "display_name": row.get("display_name") or row.get("band_label") or "",
        "row_kind": row.get("row_kind") or "",
        "section_ref": section_ref,
        "row_quote": row_quote,
        "kind_suggested": suggest_kind(derived_ya, live_yas, max_in_scope_ya),
        "kind_human": None,
        "kind_set_by": None,
        "kind_set_at": None,
        "derived_assessment_year": derived_ya,
        "effective_from": effective_raw or operation_date,
        "operation_date": operation_date,
        "commencement_quote": commencement_quote,
        "commencement_parse_kind": parse_kind,
        "commencement_section_ref": commencement_section,
        "note": note,
    }
    return ensure_provision_attribution(payload)


def _write_harvest_sidecar(
    harvest: dict[str, Any],
    *,
    source_doc_id: str,
    paths: CatalogAdminPaths,
) -> str:
    paths.harvest_sidecar_dir.mkdir(parents=True, exist_ok=True)
    path = paths.harvest_sidecar_dir / f"{source_doc_id}.json"
    payload = {
        "spec_version": "1.0.0",
        "note": (
            "Catalog-admin sidecar for Rule 2 in-memory merge. "
            "Does not replace harvest/commencement_records.json."
        ),
        "written_at": now_iso(),
        **harvest,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path.as_posix()


def run_harvest(
    *,
    source_doc_id: str,
    pdf_path: Path,
    paths: CatalogAdminPaths,
) -> dict[str, Any]:
    """Call harvest_act on this PDF only. Never writes the Phase 1 corpus harvest file."""
    try:
        raw = _harvest_act(source_doc_id, pdf_path, HARVEST_MAX_PAGES)
        harvest = harvest_as_dict(raw)
    except Exception as exc:  # noqa: BLE001 — empty harvest is a warning, not a crash
        logger.exception("harvest_act failed for %s", source_doc_id)
        harvest = {
            "source_doc_id": source_doc_id,
            "file_name": pdf_path.name,
            "pages_scanned": 0,
            "notes": [f"harvest_act failed: {exc}"],
            "records": [],
        }
    if not harvest["records"] and not any(
        "No commencement" in n for n in harvest["notes"]
    ):
        harvest["notes"].append("No commencement / Column III dates recovered in scanned pages.")
    harvest["corpus_harvest_path"] = HARVEST_CORPUS_JSON.as_posix()
    harvest["corpus_harvest_written"] = False
    harvest["sidecar_path"] = _write_harvest_sidecar(
        harvest, source_doc_id=source_doc_id, paths=paths
    )
    return harvest


def attach_classification(
    proposal: dict[str, Any],
    *,
    pdf_path: Path,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Add ``classification`` with suggestions only. Does not set ``kind_human``."""
    root = paths or catalog_admin_paths()
    sid = str(proposal.get("source_doc_id") or "")
    harvest = run_harvest(source_doc_id=sid, pdf_path=pdf_path, paths=root)
    live = live_confirmed_yas()
    live_set = set(live)
    max_ya = str(p1().MAX_IN_SCOPE_YA)
    provisions = [
        suggest_provision(
            row,
            harvest_records=harvest["records"],
            live_yas=live_set,
            max_in_scope_ya=max_ya,
        )
        for row in included_rows(proposal)
    ]
    proposal["classification"] = {
        "status": "pending_human",
        "pages_scanned": harvest["pages_scanned"],
        "harvest_notes": harvest["notes"],
        "harvest_record_count": len(harvest["records"]),
        "harvest_sidecar": harvest.get("sidecar_path"),
        "corpus_harvest_written": False,
        "live_confirmed_yas": live,
        "max_in_scope_ya": max_ya,
        "provisions": provisions,
    }
    apply_staging_schema(proposal)
    return proposal


def load_proposed(
    source_doc_id: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    root = paths or catalog_admin_paths()
    path = root.proposed_dir / f"{source_doc_id}.json"
    if not path.is_file():
        raise CatalogDuplicateError(f"Proposal {source_doc_id} not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_proposed(
    proposal: dict[str, Any],
    paths: CatalogAdminPaths | None = None,
) -> Path:
    """Stage via Phase 6 save_proposed (proposed/ only)."""
    return save_staged_proposal(proposal, paths)


def unset_row_ids(proposal: dict[str, Any]) -> list[str]:
    provisions = (proposal.get("classification") or {}).get("provisions") or []
    return [
        str(p.get("row_id") or "")
        for p in provisions
        if p.get("kind_human") not in KIND_HUMAN_VALUES
    ]


def classification_complete(proposal: dict[str, Any]) -> bool:
    block = proposal.get("classification") or {}
    provisions = block.get("provisions")
    if provisions is None:
        return False
    if not provisions:
        return True
    return not unset_row_ids(proposal)


def proposal_review_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    unset = unset_row_ids(proposal)
    complete = classification_complete(proposal)
    reason = None
    if proposal.get("classification") is None:
        reason = "This proposal has no classification block. Re-extract to classify."
    elif not complete:
        reason = (
            "Promote is disabled until every included row has a human classification "
            "(UPDATE or NEW_YEAR). Suggestions are not selected."
        )
    else:
        reason = "Classification is complete. Promote lands in a later step."
    return {
        "source_doc_id": proposal.get("source_doc_id"),
        "proposal": proposal,
        "classification_complete": complete and proposal.get("classification") is not None,
        "unset_row_ids": unset,
        "promote_enabled": False,
        "promote_blocked_reason": reason,
    }


def set_kind_human(
    source_doc_id: str,
    *,
    row_id: str,
    kind_human: str,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Write ``kind_human`` / ``kind_set_by`` / ``kind_set_at`` only for that provision."""
    kind = (kind_human or "").strip().upper()
    if kind not in KIND_HUMAN_VALUES:
        raise CatalogDuplicateError("kind_human must be UPDATE or NEW_YEAR.")
    rid = (row_id or "").strip()
    if not rid:
        raise CatalogDuplicateError("row_id is required.")
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    block = proposal.get("classification")
    if not isinstance(block, dict) or not isinstance(block.get("provisions"), list):
        raise CatalogDuplicateError("This proposal has no classification block. Re-extract to classify.")
    matched = None
    for provision in block["provisions"]:
        if str(provision.get("row_id") or "") == rid:
            matched = provision
            break
    if matched is None:
        raise CatalogDuplicateError(f"Row {rid} is not an included classified provision.")
    matched["kind_human"] = kind
    matched["kind_set_by"] = reviewer
    matched["kind_set_at"] = now_iso()
    block["status"] = "complete" if classification_complete(proposal) else "pending_human"
    save_proposed(proposal, root)
    return proposal_review_payload(proposal)


def _proposal_pdf_path(proposal: dict[str, Any], paths: CatalogAdminPaths) -> Path:
    job_id = str(proposal.get("job_id") or "")
    if job_id:
        job = load_job(job_id, paths)
        raw = (job or {}).get("storage_path") or ""
        stored = Path(raw) if raw else None
        if stored is not None and stored.is_file():
            return stored
    for key in ("pdf_path", "storage_path"):
        raw = str(proposal.get(key) or "")
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.is_file():
            return path
    raise CatalogDuplicateError(
        "Uploaded PDF is missing; cannot harvest this proposal. Upload again."
    )


def refresh_classification(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Run harvest_act on the stored PDF and attach suggestions. Keeps existing kind_human."""
    root = paths or catalog_admin_paths()
    proposal = load_proposed(source_doc_id, root)
    pdf_path = _proposal_pdf_path(proposal, root)
    prior = {
        str(p.get("row_id") or ""): p
        for p in ((proposal.get("classification") or {}).get("provisions") or [])
    }
    attach_classification(proposal, pdf_path=pdf_path, paths=root)
    for provision in proposal["classification"]["provisions"]:
        old = prior.get(str(provision.get("row_id") or ""))
        if old:
            copy_human_attribution(old, provision)
    proposal["classification"]["status"] = (
        "complete" if classification_complete(proposal) else "pending_human"
    )
    proposal["classification"]["harvest_run_by"] = reviewer
    proposal["classification"]["harvest_run_at"] = now_iso()
    save_proposed(proposal, root)
    return proposal_review_payload(proposal)
