"""Catalog-admin Step 3: background extract_proposal (no forked quote gate)."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from adaptive_tax_app.services.catalog_admin_store import (
    CatalogAdminPaths,
    catalog_admin_paths,
    job_path,
    list_jobs,
    load_job,
    now_iso,
    save_job,
)
from adaptive_tax_app.services.catalog_classify import attach_classification
from adaptive_tax_app.services.catalog_duplicate import CatalogDuplicateError, p6
from adaptive_tax_app.services.catalog_stage import apply_staging_schema, save_staged_proposal

logger = logging.getLogger(__name__)

WATCHER_MODEL = "gpt-4o"
WATCHER_MAX_CALLS = 80

ExtractFn = Callable[..., dict[str, Any]]
extract_proposal_impl: ExtractFn | None = None

_THREADS: dict[str, threading.Thread] = {}
_START_LOCK = threading.Lock()


def _extract_proposal(**kwargs: Any) -> dict[str, Any]:
    fn = extract_proposal_impl
    if fn is not None:
        return fn(**kwargs)
    return p6().extract_proposal(**kwargs)


def _pdf_path(job: dict[str, Any]) -> Path:
    raw = job.get("storage_path") or ""
    path = Path(raw)
    if not path.is_file():
        raise CatalogDuplicateError("Uploaded PDF is missing; cannot extract.")
    return path


def _proposed_paths_for_sid(source_doc_id: str, paths: CatalogAdminPaths) -> list[Path]:
    sid = (source_doc_id or "").strip()
    if not sid or not paths.proposed_dir.is_dir():
        return []
    found: list[Path] = []
    exact = paths.proposed_dir / f"{sid}.json"
    if exact.is_file():
        found.append(exact)
    for path in sorted(paths.proposed_dir.glob("*.json")):
        if path in found:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("source_doc_id") or "") == sid:
            found.append(path)
    return found


def cleanup_extract_artifacts(source_doc_id: str, paths: CatalogAdminPaths) -> None:
    """Retry must not leave half-written extracted/ or proposed/ files."""
    sid = (source_doc_id or "").strip()
    if not sid:
        return
    if paths.extracted_dir.is_dir():
        for leftover in paths.extracted_dir.glob(f"{sid}__*.json"):
            leftover.unlink(missing_ok=True)
    for proposed in _proposed_paths_for_sid(sid, paths):
        proposed.unlink(missing_ok=True)


def _write_extracted_sections(
    proposal: dict[str, Any],
    *,
    pdf_name: str,
    paths: CatalogAdminPaths,
) -> list[str]:
    """Write section staging JSON only after the full extract_proposal return."""
    sid = str(proposal["source_doc_id"])
    paths.extracted_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for section in proposal.get("sections") or []:
        if section.get("status") != "ok":
            continue
        key = str(section.get("section_key") or "section")
        safe_key = key.replace(" ", "_").lower()
        out_path = paths.extracted_dir / f"{sid}__{safe_key}.json"
        rows = list(section.get("rows") or [])
        staging = {
            "spec_version": "1.0.0",
            "run_id": proposal.get("run_id"),
            "model": proposal.get("model"),
            "temperature": proposal.get("temperature", 0),
            "source_doc_id": sid,
            "act_title": proposal.get("act_title"),
            "pdf_file_name": pdf_name,
            "section_key": key,
            "focus_chars": section.get("focus_chars"),
            "focus_prose": section.get("focus_prose"),
            "extracted_at": proposal.get("extracted_at"),
            "row_count": section.get("row_count", len(rows)),
            "included_count": section.get("included_count", 0),
            "rows": rows,
            "note": "Staging only. Never promoted without Phase 5 human review.",
        }
        out_path.write_text(
            json.dumps(staging, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(out_path.name)
    return written


def _act_title(job: dict[str, Any]) -> str:
    identity = job.get("act_identity") or {}
    label = str(identity.get("label") or "").strip()
    if label:
        return label
    return str(job.get("original_filename") or job.get("source_doc_id") or "Act")


def _fail_job(job: dict[str, Any], *, error: str, paths: CatalogAdminPaths) -> dict[str, Any]:
    sid = str(job.get("source_doc_id") or "")
    cleanup_extract_artifacts(sid, paths)
    job["status"] = "failed"
    job["error"] = error
    job["failed_at"] = now_iso()
    job["extract_finished_at"] = job["failed_at"]
    save_job(job, paths)
    return job


def run_extract_job(job_id: str, *, paths: CatalogAdminPaths | None = None) -> dict[str, Any]:
    """Synchronous extract body (used by the worker thread and tests)."""
    root = paths or catalog_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise CatalogDuplicateError(f"Job {job_id} not found.")
    sid = str(job.get("source_doc_id") or "").strip()
    try:
        pdf_path = _pdf_path(job)
        cleanup_extract_artifacts(sid, root)
        proposal = _extract_proposal(
            source_doc_id=sid,
            act_title=_act_title(job),
            pdf_path=pdf_path,
            model=WATCHER_MODEL,
            max_calls=WATCHER_MAX_CALLS,
            dry_run=False,
            only_sections=None,
        )
        proposal["text_sha256"] = job.get("text_sha256")
        proposal["tables_sha256"] = job.get("tables_sha256")
        proposal["act_identity"] = job.get("act_identity")
        proposal["job_id"] = job_id
        proposal["duplicate_check"] = {
            "outcome": "clear",
            "corpus_hit": job.get("matched_source_doc_id"),
            "proposed_hit": None,
        }
        attach_classification(proposal, pdf_path=pdf_path, paths=root)
        apply_staging_schema(proposal, job=job)
        written = _write_extracted_sections(
            proposal,
            pdf_name=str(job.get("original_filename") or pdf_path.name),
            paths=root,
        )
        proposed_path = save_staged_proposal(proposal, root)
        job["status"] = "extracted"
        job["error"] = None
        job["extract_finished_at"] = now_iso()
        job["included_count"] = proposal.get("included_count", 0)
        job["row_count"] = proposal.get("row_count", 0)
        job["extracted_sections"] = written
        job["proposed_path"] = proposed_path.as_posix()
        job["review_path"] = f"/adaptive-tax/catalog-admin/review/{sid}"
        save_job(job, root)
        return job
    except (Exception, SystemExit) as exc:
        logger.exception("Catalog-admin extract failed for job %s", job_id)
        return _fail_job(job, error=str(exc) or exc.__class__.__name__, paths=root)


def _spawn(job_id: str) -> None:
    thread = threading.Thread(
        target=run_extract_job,
        kwargs={"job_id": job_id},
        name=f"catalog-admin-extract-{job_id[:8]}",
        daemon=True,
    )
    _THREADS[job_id] = thread
    thread.start()


def resume_interrupted_extracts(paths: CatalogAdminPaths | None = None) -> list[str]:
    """Re-spawn extract threads lost to uvicorn reload or process restart."""
    root = paths or catalog_admin_paths()
    resumed: list[str] = []
    for job in list_jobs(root):
        if str(job.get("status") or "") != "extracting":
            continue
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        thread = _THREADS.get(job_id)
        if thread is not None and thread.is_alive():
            continue
        logger.info("Resuming interrupted catalog-admin extract for job %s", job_id)
        _spawn(job_id)
        resumed.append(job_id)
    return resumed


def join_extract(job_id: str, timeout: float = 30.0) -> None:
    thread = _THREADS.get(job_id)
    if thread is not None:
        thread.join(timeout=timeout)


def start_extract(
    job_id: str,
    *,
    reviewer: str,
    retry: bool = False,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Mark extracting and return immediately. LLM work runs in a background thread."""
    root = paths or catalog_admin_paths()
    with _START_LOCK:
        job = load_job(job_id, root)
        if job is None:
            raise CatalogDuplicateError(f"Job {job_id} not found.")
        status = str(job.get("status") or "")
        if status == "extracting":
            raise CatalogDuplicateError("Extraction already running for this job.")
        if status == "extracted":
            raise CatalogDuplicateError("This job already extracted. Open the review queue.")
        if status == "paused_rescan":
            raise CatalogDuplicateError(
                "Re-scan is paused. Cancel, or treat as a new source, before extract."
            )
        if status == "discarded":
            raise CatalogDuplicateError("This job was discarded. Upload the PDF again.")
        if retry:
            if status != "failed":
                raise CatalogDuplicateError("Retry is only for failed jobs.")
        elif status != "uploaded":
            raise CatalogDuplicateError("Extract starts only after a clear duplicate check (uploaded).")
        sid = str(job.get("source_doc_id") or "").strip()
        if not sid:
            raise CatalogDuplicateError("Set source_doc_id before extract.")
        _pdf_path(job)
        cleanup_extract_artifacts(sid, root)
        job["status"] = "extracting"
        job["error"] = None
        job["extract_started_at"] = now_iso()
        job["extract_started_by"] = reviewer
        if retry:
            job["retried_at"] = job["extract_started_at"]
            job["retried_by"] = reviewer
        save_job(job, root)
    _spawn(job_id)
    return job


