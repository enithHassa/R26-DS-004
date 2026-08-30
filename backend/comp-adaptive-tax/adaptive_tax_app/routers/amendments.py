"""Admin amendment upload / extract / review API."""

from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import AmendmentExtractRun, AmendmentJob, RuleSource
from adaptive_tax_app.schemas.amendments import (
    AmendmentApproveResponse,
    AmendmentExtractResponse,
    AmendmentJobOut,
    AmendmentRejectResponse,
    AmendmentUploadResponse,
    ExtractRunOut,
    MergeStubOut,
    ParamOverrideStubOut,
    RejectAmendmentRequest,
    RuleSourceOut,
)
from adaptive_tax_app.services.amendment_review import (
    AmendmentReviewError,
    approve_amendment,
    approve_amendment_file,
    reject_amendment,
    reject_amendment_file,
)
from adaptive_tax_app.services.extraction import (
    AmendmentExtractError,
    get_job_rule_sources,
    get_latest_extract_run,
    run_amendment_extraction,
    run_amendment_extraction_file,
)
from adaptive_tax_app.services.storage import (
    AmendmentStorageError,
    store_amendment_pdf,
)
from backend.shared.config.database import SessionLocal

router = APIRouter(prefix="/admin/amendments", tags=["admin-amendments"])


def get_amendment_db() -> Generator[Session | None, None, None]:
    """Yield a DB session only when amendment jobs use PostgreSQL."""
    if get_adaptive_tax_settings().amendment_store_mode == "file":
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

_DB_UNAVAILABLE_DETAIL = (
    "PostgreSQL is unavailable — amendment upload needs a live database. "
    "Your previous setup uses Azure Postgres (DATABASE_MODE=azure). "
    "Start Flexible Server 'tax-advisory-db' in Azure Portal, then retry. "
    "Local Docker Postgres needs WSL2; without WSL use Azure instead of DATABASE_MODE=local. "
    "Temporary demo without Postgres: set COMP_ADAPTIVE_TAX_AMENDMENT_STORE=file in .env "
    "and restart the Adaptive Tax service."
)


