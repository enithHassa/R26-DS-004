"""Approve / reject amendment jobs after extraction review."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

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
    write_sec52_override_from_rules,
)


class AmendmentReviewError(RuntimeError):
    """Raised when approve/reject cannot proceed."""


@dataclass
class ApproveAmendmentResult:
    job: AmendmentJob
    rule_sources: list[RuleSource]
    rule_versions: list[RuleVersion]
    merge: AmendmentMergeResult
    param_override: ParamOverrideWriteResult | None = None


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

    now = datetime.now(timezone.utc)
    versions: list[RuleVersion] = []
    for rule in pending:
        rule.status = RuleSourceStatus.APPROVED
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

    # Phase 4: live Sec 52 cap for calculate (independent of Neo4j merge success).
    param_override = write_sec52_override_from_rules(
        pending,
        amendment_job_id=job.id,
    )

    return ApproveAmendmentResult(
        job=job,
        rule_sources=pending,
        rule_versions=versions,
        merge=merge,
        param_override=param_override,
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
