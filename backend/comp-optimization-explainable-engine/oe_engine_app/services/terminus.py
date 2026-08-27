"""Tier terminus: Act may promote; Guide and Consolidated must not."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.shared.config.settings import PROJECT_ROOT
from db.models import OeEngineChunk, OeEngineDocument
from db.year_views import OeEnginePromotedEntity, OeEnginePromotedRun
from oe_engine_app.schemas.extract import ExtractRun, terminus_for_tier
from oe_engine_app.services.archive import archive_previous_and_diff
from oe_engine_app.services.compiler import recompile_year_views
from oe_engine_app.services.engine_scope import is_promotable_scope, resolve_engine_scope
from oe_engine_app.services.hash_match import canonical_payload_hash, classify_act_hash
from oe_engine_app.services.mismatch_queue import write_consolidated_facts as _write_facts
from oe_engine_app.services.mismatch_queue import recompare_all_facts

GUIDE_DISPLAY_DIR = PROJECT_ROOT / "models" / "opt-explain-engine" / "extracted" / "guide_display"


class PromoteForbidden(RuntimeError):
    """Guide and Consolidated never promote into year views."""


class ChunkCoverageError(RuntimeError):
    """Act promote requires ingested chunks for that source_doc_id."""


def assert_promote_allowed(tier: str) -> None:
    if tier != "act":
        raise PromoteForbidden(
            f"promote is Act-only; {tier} terminus is {terminus_for_tier(tier)}"
        )


def _included_entities(
    run: ExtractRun,
    *,
    require_review_accepted: bool = False,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entity in run.entities:
        if entity.get("entity_kind") not in {"relief", "rate_band"}:
            continue
        if entity.get("included") is False:
            continue
        if require_review_accepted and str(entity.get("review_status") or "pending") != "accepted":
            continue
        if entity.get("change_action") == "repeal":
            payload = dict(entity)
            payload["engine_scope"] = resolve_engine_scope(entity)
            out.append(payload)
            continue
        if not is_promotable_scope(entity):
            continue
        payload = dict(entity)
        payload["engine_scope"] = resolve_engine_scope(entity)
        out.append(payload)
    return out


def promote_act_run(
    session: Session,
    run: ExtractRun,
    *,
    require_review_accepted: bool = False,
) -> dict[str, Any]:
    assert_promote_allowed(run.tier)
    chunk_count = (
        session.query(OeEngineChunk)
        .filter(OeEngineChunk.source_doc_id == run.source_doc_id)
        .count()
    )
    if chunk_count < 1:
        raise ChunkCoverageError(
            f"promote rejected: no chunks for {run.source_doc_id} (ingest first)"
        )
    entities = _included_entities(run, require_review_accepted=require_review_accepted)
    if require_review_accepted and not entities:
        raise PromoteForbidden(
            "activation requires at least one accepted relief or rate band row"
        )
    excluded_other = sum(
        1
        for entity in run.entities
        if entity.get("entity_kind") in {"relief", "rate_band"}
        and entity.get("included") is not False
        and not is_promotable_scope(entity)
    )
    new_hash = canonical_payload_hash(entities)
    existing = session.get(OeEnginePromotedRun, run.source_doc_id)
    branch = classify_act_hash(
        existing_hash=None if existing is None else existing.payload_hash,
        new_hash=new_hash,
    )
    diff = archive_previous_and_diff(run.model_dump(mode="json"))
    if branch == "identical":
        # Skip entity rewrite, but still compile year views (empty views after a
        # prior autoflush miss, or a teammate's POST /index/refresh equivalent).
        recompile_year_views(session, persist=True)
        flags = recompare_all_facts(session)
        return {
            "terminus": run.terminus,
            "branch": branch,
            "source_doc_id": run.source_doc_id,
            "extraction_run_id": run.extraction_run_id,
            "payload_hash": new_hash,
            "chunk_count": chunk_count,
            "reextract_diff": diff,
            "mismatch_flags_touched": flags,
            "skipped": True,
            "entity_count": len(entities),
            "excluded_other_scope": excluded_other,
        }

    session.query(OeEnginePromotedEntity).filter(
        OeEnginePromotedEntity.source_doc_id == run.source_doc_id
    ).delete(synchronize_session=False)
    now = datetime.now(timezone.utc)
    for entity in entities:
        payload = dict(entity)
        payload["extraction_run_id"] = run.extraction_run_id
        session.add(
            OeEnginePromotedEntity(
                source_doc_id=run.source_doc_id,
                extraction_run_id=run.extraction_run_id,
                entity_kind=str(entity.get("entity_kind") or ""),
                compare_group_id=str(entity.get("compare_group_id") or ""),
                entry_id=str(entity.get("entry_id") or ""),
                payload_json=payload,
                payload_hash=new_hash,
                promoted_at=now,
            )
        )
    if existing is None:
        session.add(
            OeEnginePromotedRun(
                source_doc_id=run.source_doc_id,
                extraction_run_id=run.extraction_run_id,
                payload_hash=new_hash,
                branch=branch,
                promoted_at=now,
            )
        )
    else:
        existing.extraction_run_id = run.extraction_run_id
        existing.payload_hash = new_hash
        existing.branch = branch
        existing.promoted_at = now

    session.flush()
    recompile_year_views(session, persist=True)
    flags = recompare_all_facts(session)
    return {
        "terminus": run.terminus,
        "branch": branch,
        "source_doc_id": run.source_doc_id,
        "extraction_run_id": run.extraction_run_id,
        "payload_hash": new_hash,
        "chunk_count": chunk_count,
        "entity_count": len(entities),
        "excluded_other_scope": excluded_other,
        "mismatch_flags_touched": flags,
        "reextract_diff": diff,
        "skipped": False,
    }


def unpromote_source_doc(session: Session, source_doc_id: str) -> dict[str, Any]:
    """Drop one Act's promoted rows and recompile. Ingest, extract, and drafts stay."""
    sid = (source_doc_id or "").strip()
    if not sid:
        raise ValueError("source_doc_id is required")
    removed_entities = (
        session.query(OeEnginePromotedEntity)
        .filter(OeEnginePromotedEntity.source_doc_id == sid)
        .delete(synchronize_session=False)
    )
    run = session.get(OeEnginePromotedRun, sid)
    had_run = run is not None
    if run is not None:
        session.delete(run)
    session.flush()
    recompile_year_views(session, persist=True)
    flags = recompare_all_facts(session)
    return {
        "source_doc_id": sid,
        "removed_entities": int(removed_entities or 0),
        "removed_run": had_run,
        "mismatch_flags_touched": flags,
    }