def _raise_if_db_unavailable(exc: BaseException) -> None:
    """Map connection failures to HTTP 503 with an actionable message."""
    if isinstance(exc, OperationalError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from exc
    msg = str(exc).lower()
    if any(
        needle in msg
        for needle in (
            "connection timed out",
            "could not connect",
            "connection refused",
            "actively refused",
            "server closed the connection",
            "operationalerror",
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from exc


def _rule_source_out(row: RuleSource) -> RuleSourceOut:
    return RuleSourceOut(
        id=row.id,
        amendment_job_id=row.amendment_job_id,
        extract_run_id=row.extract_run_id,
        sort_order=row.sort_order,
        section=row.section,
        paragraph=row.paragraph,
        rule_type=row.rule_type.value if row.rule_type is not None else "",
        concept_id=row.concept_id,
        condition=row.condition,
        formula=row.formula,
        threshold=row.threshold,
        maximum=row.maximum,
        effective_date=row.effective_date,
        amends_section=row.amends_section,
        source_quote=row.source_quote,
        status=row.status.value if row.status is not None else "",
        created_at=row.created_at,
    )


def _extract_run_out(row: AmendmentExtractRun) -> ExtractRunOut:
    metrics = row.metrics if isinstance(row.metrics, dict) else None
    mode = None
    if metrics and isinstance(metrics.get("mode"), str):
        mode = metrics["mode"]
    elif isinstance(row.audit_payload, dict) and isinstance(row.audit_payload.get("mode"), str):
        mode = row.audit_payload["mode"]
    return ExtractRunOut(
        id=row.id,
        amendment_job_id=row.amendment_job_id,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        status=row.status.value if row.status is not None else "",
        mode=mode,
        warnings=row.warnings,
        metrics=metrics,
        audit_payload=row.audit_payload if isinstance(row.audit_payload, dict) else None,
        error_message=row.error_message,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _job_out(
    job: AmendmentJob,
    rule_sources: list[RuleSource] | None = None,
    latest_extract_run: AmendmentExtractRun | None = None,
) -> AmendmentJobOut:
    rows = rule_sources if rule_sources is not None else []
    return AmendmentJobOut(
        id=job.id,
        original_filename=job.original_filename,
        content_type=job.content_type,
        size_bytes=job.size_bytes,
        file_hash=job.file_hash,
        storage_path=job.storage_path,
        status=job.status.value if job.status is not None else "",
        extracted_rules=job.extracted_rules,
        rejection_reason=job.rejection_reason,
        created_at=job.created_at,
        updated_at=job.updated_at,
        extracted_at=job.extracted_at,
        reviewed_at=job.reviewed_at,
        rule_sources=[_rule_source_out(r) for r in rows],
        latest_extract_run=_extract_run_out(latest_extract_run) if latest_extract_run else None,
    )


def _stored_job_out(job: "StoredAmendmentJob") -> AmendmentJobOut:
    from adaptive_tax_app.services.amendment_file_store import (
        StoredAmendmentJob,
        StoredExtractRunRecord,
        StoredRuleSourceRecord,
        get_latest_extract_run as get_latest_file_extract_run,
    )

    latest: StoredExtractRunRecord | None = get_latest_file_extract_run(job)

    def _stored_rule_out(row: StoredRuleSourceRecord) -> RuleSourceOut:
        return RuleSourceOut(
            id=row.id,
            amendment_job_id=row.amendment_job_id,
            extract_run_id=row.extract_run_id,
            sort_order=row.sort_order,
            section=row.section,
            paragraph=row.paragraph,
            rule_type=row.rule_type,
            concept_id=row.concept_id,
            condition=row.condition,
            formula=row.formula,
            threshold=row.threshold,
            maximum=row.maximum,
            effective_date=row.effective_date,
            amends_section=row.amends_section,
            source_quote=row.source_quote,
            status=row.status,
            created_at=row.created_at,
        )

    def _stored_extract_out(row: StoredExtractRunRecord) -> ExtractRunOut:
        metrics = row.metrics if isinstance(row.metrics, dict) else None
        mode = None
        if metrics and isinstance(metrics.get("mode"), str):
            mode = metrics["mode"]
        elif isinstance(row.audit_payload, dict) and isinstance(row.audit_payload.get("mode"), str):
            mode = row.audit_payload["mode"]
        warnings = row.warnings
        if isinstance(warnings, dict) and "messages" in warnings:
            raw = warnings.get("messages")
            if isinstance(raw, list):
                warnings = raw
        return ExtractRunOut(
            id=row.id,
            amendment_job_id=row.amendment_job_id,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            status=row.status,
            mode=mode,
            warnings=warnings,
            metrics=metrics,
            audit_payload=row.audit_payload if isinstance(row.audit_payload, dict) else None,
            error_message=row.error_message,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )

    return AmendmentJobOut(
        id=job.id,
        original_filename=job.original_filename,
        content_type=job.content_type,
        size_bytes=job.size_bytes,
        file_hash=job.file_hash,
        storage_path=job.storage_path,
        status=job.status,
        extracted_rules=job.extracted_rules,
        rejection_reason=job.rejection_reason,
        created_at=job.created_at,
        updated_at=job.updated_at,
        extracted_at=job.extracted_at,
        reviewed_at=job.reviewed_at,
        rule_sources=[_stored_rule_out(r) for r in job.rule_sources],
        latest_extract_run=_stored_extract_out(latest) if latest else None,
    )


def _uses_file_store() -> bool:
    return get_adaptive_tax_settings().amendment_store_mode == "file"


@router.post(
    "/upload",
    response_model=AmendmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_amendment(
    file: UploadFile = File(...),
    db: Session | None = Depends(get_amendment_db),
) -> AmendmentUploadResponse:
    content = await file.read()
    if _uses_file_store():
        from adaptive_tax_app.services.amendment_file_store import store_amendment_pdf_file

        try:
            result = store_amendment_pdf_file(
                content=content,
                filename=file.filename or "amendment.pdf",
                content_type=file.content_type,
            )
        except AmendmentStorageError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        job = result.job
        return AmendmentUploadResponse(
            id=job.id,
            original_filename=job.original_filename,
            file_hash=job.file_hash,
            storage_path=job.storage_path,
            size_bytes=job.size_bytes,
            status=job.status,
            duplicate_hash_warning=result.duplicate_hash_warning,
        )

    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database session unavailable.",
            )
        result = store_amendment_pdf(
            db=db,
            content=content,
            filename=file.filename or "amendment.pdf",
            content_type=file.content_type,
        )
        db.commit()
        db.refresh(result.job)
    except AmendmentStorageError as exc:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        _raise_if_db_unavailable(exc)
        raise

    job = result.job
    return AmendmentUploadResponse(
        id=job.id,
        original_filename=job.original_filename,
        file_hash=job.file_hash,
        storage_path=job.storage_path,
        size_bytes=job.size_bytes,
        status=job.status.value,
        duplicate_hash_warning=result.duplicate_hash_warning,
    )


@router.post("/{job_id}/extract", response_model=AmendmentExtractResponse)
def extract_amendment(
    job_id: UUID,
    db: Session | None = Depends(get_amendment_db),
) -> AmendmentExtractResponse:
    if _uses_file_store():
        try:
            result = run_amendment_extraction_file(job_id=job_id)
        except AmendmentExtractError as exc:
            detail = str(exc)
            code = status.HTTP_400_BAD_REQUEST
            if "not found" in detail.lower():
                code = status.HTTP_404_NOT_FOUND
            raise HTTPException(status_code=code, detail=detail) from exc

        job_out = _stored_job_out(result.job)
        return AmendmentExtractResponse(
            job=job_out,
            extract_run_id=result.extract_run.id,
            mode=result.extraction.mode,
            model_name=result.extraction.model_name,
            rule_count=len(result.rule_sources),
            warnings=result.extraction.warnings,
            amends_section_candidates=result.focused.amends_section_candidates,
        )

    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database session unavailable.",
            )
        result = run_amendment_extraction(db=db, job_id=job_id)
        db.commit()
        db.refresh(result.job)
        for row in result.rule_sources:
            db.refresh(row)
    except AmendmentExtractError as exc:
        # Persist FAILED job / extract_run rows written before the raise.
        db.commit()
        detail = str(exc)
        code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        _raise_if_db_unavailable(exc)
        raise

    return AmendmentExtractResponse(
        job=_job_out(result.job, result.rule_sources, result.extract_run),
        extract_run_id=result.extract_run.id,
        mode=result.extraction.mode,
        model_name=result.extraction.model_name,
        rule_count=len(result.rule_sources),
        warnings=result.extraction.warnings,
        amends_section_candidates=result.focused.amends_section_candidates,
    )


@router.get("/{job_id}", response_model=AmendmentJobOut)
def get_amendment(
    job_id: UUID,
    db: Session | None = Depends(get_amendment_db),
) -> AmendmentJobOut:
    if _uses_file_store():
        from adaptive_tax_app.services.amendment_file_store import load_job

        job = load_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amendment job not found")
        return _stored_job_out(job)

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session unavailable.",
        )
    job = db.get(AmendmentJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amendment job not found")
    rules = get_job_rule_sources(db, job.id)
    latest = get_latest_extract_run(db, job.id)
    return _job_out(job, rules, latest)


@router.post("/{job_id}/approve", response_model=AmendmentApproveResponse)
def approve_amendment_endpoint(
    job_id: UUID,
    db: Session | None = Depends(get_amendment_db),
) -> AmendmentApproveResponse:
    if _uses_file_store():
        try:
            result = approve_amendment_file(job_id=job_id)
        except AmendmentReviewError as exc:
            detail = str(exc)
            code = status.HTTP_400_BAD_REQUEST
            if "not found" in detail.lower():
                code = status.HTTP_404_NOT_FOUND
            raise HTTPException(status_code=code, detail=detail) from exc

        override_out: ParamOverrideStubOut | None = None
        if result.param_override is not None:
            po = result.param_override
            override_out = ParamOverrideStubOut(
                written=True,
                source=po.source,
                path=str(po.path),
                concept_id=po.concept_id,
                cap_amount=format(po.cap_amount, "f"),
                rule_source_id=po.rule_source_id,
                amendment_job_id=po.amendment_job_id,
                kind="relief",
            )
        else:
            override_out = ParamOverrideStubOut(written=False, kind="relief")

        rate_out: ParamOverrideStubOut | None = None
        if result.rate_override is not None:
            ro = result.rate_override
            rate_out = ParamOverrideStubOut(
                written=True,
                source=ro.source,
                path=str(ro.path),
                concept_id=ro.concept_id,
                rule_source_id=ro.rule_source_id,
                amendment_job_id=ro.amendment_job_id,
                kind="rate",
                band_update_count=ro.band_update_count,
                assessment_years=list(ro.assessment_years),
            )
        else:
            rate_out = ParamOverrideStubOut(written=False, kind="rate")

        return AmendmentApproveResponse(
            job=_stored_job_out(result.job),
            rule_version_ids=[v.id for v in result.rule_versions],
            merge=MergeStubOut(
                merged=result.merge.merged,
                reason=result.merge.reason,
                amendment_job_id=result.merge.amendment_job_id,
                details=result.merge.details,
            ),
            param_override=override_out,
            rate_override=rate_out,
        )

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session unavailable.",
        )
    try:
        result = approve_amendment(db=db, job_id=job_id)
    except AmendmentReviewError as exc:
        detail = str(exc)
        code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc

    override_out: ParamOverrideStubOut | None = None
    if result.param_override is not None:
        po = result.param_override
        override_out = ParamOverrideStubOut(
            written=True,
            source=po.source,
            path=str(po.path),
            concept_id=po.concept_id,
            cap_amount=format(po.cap_amount, "f"),
            rule_source_id=po.rule_source_id,
            amendment_job_id=po.amendment_job_id,
            kind="relief",
        )
    else:
        override_out = ParamOverrideStubOut(written=False, kind="relief")

    rate_out: ParamOverrideStubOut | None = None
    if result.rate_override is not None:
        ro = result.rate_override
        rate_out = ParamOverrideStubOut(
            written=True,
            source=ro.source,
            path=str(ro.path),
            concept_id=ro.concept_id,
            rule_source_id=ro.rule_source_id,
            amendment_job_id=ro.amendment_job_id,
            kind="rate",
            band_update_count=ro.band_update_count,
            assessment_years=list(ro.assessment_years),
        )
    else:
        rate_out = ParamOverrideStubOut(written=False, kind="rate")

    return AmendmentApproveResponse(
        job=_job_out(
            result.job,
            result.rule_sources,
            get_latest_extract_run(db, result.job.id),
        ),
        rule_version_ids=[v.id for v in result.rule_versions],
        merge=MergeStubOut(
            merged=result.merge.merged,
            reason=result.merge.reason,
            amendment_job_id=result.merge.amendment_job_id,
            details=result.merge.details,
        ),
        param_override=override_out,
        rate_override=rate_out,
    )


@router.post("/{job_id}/reject", response_model=AmendmentRejectResponse)
def reject_amendment_endpoint(
    job_id: UUID,
    body: RejectAmendmentRequest,
    db: Session | None = Depends(get_amendment_db),
) -> AmendmentRejectResponse:
    if _uses_file_store():
        try:
            result = reject_amendment_file(job_id=job_id, reason=body.reason)
        except AmendmentReviewError as exc:
            detail = str(exc)
            code = status.HTTP_400_BAD_REQUEST
            if "not found" in detail.lower():
                code = status.HTTP_404_NOT_FOUND
            raise HTTPException(status_code=code, detail=detail) from exc

        return AmendmentRejectResponse(job=_stored_job_out(result.job))

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session unavailable.",
        )
    try:
        result = reject_amendment(db=db, job_id=job_id, reason=body.reason)
    except AmendmentReviewError as exc:
        detail = str(exc)
        code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc

    return AmendmentRejectResponse(
        job=_job_out(
            result.job,
            result.rule_sources,
            get_latest_extract_run(db, result.job.id),
        )
    )