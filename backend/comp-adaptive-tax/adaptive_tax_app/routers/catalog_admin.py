"""Catalog-admin gate, duplicate check, extract, and per-row classification."""
# WatchFiles reload so COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN is picked up.

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.services.catalog_admin_store import load_job
from adaptive_tax_app.services.catalog_classify import (
    refresh_classification,
    set_kind_human,
)
from adaptive_tax_app.services.catalog_duplicate import (
    CatalogConflictError,
    CatalogDuplicateError,
    build_corpus_hash_index,
    discard_job,
    ingest_upload,
    queue_payload,
    set_source_doc_id,
    treat_as_new_source,
)
from adaptive_tax_app.services.catalog_extract import delete_job, remove_proposal, start_extract
from adaptive_tax_app.services.catalog_promote import confirm_new_year, promote_new_year, promote_update
from adaptive_tax_app.services.catalog_review import (
    decide_row,
    promote_preview,
    review_payload,
    set_row_engine_binding,
    set_row_question_fields,
)

router = APIRouter(prefix="/catalog-admin", tags=["catalog-admin"])

TOKEN_HEADER = "X-Catalog-Admin-Token"
REVIEWER_HEADER = "X-Catalog-Admin-Reviewer"


def require_catalog_admin_token(
    x_catalog_admin_token: Annotated[str | None, Header()] = None,
) -> str:
    """Gate: configured token must match. Does not identify the reviewer."""
    expected = (get_adaptive_tax_settings().COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Catalog admin is not configured — set COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN "
                "in .env and restart Adaptive Tax."
            ),
        )
    provided = (x_catalog_admin_token or "").strip()
    if not provided or not compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing catalog admin token.",
        )
    return provided


def require_catalog_admin_reviewer(
    x_catalog_admin_reviewer: Annotated[str | None, Header()] = None,
) -> str:
    """Attribution only — not a second password. Required on mutating routes."""
    name = (x_catalog_admin_reviewer or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Catalog-Admin-Reviewer is required (reviewer name, not a password).",
        )
    return name


CatalogAdminToken = Annotated[str, Depends(require_catalog_admin_token)]
CatalogAdminReviewer = Annotated[str, Depends(require_catalog_admin_reviewer)]


def _raise_duplicate(exc: CatalogDuplicateError) -> None:
    msg = str(exc)
    if isinstance(exc, CatalogConflictError):
        code = status.HTTP_409_CONFLICT
    elif "not found" in msg.lower():
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=msg) from exc


@router.get("/session", summary="Verify catalog-admin token (no reviewer required)")
def catalog_admin_session(_token: CatalogAdminToken) -> dict[str, Any]:
    return {
        "ok": True,
        "gate": "token",
        "step": 7,
        "routes": [
            "/adaptive-tax/catalog-admin",
            "/adaptive-tax/catalog-admin/upload",
            "/adaptive-tax/catalog-admin/review/:sourceDocId",
            "/adaptive-tax/catalog-admin/jobs/:jobId",
        ],
    }


@router.post("/session/check", summary="Verify token + reviewer on a mutating call")
def catalog_admin_session_check(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
) -> dict[str, Any]:
    return {"ok": True, "gate": "token+reviewer", "reviewer": reviewer}


@router.get("/queue", summary="Pending proposals, in-flight jobs, failed jobs")
def catalog_admin_queue(_token: CatalogAdminToken) -> dict[str, Any]:
    return queue_payload()


