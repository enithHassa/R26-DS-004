"""API request/response models for admin amendment endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AmendmentUploadResponse(BaseModel):
    id: UUID
    original_filename: str
    file_hash: str
    storage_path: str
    size_bytes: int
    status: str
    duplicate_hash_warning: str | None = None


class RuleSourceOut(BaseModel):
    id: UUID
    amendment_job_id: UUID
    extract_run_id: UUID | None = None
    sort_order: int
    section: str
    paragraph: str | None = None
    rule_type: str
    concept_id: str | None = None
    condition: str | None = None
    formula: str | None = None
    threshold: float | None = None
    maximum: float | None = None
    effective_date: date | None = None
    amends_section: str | None = None
    source_quote: str
    status: str
    created_at: datetime | None = None


class ExtractRunOut(BaseModel):
    """Latest extract-run audit row for viva / admin review."""

    id: UUID
    amendment_job_id: UUID
    model_name: str
    prompt_version: str | None = None
    status: str
    mode: str | None = None
    warnings: list[str] | dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    audit_payload: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AmendmentJobOut(BaseModel):
    id: UUID
    original_filename: str
    content_type: str | None = None
    size_bytes: int
    file_hash: str
    storage_path: str
    status: str
    extracted_rules: dict[str, Any] | list[Any] | None = None
    rejection_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    extracted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rule_sources: list[RuleSourceOut] = Field(default_factory=list)
    latest_extract_run: ExtractRunOut | None = None


class AmendmentExtractResponse(BaseModel):
    job: AmendmentJobOut
    extract_run_id: UUID
    mode: str
    model_name: str
    rule_count: int
    warnings: list[str] = Field(default_factory=list)
    amends_section_candidates: list[str] = Field(default_factory=list)


class RejectAmendmentRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class MergeStubOut(BaseModel):
    merged: bool
    reason: str
    amendment_job_id: UUID
    details: dict[str, Any] | None = None


class ParamOverrideStubOut(BaseModel):
    """Runtime override written on approve (Sec 52 and/or First Schedule rates)."""

    written: bool
    source: str | None = None
    path: str | None = None
    concept_id: str | None = None
    cap_amount: str | None = None
    rule_source_id: str | None = None
    amendment_job_id: str | None = None
    kind: str | None = Field(
        default=None,
        description="relief | rate — which override payload was written.",
    )
    band_update_count: int | None = None
    assessment_years: list[str] | None = None


class AmendmentApproveResponse(BaseModel):
    job: AmendmentJobOut
    rule_version_ids: list[UUID]
    merge: MergeStubOut
    param_override: ParamOverrideStubOut | None = None
    rate_override: ParamOverrideStubOut | None = None


class AmendmentRejectResponse(BaseModel):
    job: AmendmentJobOut
    status: Literal["rejected"] = "rejected"