def delete_job(
    job_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Remove job record + uploaded PDF only. Does not touch approved/ or rates/."""
    root = paths or catalog_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise CatalogDuplicateError(f"Job {job_id} not found.")
    status = str(job.get("status") or "")
    if status in {"extracting", "extracted"}:
        raise CatalogDuplicateError("Cannot delete an in-flight or completed extract.")
    sid = str(job.get("source_doc_id") or "")
    cleanup_extract_artifacts(sid, root)
    storage = job.get("storage_path")
    if storage:
        Path(storage).unlink(missing_ok=True)
    job_path(job_id, root).unlink(missing_ok=True)
    return {
        "id": job_id,
        "status": "deleted",
        "deleted_by": reviewer,
        "deleted_at": now_iso(),
    }


def _purge_ledger_decisions(source_doc_id: str, paths: CatalogAdminPaths) -> int:
    ledger_path = paths.ledger_path
    if not ledger_path.is_file():
        return 0
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    decisions = data.get("decisions") or {}
    removed_keys = [
        key
        for key, value in decisions.items()
        if str(value.get("source_doc_id") or "") == source_doc_id
    ]
    for key in removed_keys:
        del decisions[key]
    for block in data.get("superseded_decisions") or []:
        block_decisions = block.get("decisions") or {}
        for key in list(block_decisions.keys()):
            if str(block_decisions[key].get("source_doc_id") or "") == source_doc_id:
                del block_decisions[key]
    ledger_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(removed_keys)


def remove_proposal(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: CatalogAdminPaths | None = None,
) -> dict[str, Any]:
    """Drop a finished extract from the review queue (staging only; never approved/ or rates/)."""
    root = paths or catalog_admin_paths()
    sid = (source_doc_id or "").strip()
    if not sid:
        raise CatalogDuplicateError("source_doc_id is required.")

    proposed_paths = _proposed_paths_for_sid(sid, root)
    extracted_paths = (
        list(root.extracted_dir.glob(f"{sid}__*.json")) if root.extracted_dir.is_dir() else []
    )
    sidecar_paths = (
        list(root.harvest_sidecar_dir.glob(f"{sid}*.json"))
        if root.harvest_sidecar_dir.is_dir()
        else []
    )
    matching_jobs = [job for job in list_jobs(root) if str(job.get("source_doc_id") or "") == sid]

    if not proposed_paths and not extracted_paths and not matching_jobs:
        raise CatalogDuplicateError(f"No queue entry found for {sid}.")

    for job in matching_jobs:
        if str(job.get("status") or "") == "extracting":
            raise CatalogDuplicateError("Cannot remove while extract is still running.")

    removed_jobs: list[str] = []
    for job in matching_jobs:
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        storage = job.get("storage_path")
        if storage:
            Path(storage).unlink(missing_ok=True)
        job_path(job_id, root).unlink(missing_ok=True)
        removed_jobs.append(job_id)

    for path in proposed_paths:
        path.unlink(missing_ok=True)
    for path in extracted_paths:
        path.unlink(missing_ok=True)
    for path in sidecar_paths:
        path.unlink(missing_ok=True)

    removed_decisions = _purge_ledger_decisions(sid, root)

    return {
        "source_doc_id": sid,
        "status": "removed",
        "removed_by": reviewer,
        "removed_at": now_iso(),
        "removed_proposed": [p.name for p in proposed_paths],
        "removed_extracted": [p.name for p in extracted_paths],
        "removed_jobs": removed_jobs,
        "removed_decisions": removed_decisions,
        "note": "approved/ and rates/ are unchanged. Re-upload to extract again.",
    }
