"""Unit tests for approve / reject review service."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from adaptive_tax_app.db_loader import (
    AmendmentJob,
    AmendmentJobStatus,
    RuleSource,
    RuleSourceStatus,
    RuleType,
)
from adaptive_tax_app.services.amendment_review import (
    AmendmentReviewError,
    approve_amendment,
    reject_amendment,
)


def _job(status: AmendmentJobStatus) -> AmendmentJob:
    job = AmendmentJob(
        original_filename="act.pdf",
        content_type="application/pdf",
        size_bytes=10,
        file_hash="abc",
        storage_path="/tmp/act.pdf",
        status=status,
    )
    job.id = uuid.uuid4()
    return job


def _pending_rule(job_id: uuid.UUID) -> RuleSource:
    row = RuleSource(
        amendment_job_id=job_id,
        sort_order=0,
        section="52",
        rule_type=RuleType.LIMIT,
        maximum=1_800_000.0,
        effective_date=date(2025, 4, 1),
        amends_section="52",
        source_quote="Section 52 of the principal enactment is hereby amended by substitution.",
        status=RuleSourceStatus.PENDING,
    )
    row.id = uuid.uuid4()
    return row


def test_approve_requires_extracted_status() -> None:
    db = MagicMock()
    job = _job(AmendmentJobStatus.UPLOADED)
    db.get.return_value = job
    with pytest.raises(AmendmentReviewError, match="extracted"):
        approve_amendment(db=db, job_id=job.id)


def test_approve_creates_rule_versions_and_calls_merge() -> None:
    db = MagicMock()
    job = _job(AmendmentJobStatus.EXTRACTED)
    rule = _pending_rule(job.id)
    db.get.return_value = job

    with (
        patch(
            "adaptive_tax_app.services.amendment_review.get_job_rule_sources",
            return_value=[rule],
        ),
        patch(
            "adaptive_tax_app.services.amendment_review.merge_approved_amendment",
        ) as merge_fn,
    ):
        from adaptive_tax_app.merge.amendment_merge import AmendmentMergeResult

        merge_fn.return_value = AmendmentMergeResult(
            merged=False,
            reason="neo4j_unavailable",
            amendment_job_id=job.id,
            details={},
        )
        result = approve_amendment(db=db, job_id=job.id)

    assert job.status == AmendmentJobStatus.APPROVED
    assert rule.status == RuleSourceStatus.APPROVED
    assert len(result.rule_versions) == 1
    assert result.rule_versions[0].params["maximum"] == 1_800_000.0
    assert result.merge.merged is False
    assert result.merge.reason == "neo4j_unavailable"
    assert result.param_override is not None
    assert result.param_override.cap_amount == Decimal("1800000")
    merge_fn.assert_called_once()
    kwargs = merge_fn.call_args.kwargs
    assert kwargs["rule_sources"] == [rule]
    assert len(kwargs["rule_versions"]) == 1
    db.add.assert_called()
    db.commit.assert_called_once()


def test_reject_sets_reason_and_status() -> None:
    db = MagicMock()
    job = _job(AmendmentJobStatus.EXTRACTED)
    rule = _pending_rule(job.id)
    db.get.return_value = job

    with patch(
        "adaptive_tax_app.services.amendment_review.get_job_rule_sources",
        return_value=[rule],
    ):
        result = reject_amendment(db=db, job_id=job.id, reason=" quote mismatch ")

    assert result.job.status == AmendmentJobStatus.REJECTED
    assert result.job.rejection_reason == "quote mismatch"
    assert rule.status == RuleSourceStatus.REJECTED
    db.commit.assert_called_once()


def test_reject_requires_reason() -> None:
    db = MagicMock()
    with pytest.raises(AmendmentReviewError, match="reason"):
        reject_amendment(db=db, job_id=uuid.uuid4(), reason="   ")
