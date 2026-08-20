"""Approve / reject amendment jobs after extraction review."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings

from adaptive_tax_app.db_loader import (
    AmendmentJob,
    AmendmentJobStatus,
    RuleSource,
    RuleSourceStatus,
    RuleVersion,
)
from adaptive_tax_app.merge.amendment_merge import (
    AmendmentMergeResult,
    merge_approved_amendment,
)
from adaptive_tax_app.services.extraction import get_job_rule_sources
from adaptive_tax_app.services.param_store import (
    ParamOverrideWriteResult,
    RateBandOverrideWriteResult,
    write_donation_cap_override_from_rules,
    write_personal_relief_override_from_rules,
    write_rate_band_override_from_rules,
    write_sec52_override_from_rules,
)

if TYPE_CHECKING:
    from adaptive_tax_app.services.amendment_file_store import (
        FileRuleSourceAdapter,
        FileRuleVersionAdapter,
        StoredAmendmentJob,
        StoredRuleSourceRecord,
    )


class AmendmentReviewError(RuntimeError):
    """Raised when approve/reject cannot proceed."""


_PHASE5_PARAM_KEYS = (
    "assessment_years",
    "executable",
    "engine_handler",
    "schedule_ref",
    "cross_refs",
    "applies_to_taxpayer",
    "relationship_hints",
)


def _phase5_fields_from_job(job: AmendmentJob, sort_order: int) -> dict:
    """Pull Phase 5.0 additive fields from job.extracted_rules JSONB."""
    raw = job.extracted_rules if isinstance(job.extracted_rules, dict) else {}
    rules = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    if sort_order < 0 or sort_order >= len(rules):
        return {}
    row = rules[sort_order]
    if not isinstance(row, dict):
        return {}
    out: dict = {}
    for key in _PHASE5_PARAM_KEYS:
        if key in row and row[key] is not None:
            out[key] = row[key]
    # Provenance: stamp source_doc_id from harvest envelope when present.
    if raw.get("source_doc_id"):
        out["source_doc_id"] = raw["source_doc_id"]
    return out


@dataclass
class ApproveAmendmentResult:
    job: AmendmentJob
    rule_sources: list[RuleSource]
    rule_versions: list[RuleVersion]
    merge: AmendmentMergeResult
    param_override: ParamOverrideWriteResult | None = None
    rate_override: RateBandOverrideWriteResult | None = None
    personal_relief_override: ParamOverrideWriteResult | None = None
    donation_cap_override: ParamOverrideWriteResult | None = None


@dataclass
class RejectAmendmentResult:
    job: AmendmentJob
    rule_sources: list[RuleSource]


def approve_amendment(*, db: Session, job_id: uuid.UUID) -> ApproveAmendmentResult:
    job = db.get(AmendmentJob, job_id)
    if job is None:
        raise AmendmentReviewError(f"Amendment job not found: {job_id}")
    if job.status != AmendmentJobStatus.EXTRACTED:
        raise AmendmentReviewError(
            f"Approve only allowed from status=extracted (got {job.status.value!r})"
        )

    rules = get_job_rule_sources(db, job.id)
    pending = [r for r in rules if r.status == RuleSourceStatus.PENDING]
    if not pending:
        raise AmendmentReviewError("No pending rule_source rows to approve")

    # Phase 5.0 provenance gate: never approve empty section / source_quote.
    for rule in pending:
        if not (rule.section or "").strip():
            raise AmendmentReviewError(
                f"Cannot approve rule_source {rule.id}: section is empty"
            )
        if not (rule.source_quote or "").strip() or len(rule.source_quote.strip()) < 20:
            raise AmendmentReviewError(
                f"Cannot approve rule_source {rule.id}: source_quote missing or too short"
            )

    now = datetime.now(timezone.utc)
    versions: list[RuleVersion] = []
    for rule in pending:
        rule.status = RuleSourceStatus.APPROVED
        # Prefer Phase 5 fields from job.extracted_rules JSON when present.
        extra = _phase5_fields_from_job(job, rule.sort_order)
        params = {
            "section": rule.section,
            "paragraph": rule.paragraph,
            "rule_type": rule.rule_type.value if rule.rule_type is not None else None,
            "concept_id": rule.concept_id,
            "condition": rule.condition,
            "formula": rule.formula,
            "threshold": rule.threshold,
            "maximum": rule.maximum,
            "effective_date": rule.effective_date.isoformat() if rule.effective_date else None,
            "amends_section": rule.amends_section,
            "source_quote": rule.source_quote,
            **extra,
        }
        version = RuleVersion(
            rule_source_id=rule.id,
            amendment_job_id=job.id,
            version=1,
            params=params,
        )
        db.add(version)
        versions.append(version)

    job.status = AmendmentJobStatus.APPROVED
    job.reviewed_at = now
    job.updated_at = now
    job.rejection_reason = None
    db.flush()

    merge = merge_approved_amendment(
        db=db,
        amendment_job_id=job.id,
        rule_sources=pending,
        rule_versions=versions,
    )
    db.commit()
    db.refresh(job)
    for row in pending:
        db.refresh(row)
    for version in versions:
        db.refresh(version)

    # Phase 4/5.2: live Sec 52 + First Schedule rate provenance for calculate.
    param_override = write_sec52_override_from_rules(
        pending,
        amendment_job_id=job.id,
    )
    rate_override = write_rate_band_override_from_rules(
        pending,
        amendment_job_id=job.id,
    )
    personal_relief_override = write_personal_relief_override_from_rules(
        pending,
        amendment_job_id=job.id,
    )
    donation_cap_override = write_donation_cap_override_from_rules(
        pending,
        amendment_job_id=job.id,
    )

    return ApproveAmendmentResult(
        job=job,
        rule_sources=pending,
        rule_versions=versions,
        merge=merge,
        param_override=param_override,
        rate_override=rate_override,
        personal_relief_override=personal_relief_override,
        donation_cap_override=donation_cap_override,
    )


def reject_amendment(
    *,
    db: Session,
    job_id: uuid.UUID,
    reason: str,
) -> RejectAmendmentResult:
    cleaned = reason.strip()
    if not cleaned:
        raise AmendmentReviewError("rejection reason is required")

    job = db.get(AmendmentJob, job_id)
    if job is None:
        raise AmendmentReviewError(f"Amendment job not found: {job_id}")
    if job.status != AmendmentJobStatus.EXTRACTED:
        raise AmendmentReviewError(
            f"Reject only allowed from status=extracted (got {job.status.value!r})"
        )

    rules = get_job_rule_sources(db, job.id)
    pending = [r for r in rules if r.status == RuleSourceStatus.PENDING]
    now = datetime.now(timezone.utc)
    for rule in pending:
        rule.status = RuleSourceStatus.REJECTED

    job.status = AmendmentJobStatus.REJECTED
    job.rejection_reason = cleaned
    job.reviewed_at = now
    job.updated_at = now
    db.commit()
    db.refresh(job)
    for row in pending:
        db.refresh(row)

    return RejectAmendmentResult(job=job, rule_sources=list(rules))


@dataclass
class ApproveAmendmentFileResult:
    job: "StoredAmendmentJob"
    rule_sources: list[FileRuleSourceAdapter]
    rule_versions: list[FileRuleVersionAdapter]
    merge: AmendmentMergeResult
    param_override: ParamOverrideWriteResult | None = None
    rate_override: RateBandOverrideWriteResult | None = None
    personal_relief_override: ParamOverrideWriteResult | None = None
    donation_cap_override: ParamOverrideWriteResult | None = None


@dataclass
class RejectAmendmentFileResult:
    job: "StoredAmendmentJob"
    rule_sources: list[StoredRuleSourceRecord]


def approve_amendment_file(
    *,
    job_id: uuid.UUID,
    settings: AdaptiveTaxSettings | None = None,
) -> ApproveAmendmentFileResult:
    from adaptive_tax_app.services.amendment_file_store import (
        StoredRuleVersionRecord,
        load_job,
        phase5_fields_from_stored_job,
        rule_source_adapters,
        rule_version_adapters,
        save_job,
    )

    cfg = settings or get_adaptive_tax_settings()
    job = load_job(job_id, settings=cfg)
    if job is None:
        raise AmendmentReviewError(f"Amendment job not found: {job_id}")
    if job.status != AmendmentJobStatus.EXTRACTED.value:
        raise AmendmentReviewError(
            f"Approve only allowed from status=extracted (got {job.status!r})"
        )

    pending_records = [r for r in job.rule_sources if r.status == RuleSourceStatus.PENDING.value]
    if not pending_records:
        raise AmendmentReviewError("No pending rule_source rows to approve")

    for rule in pending_records:
        if not (rule.section or "").strip():
            raise AmendmentReviewError(
                f"Cannot approve rule_source {rule.id}: section is empty"
            )
        if not (rule.source_quote or "").strip() or len(rule.source_quote.strip()) < 20:
            raise AmendmentReviewError(
                f"Cannot approve rule_source {rule.id}: source_quote missing or too short"
            )

    now = datetime.now(timezone.utc)
    versions: list[StoredRuleVersionRecord] = []
    for rule in pending_records:
        rule.status = RuleSourceStatus.APPROVED.value
        extra = phase5_fields_from_stored_job(job, rule.sort_order)
        params = {
            "section": rule.section,
            "paragraph": rule.paragraph,
            "rule_type": rule.rule_type,
            "concept_id": rule.concept_id,
            "condition": rule.condition,
            "formula": rule.formula,
            "threshold": rule.threshold,
            "maximum": rule.maximum,
            "effective_date": rule.effective_date.isoformat() if rule.effective_date else None,
            "amends_section": rule.amends_section,
            "source_quote": rule.source_quote,
            **extra,
        }
        version = StoredRuleVersionRecord(
            id=uuid.uuid4(),
            rule_source_id=rule.id,
            amendment_job_id=job.id,
            version=1,
            params=params,
            created_at=now,
        )
        job.rule_versions.append(version)
        versions.append(version)

    job.status = AmendmentJobStatus.APPROVED.value
    job.reviewed_at = now
    job.updated_at = now
    job.rejection_reason = None
    save_job(job, settings=cfg)

    adapters = rule_source_adapters(job)
    pending_adapters = [a for a in adapters if a.status == RuleSourceStatus.APPROVED]
    version_adapters = rule_version_adapters(job)

    merge = merge_approved_amendment(
        db=None,
        amendment_job_id=job.id,
        rule_sources=pending_adapters,  # type: ignore[arg-type]
        rule_versions=version_adapters,  # type: ignore[arg-type]
        original_filename=job.original_filename,
    )

    param_override = write_sec52_override_from_rules(
        pending_adapters,
        amendment_job_id=job.id,
    )
    rate_override = write_rate_band_override_from_rules(
        pending_adapters,
        amendment_job_id=job.id,
    )
    personal_relief_override = write_personal_relief_override_from_rules(
        pending_adapters,
        amendment_job_id=job.id,
    )
    donation_cap_override = write_donation_cap_override_from_rules(
        pending_adapters,
        amendment_job_id=job.id,
    )

    return ApproveAmendmentFileResult(
        job=job,
        rule_sources=pending_adapters,
        rule_versions=version_adapters,
        merge=merge,
        param_override=param_override,
        rate_override=rate_override,
        personal_relief_override=personal_relief_override,
        donation_cap_override=donation_cap_override,
    )


def reject_amendment_file(
    *,
    job_id: uuid.UUID,
    reason: str,
    settings: AdaptiveTaxSettings | None = None,
) -> RejectAmendmentFileResult:
    from adaptive_tax_app.services.amendment_file_store import load_job, save_job

    cleaned = reason.strip()
    if not cleaned:
        raise AmendmentReviewError("rejection reason is required")

    cfg = settings or get_adaptive_tax_settings()
    job = load_job(job_id, settings=cfg)
    if job is None:
        raise AmendmentReviewError(f"Amendment job not found: {job_id}")
    if job.status != AmendmentJobStatus.EXTRACTED.value:
        raise AmendmentReviewError(
            f"Reject only allowed from status=extracted (got {job.status!r})"
        )

    now = datetime.now(timezone.utc)
    for rule in job.rule_sources:
        if rule.status == RuleSourceStatus.PENDING.value:
            rule.status = RuleSourceStatus.REJECTED.value

    job.status = AmendmentJobStatus.REJECTED.value
    job.rejection_reason = cleaned
    job.reviewed_at = now
    job.updated_at = now
    save_job(job, settings=cfg)

    return RejectAmendmentFileResult(job=job, rule_sources=list(job.rule_sources))
