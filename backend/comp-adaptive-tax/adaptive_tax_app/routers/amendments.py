"""Admin amendment upload / extract / review API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from adaptive_tax_app.db_loader import AmendmentJob, RuleSource
from adaptive_tax_app.schemas.amendments import (
    AmendmentApproveResponse,
    AmendmentExtractResponse,
    AmendmentJobOut,
    AmendmentRejectResponse,
    AmendmentUploadResponse,
    MergeStubOut,
    ParamOverrideStubOut,
    RejectAmendmentRequest,
    RuleSourceOut,
)
from adaptive_tax_app.services.amendment_review import (
    AmendmentReviewError,
    approve_amendment,
    reject_amendment,
)
from adaptive_tax_app.services.extraction import (
    AmendmentExtractError,
    get_job_rule_sources,
    run_amendment_extraction,
)
from adaptive_tax_app.services.storage import (
    AmendmentStorageError,
    store_amendment_pdf,
)
from backend.shared.config.database import get_db

router = APIRouter(prefix="/admin/amendments", tags=["admin-amendments"])


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


def _job_out(job: AmendmentJob, rule_sources: list[RuleSource] | None = None) -> AmendmentJobOut:
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
    )


@router.post(
    "/upload",
    response_model=AmendmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_amendment(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AmendmentUploadResponse:
    content = await file.read()
    try:
        result = store_amendment_pdf(
            db=db,
            content=content,
            filename=file.filename or "amendment.pdf",
            content_type=file.content_type,
        )
        db.commit()
        db.refresh(result.job)
    except AmendmentStorageError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
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
    db: Session = Depends(get_db),
) -> AmendmentExtractResponse:
    try:
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
    except Exception:
        db.rollback()
        raise

    return AmendmentExtractResponse(
        job=_job_out(result.job, result.rule_sources),
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
    db: Session = Depends(get_db),
) -> AmendmentJobOut:
    job = db.get(AmendmentJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amendment job not found")
    rules = get_job_rule_sources(db, job.id)
    return _job_out(job, rules)


@router.post("/{job_id}/approve", response_model=AmendmentApproveResponse)
def approve_amendment_endpoint(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> AmendmentApproveResponse:
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
        )
    else:
        override_out = ParamOverrideStubOut(written=False)

    return AmendmentApproveResponse(
        job=_job_out(result.job, result.rule_sources),
        rule_version_ids=[v.id for v in result.rule_versions],
        merge=MergeStubOut(
            merged=result.merge.merged,
            reason=result.merge.reason,
            amendment_job_id=result.merge.amendment_job_id,
            details=result.merge.details,
        ),
        param_override=override_out,
    )


@router.post("/{job_id}/reject", response_model=AmendmentRejectResponse)
def reject_amendment_endpoint(
    job_id: UUID,
    body: RejectAmendmentRequest,
    db: Session = Depends(get_db),
) -> AmendmentRejectResponse:
    try:
        result = reject_amendment(db=db, job_id=job_id, reason=body.reason)
    except AmendmentReviewError as exc:
        detail = str(exc)
        code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc

    return AmendmentRejectResponse(job=_job_out(result.job, result.rule_sources))
