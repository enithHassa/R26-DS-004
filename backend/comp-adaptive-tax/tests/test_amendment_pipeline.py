"""Orchestration tests for amendment pipeline (mocked DB / PDF / GPT)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz
import pytest

from adaptive_tax_app.db_loader import (
    AmendmentExtractRun,
    AmendmentExtractRunStatus,
    AmendmentJob,
    AmendmentJobStatus,
    RuleSource,
    RuleSourceStatus,
    RuleType,
)
from adaptive_tax_app.merge.amendment_merge import merge_approved_amendment
from adaptive_tax_app.schemas.amendments import AmendmentJobOut, RuleSourceOut
from adaptive_tax_app.services.extraction import (
    AmendmentExtractError,
    persist_extracted_rules,
    run_amendment_extraction,
)
from adaptive_tax_app.services.gpt_extract import ExtractionResult, load_fixture_rules
from adaptive_tax_app.services.pdf_extract import FocusedAmendmentText
from adaptive_tax_app.services.storage import AmendmentStorageError, validate_pdf_bytes


def _make_pdf(path: Path, text: str = "Section 52 of the principal enactment is hereby amended.") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_upload_validation_empty_and_non_pdf() -> None:
    with pytest.raises(AmendmentStorageError, match="empty"):
        validate_pdf_bytes(b"")
    with pytest.raises(AmendmentStorageError, match="not a PDF"):
        validate_pdf_bytes(b"hello", filename="x.pdf")


def test_merge_offline_without_password_does_not_raise() -> None:
    job_id = uuid.uuid4()
    rule = RuleSource(
        amendment_job_id=job_id,
        sort_order=0,
        section="52",
        rule_type=RuleType.LIMIT,
        maximum=1_800_000.0,
        amends_section="52",
        source_quote="quote",
        status=RuleSourceStatus.APPROVED,
    )
    rule.id = uuid.uuid4()
    db = MagicMock()
    db.get.return_value = MagicMock(original_filename="IR_Act_No_02-2025_E.pdf")
    with patch(
        "adaptive_tax_app.merge.amendment_merge.get_adaptive_tax_settings"
    ) as settings_fn:
        settings = MagicMock()
        settings.NEO4J_PASSWORD = ""
        settings.NEO4J_URI = "bolt://127.0.0.1:7687"
        settings.NEO4J_USER = "neo4j"
        settings_fn.return_value = settings
        result = merge_approved_amendment(
            db=db,
            amendment_job_id=job_id,
            rule_sources=[rule],
        )
    assert result.merged is False
    assert result.reason == "neo4j_unavailable"
    assert result.amendment_job_id == job_id
    assert result.details is not None
    assert len(result.details["rule_source_ids"]) == 1


def test_persist_rule_source_rows_include_source_quote() -> None:
    rules = load_fixture_rules()
    assert all(r.source_quote for r in rules)

    job = AmendmentJob(
        original_filename="act.pdf",
        content_type="application/pdf",
        size_bytes=1,
        file_hash="hash",
        storage_path="/tmp/a.pdf",
        status=AmendmentJobStatus.EXTRACTING,
    )
    job.id = uuid.uuid4()
    run = AmendmentExtractRun(
        amendment_job_id=job.id,
        model_name="fixture:test",
        status=AmendmentExtractRunStatus.STARTED,
    )
    run.id = uuid.uuid4()

    db = MagicMock()
    rows = persist_extracted_rules(db=db, job=job, extract_run=run, rules=rules)

    assert job.extracted_rules is not None
    assert "rules" in job.extracted_rules
    assert len(rows) == len(rules)
    for row, rule in zip(rows, rules, strict=True):
        assert row.status == RuleSourceStatus.PENDING
        assert row.source_quote == rule.source_quote
        assert len(row.source_quote) >= 20
        assert row.section == rule.section


def test_get_payload_shape_matches_api_schema() -> None:
    job_id = uuid.uuid4()
    rule = RuleSourceOut(
        id=uuid.uuid4(),
        amendment_job_id=job_id,
        extract_run_id=uuid.uuid4(),
        sort_order=0,
        section="52",
        paragraph=None,
        rule_type="limit",
        concept_id="qualifying_payment_cap",
        condition=None,
        formula=None,
        threshold=None,
        maximum=1_800_000.0,
        effective_date=date(2025, 4, 1),
        amends_section="52",
        source_quote="Section 52 of the principal enactment is hereby amended by substitution.",
        status="pending",
        created_at=None,
    )
    payload = AmendmentJobOut(
        id=job_id,
        original_filename="IR_Act_No_02-2025_E.pdf",
        content_type="application/pdf",
        size_bytes=100,
        file_hash="abc123",
        storage_path="/tmp/x.pdf",
        status="extracted",
        extracted_rules={"rules": [rule.model_dump(mode="json")]},
        rejection_reason=None,
        rule_sources=[rule],
    )
    dumped = payload.model_dump(mode="json")
    assert dumped["status"] == "extracted"
    assert dumped["rule_sources"][0]["source_quote"]
    assert dumped["rule_sources"][0]["section"] == "52"
    assert dumped["extracted_rules"]["rules"][0]["maximum"] == 1_800_000.0


def test_run_extraction_orchestration_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adaptive_tax_app.config import get_adaptive_tax_settings

    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "fixture")
    get_adaptive_tax_settings.cache_clear()

    pdf_path = _make_pdf(tmp_path / "amendment.pdf")
    job = AmendmentJob(
        original_filename="amendment.pdf",
        content_type="application/pdf",
        size_bytes=pdf_path.stat().st_size,
        file_hash="deadbeef",
        storage_path=str(pdf_path),
        status=AmendmentJobStatus.UPLOADED,
    )
    job.id = uuid.uuid4()

    db = MagicMock()
    db.get.return_value = job

    # Capture extract_run / rule_source objects added to the session.
    added: list[object] = []

    def _add(obj: object) -> None:
        if isinstance(obj, AmendmentExtractRun) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        added.append(obj)

    db.add.side_effect = _add

    focused = FocusedAmendmentText(
        full_text="full",
        focused_text="Section 52 of the principal enactment is hereby amended.",
        amends_section_candidates=["52"],
        page_count=1,
        truncated=False,
        char_count_full=10,
        char_count_focused=10,
    )
    fixture_rules = load_fixture_rules()
    extraction = ExtractionResult(
        rules=fixture_rules,
        model_name="fixture:section52_extract_sample",
        mode="fixture",
        warnings=[],
        metrics={"rule_count": len(fixture_rules)},
    )

    with (
        patch(
            "adaptive_tax_app.services.extraction.extract_focused_amendment_text",
            return_value=focused,
        ),
        patch(
            "adaptive_tax_app.services.extraction.extract_rules",
            return_value=extraction,
        ),
    ):
        result = run_amendment_extraction(db=db, job_id=job.id)

    assert result.job.status == AmendmentJobStatus.EXTRACTED
    assert result.extraction.mode == "fixture"
    assert len(result.rule_sources) == len(fixture_rules)
    assert all(r.source_quote for r in result.rule_sources)
    assert result.job.extracted_rules is not None
    assert result.extract_run.status == AmendmentExtractRunStatus.COMPLETED
    get_adaptive_tax_settings.cache_clear()


def test_run_extraction_rejects_wrong_status() -> None:
    job = AmendmentJob(
        original_filename="a.pdf",
        content_type="application/pdf",
        size_bytes=1,
        file_hash="x",
        storage_path="/tmp/missing.pdf",
        status=AmendmentJobStatus.APPROVED,
    )
    job.id = uuid.uuid4()
    db = MagicMock()
    db.get.return_value = job

    with pytest.raises(AmendmentExtractError, match="Cannot extract"):
        run_amendment_extraction(db=db, job_id=job.id)


def test_approve_and_reject_paths_covered_via_review_module() -> None:
    """Smoke import — detailed cases live in test_amendment_review.py."""
    from adaptive_tax_app.services import amendment_review

    assert callable(amendment_review.approve_amendment)
    assert callable(amendment_review.reject_amendment)