@router.post("/upload", summary="Cheap PDF read + hash-first duplicate check (no Pass 1)")
async def catalog_admin_upload(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    raw = await file.read()
    try:
        decision, job = ingest_upload(
            content=raw,
            filename=file.filename or "upload.pdf",
            reviewer=reviewer,
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    payload = decision.as_dict()
    payload["job"] = job
    return payload


@router.post("/corpus-hashes/refresh", summary="Rebuild corpus_text_hashes.json (not the manifest)")
def catalog_admin_refresh_hashes(
    _token: CatalogAdminToken,
    _reviewer: CatalogAdminReviewer,
) -> dict[str, Any]:
    index = build_corpus_hash_index()
    return {
        "ok": True,
        "indexed_at": index.get("indexed_at"),
        "document_count": len(index.get("documents") or []),
        "path_errors": index.get("path_errors") or [],
        "path": "models/adaptive-tax/relief-interview/review/corpus_text_hashes.json",
    }


@router.get("/jobs/{job_id}", summary="In-flight / failed / paused catalog-admin job")
def catalog_admin_get_job(_token: CatalogAdminToken, job_id: str) -> dict[str, Any]:
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")
    return job


@router.post(
    "/jobs/{job_id}/treat-as-new-source",
    summary="Case (d): mint a new source_doc_id; never replace the matched Act",
)
def catalog_admin_treat_as_new_source(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    job_id: str,
) -> dict[str, Any]:
    try:
        decision, job = treat_as_new_source(job_id, reviewer=reviewer)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    payload = decision.as_dict()
    payload["job"] = job
    return payload


@router.post("/jobs/{job_id}/discard", summary="Cancel a paused or pre-extract job")
def catalog_admin_discard_job(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    job_id: str,
) -> dict[str, Any]:
    try:
        job = discard_job(job_id, reviewer=reviewer)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    return job


@router.post("/jobs/{job_id}/source-doc-id", summary="Edit minted source_doc_id before extract")
def catalog_admin_set_source_doc_id(
    _token: CatalogAdminToken,
    _reviewer: CatalogAdminReviewer,
    job_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    try:
        job = set_source_doc_id(job_id, str(body.get("source_doc_id") or ""))
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    return job


@router.post(
    "/jobs/{job_id}/extract",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start extract_proposal in the background (no Pass 1 shortcut)",
)
def catalog_admin_extract(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    job_id: str,
) -> dict[str, Any]:
    try:
        job = start_extract(job_id, reviewer=reviewer, retry=False)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    return job


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed extract on the same stored PDF",
)
def catalog_admin_retry_extract(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    job_id: str,
) -> dict[str, Any]:
    try:
        job = start_extract(job_id, reviewer=reviewer, retry=True)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
    return job


@router.delete(
    "/jobs/{job_id}",
    summary="Delete failed/abandoned job + uploaded PDF only",
)
def catalog_admin_delete_job(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    job_id: str,
) -> dict[str, Any]:
    try:
        return delete_job(job_id, reviewer=reviewer)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.delete(
    "/proposed/{source_doc_id}",
    summary="Remove a finished extract from the review queue (staging only)",
)
def catalog_admin_remove_proposal(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
) -> dict[str, Any]:
    try:
        return remove_proposal(source_doc_id, reviewer=reviewer)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.get("/proposed/{source_doc_id}", summary="Proposal + Phase 5 review rows (wrapper, not a second ledger)")
def catalog_admin_get_proposed(_token: CatalogAdminToken, source_doc_id: str) -> dict[str, Any]:
    try:
        return review_payload(source_doc_id)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/classification",
    summary="Set human kind_human on one included row (suggestion is never auto-selected)",
)
def catalog_admin_set_classification(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    try:
        set_kind_human(
            source_doc_id,
            row_id=str(body.get("row_id") or ""),
            kind_human=str(body.get("kind_human") or ""),
            reviewer=reviewer,
        )
        return review_payload(source_doc_id)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/classify",
    summary="Run harvest_act on the stored PDF and attach per-row suggestions",
)
def catalog_admin_refresh_classification(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
) -> dict[str, Any]:
    try:
        refresh_classification(source_doc_id, reviewer=reviewer)
        return review_payload(source_doc_id)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/engine-binding",
    summary="Set engine_binding on one included relief (third trail; does not overwrite kind_set_* or reviewed_by)",
)
def catalog_admin_set_engine_binding(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    try:
        return set_row_engine_binding(
            source_doc_id,
            row_id=str(body.get("row_id") or ""),
            kind=str(body.get("kind") or ""),
            reviewer=reviewer,
            component_id=(str(body["component_id"]) if body.get("component_id") else None),
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/question-fields",
    summary="Auditor-edit taxpayer question fields (caps and quotes stay verbatim)",
)
def catalog_admin_set_question_fields(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    try:
        return set_row_question_fields(
            source_doc_id,
            row_id=str(body.get("row_id") or ""),
            display_name=str(body.get("display_name") or ""),
            question_prompt=str(body.get("question_prompt") or ""),
            input_kind=str(body.get("input_kind") or ""),
            help_text=str(body.get("help") or ""),
            compare_group_id=str(body.get("compare_group_id") or ""),
            reviewer=reviewer,
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/rows/{row_id}/approve",
    summary="Phase 5 approve via _record (ledger reviewer only; gate-fail blocked)",
)
def catalog_admin_approve_row(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    row_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = body or {}
    try:
        return decide_row(
            source_doc_id,
            row_id=row_id,
            status="approved",
            reviewer=reviewer,
            sole_check=bool(payload.get("sole_check")),
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/rows/{row_id}/reject",
    summary="Phase 5 reject via _record",
)
def catalog_admin_reject_row(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    row_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason = str((body or {}).get("reason") or "") or None
    try:
        return decide_row(
            source_doc_id, row_id=row_id, status="rejected", reviewer=reviewer, reason=reason
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/rows/{row_id}/flag",
    summary="Request re-extract: Phase 5 needs_manual_verification",
)
def catalog_admin_flag_row(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    row_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason = str((body or {}).get("reason") or "") or None
    try:
        return decide_row(
            source_doc_id,
            row_id=row_id,
            status="needs_manual_verification",
            reviewer=reviewer,
            reason=reason,
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/confirm-new-year",
    summary="Hard-stop confirm: write_empty_skeletons then Phase 6 cmd_set_year",
)
def catalog_admin_confirm_new_year(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = body or {}
    try:
        return confirm_new_year(
            source_doc_id,
            reviewer=reviewer,
            assessment_year=str(payload.get("assessment_year") or ""),
            confirmed=bool(payload.get("confirmed")),
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/promote-new-year",
    summary="NEW_YEAR populate via Phase 6 cmd_promote after confirm",
)
def catalog_admin_promote_new_year(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
) -> dict[str, Any]:
    try:
        return promote_new_year(source_doc_id, reviewer=reviewer)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/promote-preview",
    summary="Impact preview: select_for_year before/after; does not write year files",
)
def catalog_admin_promote_preview(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
) -> dict[str, Any]:
    try:
        return promote_preview(source_doc_id)
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover


@router.post(
    "/proposed/{source_doc_id}/promote",
    summary="UPDATE promote via select_for_year; writes only changed year files",
)
def catalog_admin_promote(
    _token: CatalogAdminToken,
    reviewer: CatalogAdminReviewer,
    source_doc_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = body or {}
    try:
        return promote_update(
            source_doc_id,
            reviewer=reviewer,
            preview_fingerprint=str(payload.get("preview_fingerprint") or ""),
            acknowledged_group_ids=[
                str(g) for g in (payload.get("acknowledged_group_ids") or [])
            ],
        )
    except CatalogDuplicateError as exc:
        _raise_duplicate(exc)
        raise  # pragma: no cover
