"""Background ingest + quote-gated LLM extract for act-admin jobs."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.deps import SessionLocal
from oe_engine_app.services.act_admin_ingest import (
    _rewrite_draft_ids,
    extract_source_doc_id,
    ingest_uploaded_pdf,
)
from oe_engine_app.services.act_admin_store import (
    ActAdminPaths,
    act_admin_paths,
    load_job,
    now_iso,
    save_draft,
    save_job,
)
from oe_engine_app.services.act_admin_duplicate import ActAdminUploadError
from oe_engine_app.services.embedder import Embedder
from oe_engine_app.services.extract import run_extract, write_extract_run
from oe_engine_app.services.spend import PHASE6_HARD_STOP_USD, PHASE6_SOFT_CAP_USD, SpendLedger, load_phase6_prior

logger = logging.getLogger(__name__)

_THREADS: dict[str, threading.Thread] = {}
_START_LOCK = threading.Lock()

ExtractRunner = Callable[..., dict[str, Any]]
extract_runner_impl: ExtractRunner | None = None


def _pdf_path(job: dict[str, Any]) -> Path:
    raw = job.get("storage_path") or ""
    path = Path(raw)
    if not path.is_file():
        raise ActAdminUploadError("Uploaded PDF is missing; cannot extract.")
    return path


def _fail_job(job: dict[str, Any], *, error: str, paths: ActAdminPaths) -> dict[str, Any]:
    job["status"] = "failed"
    job["error"] = error
    job["failed_at"] = now_iso()
    job["extract_finished_at"] = job["failed_at"]
    save_job(job, paths)
    return job


def _build_embedder() -> Embedder:
    settings = get_oe_engine_settings()
    if not settings.OPENAI_API_KEY:
        raise ActAdminUploadError("OPENAI_API_KEY is not set (required for ingest embeddings).")

    from oe_engine_app.services.embedder import OpenAIEmbedder

    return OpenAIEmbedder(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OE_ENGINE_EMBEDDING_MODEL,
        batch_size=settings.OE_ENGINE_EMBED_BATCH_SIZE,
    )


def _build_llm(ledger: SpendLedger):
    settings = get_oe_engine_settings()
    if not settings.OPENAI_API_KEY:
        raise ActAdminUploadError("OPENAI_API_KEY is not set (required for LLM extract).")
    from openai import OpenAI

    from oe_engine_app.services.extract_llm import OpenAIExtractLLM

    return OpenAIExtractLLM(
        OpenAI(api_key=settings.OPENAI_API_KEY),
        model=settings.OE_ENGINE_EXTRACT_MODEL,
        ledger=ledger,
    )


def run_extract_job(job_id: str, *, paths: ActAdminPaths | None = None) -> dict[str, Any]:
    """Synchronous extract body (worker thread and tests)."""
    root = paths or act_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise ActAdminUploadError(f"Job {job_id} not found.")
    sid = str(job.get("source_doc_id") or "").strip()
    try:
        pdf_path = _pdf_path(job)
        job["status"] = "ingesting"
        job["extract_started_at"] = now_iso()
        job["error"] = None
        save_job(job, root)

        session = SessionLocal()
        try:
            embedder = _build_embedder()
            ingest_result = ingest_uploaded_pdf(
                session,
                pdf_path=pdf_path,
                source_doc_id=sid,
                title=str((job.get("act_identity") or {}).get("label") or job.get("original_filename") or sid),
                embedder=embedder,
            )
            extract_sid = extract_source_doc_id(sid, ingest_result)
            if extract_sid != sid:
                job["ingest_reused_from"] = extract_sid
            session.commit()
            job["ingest_status"] = ingest_result.status
            job["chunk_count"] = ingest_result.chunk_count
            job["embedding_usd"] = ingest_result.embedding_usd
            job["status"] = "extracting"
            save_job(job, root)

            prior = load_phase6_prior()
            ledger = SpendLedger(budget="act_admin", prior_usd=prior)
            llm = _build_llm(ledger)
            run = run_extract(
                session,
                source_doc_id=extract_sid,
                llm=llm,
                ledger=ledger,
                dry_run=False,
                schema_validate=False,
                seed=False,
                act_admin=True,
                apply_terminus=False,
            )
            session.commit()
            settings = get_oe_engine_settings()
            write_extract_run(run, settings.OE_ENGINE_EXTRACT_OUT)
            ledger.dump()

            draft = run.model_dump(mode="json")
            _rewrite_draft_ids(draft, job_sid=sid, extract_sid=extract_sid)
            draft["job_id"] = job_id
            draft["review_status"] = "pending"
            draft["reviewer"] = job.get("reviewer")
            save_draft(draft, root)

            job["status"] = "extracted"
            job["error"] = None
            job["extract_finished_at"] = now_iso()
            job["extraction_run_id"] = run.extraction_run_id
            job["entity_count"] = len(run.entities)
            job["included_count"] = sum(1 for e in run.entities if e.get("included"))
            job["usd_this_run"] = run.usd_this_run
            job["model"] = run.model
            job["review_path"] = f"/optimization-explainable-engine/act-admin/review/{sid}"
            save_job(job, root)
            return job
        finally:
            session.close()
    except Exception as exc:
        logger.exception("Act-admin extract failed for job %s", job_id)
        return _fail_job(job, error=str(exc) or exc.__class__.__name__, paths=root)


def _spawn(job_id: str) -> None:
    thread = threading.Thread(
        target=run_extract_job,
        kwargs={"job_id": job_id},
        name=f"oe-act-admin-extract-{job_id[:8]}",
        daemon=True,
    )
    with _START_LOCK:
        _THREADS[job_id] = thread
    thread.start()


def start_extract(job_id: str, *, paths: ActAdminPaths | None = None) -> dict[str, Any]:
    root = paths or act_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise ActAdminUploadError(f"Job {job_id} not found.")
    status = str(job.get("status") or "")
    if status in {"ingesting", "extracting"}:
        return job
    if status == "extracted":
        return job
    job["status"] = "extracting"
    job["extract_started_at"] = now_iso()
    job["error"] = None
    save_job(job, root)
    _spawn(job_id)
    return job


def retry_extract(job_id: str, *, paths: ActAdminPaths | None = None) -> dict[str, Any]:
    root = paths or act_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise ActAdminUploadError(f"Job {job_id} not found.")
    job["status"] = "uploaded"
    job["error"] = None
    save_job(job, root)
    return start_extract(job_id, paths=root)


def queue_payload(*, paths: ActAdminPaths | None = None) -> dict[str, Any]:
    root = paths or act_admin_paths()
    jobs = list_jobs_sorted(root)
    proposals: list[dict[str, Any]] = []
    in_flight: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for job in jobs:
        status = str(job.get("status") or "")
        sid = str(job.get("source_doc_id") or "")
        act_label = str((job.get("act_identity") or {}).get("label") or "")
        if status == "extracted":
            proposals.append(
                {
                    "source_doc_id": sid,
                    "extracted_at": job.get("extract_finished_at") or job.get("uploaded_at"),
                    "act_title": act_label,
                    "pdf_file_name": job.get("original_filename"),
                    "included_count": job.get("included_count"),
                    "entity_count": job.get("entity_count"),
                    "promotion_status": job.get("activation_status"),
                    "review_path": f"/optimization-explainable-engine/act-admin/review/{sid}",
                    "job_id": job.get("id"),
                }
            )
            continue
        if status in IN_FLIGHT_STATUSES:
            in_flight.append(
                {
                    "id": job.get("id"),
                    "status": status,
                    "source_doc_id": sid,
                    "original_filename": job.get("original_filename"),
                    "act_label": act_label,
                    "created_at": job.get("uploaded_at") or job.get("extract_started_at"),
                    "job_path": f"/optimization-explainable-engine/act-admin/jobs/{job.get('id')}",
                }
            )
            continue
        if status == "failed":
            failed.append(
                {
                    "id": job.get("id"),
                    "status": "failed",
                    "error": job.get("error"),
                    "created_at": job.get("failed_at") or job.get("uploaded_at"),
                    "original_filename": job.get("original_filename"),
                    "act_label": act_label,
                    "job_path": f"/optimization-explainable-engine/act-admin/jobs/{job.get('id')}",
                }
            )
    return {
        "proposals": proposals,
        "in_flight_jobs": in_flight,
        "failed_jobs": failed,
        "job_count": len(jobs),
        "note": (
            "Finished extracts wait in Ready to review. In-flight jobs move there when "
            "extract completes — refresh is automatic on the queue page."
        ),
    }


def list_jobs_sorted(paths: ActAdminPaths | None = None) -> list[dict[str, Any]]:
    from oe_engine_app.services.act_admin_store import list_jobs

    root = paths or act_admin_paths()
    jobs = list_jobs(root)
    jobs.sort(key=lambda row: str(row.get("uploaded_at") or ""), reverse=True)
    return jobs


IN_FLIGHT_STATUSES = frozenset({"uploaded", "ingesting", "extracting"})
PENDING_REVIEW_STATUSES = frozenset({"extracted"})


def delete_job(
    job_id: str,
    *,
    reviewer: str,
    paths: ActAdminPaths | None = None,
) -> dict[str, Any]:
    """Remove a failed, waiting, or stuck ingest/extract job and its uploaded PDF."""
    from oe_engine_app.services.act_admin_store import job_path, load_job

    root = paths or act_admin_paths()
    job = load_job(job_id, root)
    if job is None:
        raise ActAdminUploadError(f"Job {job_id} not found.")
    status = str(job.get("status") or "")
    if status == "extracted":
        raise ActAdminUploadError(
            "This extract is ready to review — remove it from Ready to review instead."
        )
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


def remove_draft(
    source_doc_id: str,
    *,
    reviewer: str,
    paths: ActAdminPaths | None = None,
) -> dict[str, Any]:
    """Drop a finished extract from the review queue (draft only; live year views unchanged)."""
    from oe_engine_app.services.act_admin_store import (
        draft_path,
        job_path,
        list_jobs,
        load_job,
    )

    root = paths or act_admin_paths()
    sid = (source_doc_id or "").strip()
    if not sid:
        raise ActAdminUploadError("source_doc_id is required.")
    matching_jobs = [job for job in list_jobs(root) if str(job.get("source_doc_id") or "") == sid]
    if not matching_jobs and not draft_path(sid, root).is_file():
        raise ActAdminUploadError(f"No queue entry found for {sid}.")
    for job in matching_jobs:
        if str(job.get("status") or "") in {"ingesting", "extracting"}:
            raise ActAdminUploadError("Cannot remove while extract is still running.")
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
    draft_path(sid, root).unlink(missing_ok=True)
    return {
        "source_doc_id": sid,
        "status": "removed",
        "removed_by": reviewer,
        "removed_at": now_iso(),
        "removed_jobs": removed_jobs,
    }