def _diff_keys(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    keys = set(old) | set(new)
    for key in sorted(keys):
        if old.get(key) != new.get(key):
            changed.append(key)
    return changed


def update_guide_display(run: ExtractRun) -> dict[str, Any]:
    """Write/update Guide display JSON. Re-extract diffs set needs_update.

    Live interview text is ``entities``. A later extract writes ``pending_entities``
    and does not swap interview notes until ``accept_guide_display`` (Update display).
    """
    GUIDE_DISPLAY_DIR.mkdir(parents=True, exist_ok=True)
    path = GUIDE_DISPLAY_DIR / f"{run.source_doc_id}.json"
    incoming_entities = [e for e in run.entities if e.get("included") is not False]
    previous: dict[str, Any] | None = None
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            previous = loaded
    if previous is None:
        incoming = {
            "source_doc_id": run.source_doc_id,
            "extraction_run_id": run.extraction_run_id,
            "review_status": "pending",
            "entities": incoming_entities,
        }
        path.write_text(json.dumps(incoming, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"path": str(path), "review_status": incoming["review_status"]}

    old_ids = {
        e.get("entry_id"): e for e in previous.get("entities") or [] if e.get("entry_id")
    }
    new_ids = {e.get("entry_id"): e for e in incoming_entities if e.get("entry_id")}
    diffs: list[dict[str, Any]] = []
    for eid, new in new_ids.items():
        old = old_ids.get(eid)
        if old is None:
            diffs.append({"entry_id": eid, "change": "added"})
            continue
        changed = _diff_keys(old, new)
        if changed:
            diffs.append({"entry_id": eid, "change": "updated", "fields": changed})
    for eid in old_ids:
        if eid not in new_ids:
            diffs.append({"entry_id": eid, "change": "removed"})
    incoming = dict(previous)
    incoming["source_doc_id"] = run.source_doc_id
    incoming["pending_entities"] = incoming_entities
    incoming["pending_extraction_run_id"] = run.extraction_run_id
    incoming["previous_extraction_run_id"] = previous.get("extraction_run_id")
    incoming["reextract_diff"] = diffs
    if diffs:
        incoming["review_status"] = "needs_update"
    path.write_text(json.dumps(incoming, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "review_status": incoming["review_status"]}


def write_consolidated_facts(session: Session, run: ExtractRun) -> dict[str, Any]:
    return _write_facts(session, run)


def apply_extract_terminus(session: Session, run: ExtractRun) -> dict[str, Any]:
    if run.tier == "act":
        return {"terminus": run.terminus, "promote": "pending_review"}
    if run.tier == "guide":
        display = update_guide_display(run)
        return {"terminus": run.terminus, "guide_display": display}
    if run.tier == "consolidated":
        facts = write_consolidated_facts(session, run)
        return {"terminus": run.terminus, "consolidated": facts}
    raise ValueError(f"unknown tier {run.tier}")


def document_tier(session: Session, source_doc_id: str) -> str:
    doc = session.get(OeEngineDocument, source_doc_id)
    if doc is None:
        raise ValueError(f"unknown source_doc_id: {source_doc_id}")
    return doc.tier


def guide_display_path(source_doc_id: str) -> Path:
    return GUIDE_DISPLAY_DIR / f"{source_doc_id}.json"


def list_guide_displays() -> list[dict[str, Any]]:
    GUIDE_DISPLAY_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(GUIDE_DISPLAY_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "source_doc_id": payload.get("source_doc_id") or path.stem,
                "extraction_run_id": payload.get("extraction_run_id"),
                "review_status": payload.get("review_status"),
                "entity_count": len(payload.get("entities") or []),
                "path": str(path),
            }
        )
    return rows


def load_guide_display(source_doc_id: str) -> dict[str, Any]:
    path = guide_display_path(source_doc_id)
    if not path.is_file():
        raise FileNotFoundError(f"no Guide display for {source_doc_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"no Guide display for {source_doc_id}")
    return payload


def accept_guide_display(source_doc_id: str) -> dict[str, Any]:
    """Update display: promote pending extract into interview notes (never year tables)."""
    payload = load_guide_display(source_doc_id)
    pending = payload.get("pending_entities")
    if isinstance(pending, list) and pending:
        payload["entities"] = pending
        payload["extraction_run_id"] = (
            payload.get("pending_extraction_run_id") or payload.get("extraction_run_id")
        )
        payload.pop("pending_entities", None)
        payload.pop("pending_extraction_run_id", None)
    payload["review_status"] = "accepted"
    path = guide_display_path(source_doc_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "review_status": "accepted", "source_doc_id": source_doc_id}


def guide_notes_for(compare_group_id: str | None = None) -> list[dict[str, Any]]:
    wanted = (compare_group_id or "").strip() or None
    notes: list[dict[str, Any]] = []
    GUIDE_DISPLAY_DIR.mkdir(parents=True, exist_ok=True)
    payloads: list[dict[str, Any]] = []
    for path in sorted(GUIDE_DISPLAY_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    if not payloads:
        from oe_engine_app.services.fixtures import load_extract_fixture

        try:
            run = load_extract_fixture("guide_extract.json")
        except FileNotFoundError:
            run = None
        if run is not None:
            payloads.append(run.model_dump(mode="json"))
    for payload in payloads:
        for entity in payload.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            if entity.get("included") is False:
                continue
            group = str(entity.get("compare_group_id") or "")
            if wanted and group != wanted:
                continue
            notes.append(
                {
                    "source_label": "Guide",
                    "source_doc_id": payload.get("source_doc_id"),
                    "compare_group_id": group,
                    "display_name": entity.get("display_name"),
                    "help": entity.get("help")
                    or (entity.get("eligibility") or {}).get("text"),
                    "eligibility": entity.get("eligibility"),
                    "required_evidence": entity.get("required_evidence") or [],
                    "quote": entity.get("quote") or "",
                    "review_status": payload.get("review_status") or "pending",
                }
            )
    return notes
