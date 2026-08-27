"""Protected act-admin routes: upload, extract jobs, review, impact, activation."""

from __future__ import annotations

from hmac import compare_digest
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.deps import get_session
from oe_engine_app.services.act_admin_duplicate import ActAdminUploadError, ingest_upload
from oe_engine_app.services.act_admin_extract import (
    delete_job,
    queue_payload,
    remove_draft,
    retry_extract,
    run_extract_job,
    start_extract,
)
from oe_engine_app.services.act_admin_review import (
    ReviewValidationError,
    activate_draft,
    catalog_preview,
    impact_preview,
    patch_row,
    review_payload,
    set_year_kind_all,
)
from oe_engine_app.services.act_admin_store import load_job

router = APIRouter(prefix="/act-admin", tags=["act-admin"])

TOKEN_HEADER = "X-Oe-Act-Admin-Token"
REVIEWER_HEADER = "X-Oe-Act-Admin-Reviewer"


def require_act_admin_token(
    x_oe_act_admin_token: Annotated[str | None, Header()] = None,
) -> str:
    expected = (get_oe_engine_settings().OE_ENGINE_ACT_ADMIN_TOKEN or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Act admin is not configured — set OE_ENGINE_ACT_ADMIN_TOKEN "
                "in .env and restart the OE Engine."
            ),
        )
    provided = (x_oe_act_admin_token or "").strip()
    if not provided or not compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing act admin token.",
        )
    return provided


def require_act_admin_reviewer(
    x_oe_act_admin_reviewer: Annotated[str | None, Header()] = None,
) -> str:
    name = (x_oe_act_admin_reviewer or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Oe-Act-Admin-Reviewer is required (reviewer name, not a password).",
        )
    return name


ActAdminToken = Annotated[str, Depends(require_act_admin_token)]
ActAdminReviewer = Annotated[str, Depends(require_act_admin_reviewer)]


class RowPatchRequest(BaseModel):
    review_status: str | None = None
    included: bool | None = None
    change_action: str | None = None
    compare_group_id: str | None = None
    display_name: str | None = None
    cap_amount: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    input_kind: str | None = None
    question_prompt: str | None = None
    help: str | None = None
    engine_binding: dict[str, str] | None = None
    engine_scope: str | None = None
    eligibility: dict[str, Any] | None = None
    required_evidence: list[str] | None = None
    sort_order: int | None = None
    year_kind: Literal["UPDATE", "NEW_YEAR"] | None = None


class YearKindRequest(BaseModel):
    year_kind: Literal["UPDATE", "NEW_YEAR"]


class ActivateRequest(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64)


@router.get("/session")
def act_admin_session(_token: ActAdminToken) -> dict[str, Any]:
    return {
        "ok": True,
        "gate": "token",
        "routes": [
            "/optimization-explainable-engine/act-admin",
            "/optimization-explainable-engine/act-admin/upload",
            "/optimization-explainable-engine/act-admin/jobs/:jobId",
            "/optimization-explainable-engine/act-admin/review/:sourceDocId",
        ],
    }


@router.post("/session/check")
def act_admin_session_check(
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    return {"ok": True, "gate": "token+reviewer", "reviewer": reviewer}


@router.get("/queue")
def act_admin_queue(_token: ActAdminToken) -> dict[str, Any]:
    return queue_payload()


@router.post("/upload")
async def act_admin_upload(
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    raw = await file.read()
    session = get_session()
    try:
        try:
            decision, job = ingest_upload(
                session,
                raw=raw,
                filename=file.filename or "upload.pdf",
                reviewer=reviewer,
            )
        except ActAdminUploadError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        payload = decision.as_dict()
        payload["job"] = job
        return payload
    finally:
        session.close()


@router.get("/jobs/{job_id}")
def act_admin_job(job_id: str, _token: ActAdminToken) -> dict[str, Any]:
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@router.post("/jobs/{job_id}/extract")
def act_admin_start_extract(
    job_id: str,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    del reviewer
    try:
        return start_extract(job_id)
    except ActAdminUploadError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/extract/sync")
def act_admin_start_extract_sync(
    job_id: str,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    """Test-only synchronous extract (same body as background worker)."""
    del reviewer
    try:
        return run_extract_job(job_id)
    except ActAdminUploadError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry")
def act_admin_retry(
    job_id: str,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    del reviewer
    try:
        return retry_extract(job_id)
    except ActAdminUploadError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}")
def act_admin_delete_job(
    job_id: str,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    try:
        return delete_job(job_id, reviewer=reviewer)
    except ActAdminUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/review/{source_doc_id}")
def act_admin_remove_draft(
    source_doc_id: str,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    try:
        return remove_draft(source_doc_id, reviewer=reviewer)
    except ActAdminUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/pdf")
def act_admin_pdf(job_id: str, _token: ActAdminToken) -> FileResponse:
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    path = Path(str(job.get("storage_path") or ""))
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF missing")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/review/{source_doc_id}")
def act_admin_review(source_doc_id: str, _token: ActAdminToken) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            return review_payload(source_doc_id, session=session)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    finally:
        session.close()


@router.patch("/review/{source_doc_id}/rows/{entry_id}")
def act_admin_patch_row(
    source_doc_id: str,
    entry_id: str,
    body: RowPatchRequest,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    patch = body.model_dump(exclude_none=True)
    session = get_session()
    try:
        try:
            return patch_row(
                source_doc_id,
                entry_id,
                reviewer=reviewer,
                patch=patch,
                session=session,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        session.close()


@router.post("/review/{source_doc_id}/year-kind")
def act_admin_set_year_kind(
    source_doc_id: str,
    body: YearKindRequest,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            return set_year_kind_all(
                source_doc_id,
                reviewer=reviewer,
                year_kind=body.year_kind,
                session=session,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        session.close()


@router.post("/review/{source_doc_id}/impact-preview")
def act_admin_impact_preview(source_doc_id: str, _token: ActAdminToken) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            return impact_preview(session, source_doc_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    finally:
        session.close()


@router.get("/review/{source_doc_id}/catalog-preview")
def act_admin_catalog_preview(
    source_doc_id: str,
    _token: ActAdminToken,
    assessment_year: str | None = None,
) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            return catalog_preview(session, source_doc_id, assessment_year=assessment_year)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    finally:
        session.close()


@router.post("/review/{source_doc_id}/activate")
def act_admin_activate(
    source_doc_id: str,
    body: ActivateRequest,
    _token: ActAdminToken,
    reviewer: ActAdminReviewer,
) -> dict[str, Any]:
    session = get_session()
    try:
        try:
            result = activate_draft(
                session,
                source_doc_id,
                fingerprint=body.fingerprint,
                reviewer=reviewer,
            )
            session.commit()
            return result
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ReviewValidationError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        session.close()
