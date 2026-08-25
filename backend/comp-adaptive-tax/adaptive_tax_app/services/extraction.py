"""Orchestrate PDF focus → GPT/fixture extract → PostgreSQL persist."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.db_loader import (
    AmendmentExtractRun,
    AmendmentExtractRunStatus,
    AmendmentJob,
    AmendmentJobStatus,
    RuleSource,
    RuleSourceStatus,
    RuleType,
)
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule, classify_extracted_rules
from adaptive_tax_app.services.gpt_extract import (
    ExtractionError,
    ExtractionResult,
    extract_rules,
)
from adaptive_tax_app.services.pdf_extract import (
    FocusedAmendmentText,
    extract_focused_amendment_text,
)


class AmendmentExtractError(RuntimeError):
    """Raised when an amendment job cannot be extracted."""


@dataclass
class PersistExtractionResult:
    job: AmendmentJob
    extract_run: AmendmentExtractRun
    rule_sources: list[RuleSource]
    focused: FocusedAmendmentText
    extraction: ExtractionResult


def run_amendment_extraction(
    *,
    db: Session,
    job_id: uuid.UUID,
) -> PersistExtractionResult:
    """Extract rules for an uploaded amendment job and persist review rows."""
    job = db.get(AmendmentJob, job_id)
    if job is None:
        raise AmendmentExtractError(f"Amendment job not found: {job_id}")

    allowed = {
        AmendmentJobStatus.UPLOADED,
        AmendmentJobStatus.FAILED,
        AmendmentJobStatus.EXTRACTED,
    }
    if job.status not in allowed:
        raise AmendmentExtractError(
            f"Cannot extract job in status={job.status.value!r}; "
            f"allowed={[s.value for s in allowed]}"
        )

    pdf_path = Path(job.storage_path)
    if not pdf_path.is_file():
        raise AmendmentExtractError(f"Stored PDF missing: {pdf_path}")

    settings = get_adaptive_tax_settings()
    job.status = AmendmentJobStatus.EXTRACTING
    job.updated_at = datetime.now(timezone.utc)
    db.flush()

    extract_run = AmendmentExtractRun(
        amendment_job_id=job.id,
        model_name="pending",
        prompt_version=None,
        status=AmendmentExtractRunStatus.STARTED,
    )
    db.add(extract_run)
    db.flush()

    try:
        focused = extract_focused_amendment_text(pdf_path)
        extraction = extract_rules(
            focused.focused_text,
            amends_section_candidates=focused.amends_section_candidates,
            settings=settings,
        )
        rule_sources = persist_extracted_rules(
            db=db,
            job=job,
            extract_run=extract_run,
            rules=extraction.rules,
        )
        extract_run.model_name = extraction.model_name
        extract_run.prompt_version = extraction.prompt_version
        extract_run.status = AmendmentExtractRunStatus.COMPLETED
        extract_run.finished_at = datetime.now(timezone.utc)
        extract_run.warnings = {"messages": extraction.warnings} if extraction.warnings else None
        extract_run.metrics = {
            **extraction.metrics,
            "page_count": focused.page_count,
            "char_count_full": focused.char_count_full,
            "char_count_focused": focused.char_count_focused,
            "truncated": focused.truncated,
            "amends_section_candidates": focused.amends_section_candidates,
            "mode": extraction.mode,
        }
        extract_run.audit_payload = extraction.audit or None
        job.status = AmendmentJobStatus.EXTRACTED
        job.extracted_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        job.rejection_reason = None
        db.flush()
        return PersistExtractionResult(
            job=job,
            extract_run=extract_run,
            rule_sources=rule_sources,
            focused=focused,
            extraction=extraction,
        )
    except (ExtractionError, OSError, ValueError, SQLAlchemyError) as exc:
        extract_run.status = AmendmentExtractRunStatus.FAILED
        extract_run.error_message = str(exc)
        extract_run.finished_at = datetime.now(timezone.utc)
        job.status = AmendmentJobStatus.FAILED
        job.updated_at = datetime.now(timezone.utc)
        db.flush()
        raise AmendmentExtractError(str(exc)) from exc


def persist_extracted_rules(
    *,
    db: Session,
    job: AmendmentJob,
    extract_run: AmendmentExtractRun,
    rules: list[ExtractedRule],
) -> list[RuleSource]:
    """Replace prior pending rule_source rows and store JSONB on the job."""
    # Drop previous pending rows for this job (re-extract). Keep approved history none yet.
    db.execute(
        delete(RuleSource).where(
            RuleSource.amendment_job_id == job.id,
            RuleSource.status == RuleSourceStatus.PENDING,
        )
    )

    classified = classify_extracted_rules(rules)
    payload = [rule.model_dump(mode="json") for rule in classified]
    job.extracted_rules = {"rules": payload}

    created: list[RuleSource] = []
    for idx, rule in enumerate(classified):
        row = RuleSource(
            amendment_job_id=job.id,
            extract_run_id=extract_run.id,
            sort_order=idx,
            section=rule.section,
            paragraph=rule.paragraph,
            rule_type=RuleType(rule.rule_type),
            concept_id=rule.concept_id,
            condition=rule.condition,
            formula=rule.formula,
            threshold=rule.threshold,
            maximum=rule.maximum,
            effective_date=rule.effective_date,
            amends_section=rule.amends_section,
            source_quote=rule.source_quote,
            status=RuleSourceStatus.PENDING,
        )
        db.add(row)
        created.append(row)

    db.flush()
    return created


def get_job_rule_sources(db: Session, job_id: uuid.UUID) -> list[RuleSource]:
    return list(
        db.scalars(
            select(RuleSource)
            .where(RuleSource.amendment_job_id == job_id)
            .order_by(RuleSource.sort_order.asc(), RuleSource.created_at.asc())
        ).all()
    )


def get_latest_extract_run(db: Session, job_id: uuid.UUID) -> AmendmentExtractRun | None:
    """Most recent extract run for a job (completed or failed)."""
    return db.scalars(
        select(AmendmentExtractRun)
        .where(AmendmentExtractRun.amendment_job_id == job_id)
        .order_by(AmendmentExtractRun.started_at.desc())
        .limit(1)
    ).first()


@dataclass
class FilePersistExtractionResult:
    job: "StoredAmendmentJob"
    extract_run: "StoredExtractRunRecord"
    rule_sources: list["StoredRuleSourceRecord"]
    focused: FocusedAmendmentText
    extraction: ExtractionResult


def run_amendment_extraction_file(
    *,
    job_id: uuid.UUID,
    settings: AdaptiveTaxSettings | None = None,
) -> FilePersistExtractionResult:
    """Extract rules for a file-store job and persist into JSON."""
    from adaptive_tax_app.services.amendment_file_store import (
        StoredAmendmentJob,
        StoredExtractRunRecord,
        StoredRuleSourceRecord,
        load_job,
        save_job,
    )

    cfg = settings or get_adaptive_tax_settings()
    job = load_job(job_id, settings=cfg)
    if job is None:
        raise AmendmentExtractError(f"Amendment job not found: {job_id}")

    allowed = {
        AmendmentJobStatus.UPLOADED.value,
        AmendmentJobStatus.FAILED.value,
        AmendmentJobStatus.EXTRACTED.value,
    }
    if job.status not in allowed:
        raise AmendmentExtractError(
            f"Cannot extract job in status={job.status!r}; allowed={sorted(allowed)}"
        )

    pdf_path = Path(job.storage_path)
    if not pdf_path.is_file():
        raise AmendmentExtractError(f"Stored PDF missing: {pdf_path}")

    now = datetime.now(timezone.utc)
    job.status = AmendmentJobStatus.EXTRACTING.value
    job.updated_at = now

    extract_run = StoredExtractRunRecord(
        id=uuid.uuid4(),
        amendment_job_id=job.id,
        model_name="pending",
        status=AmendmentExtractRunStatus.STARTED.value,
        started_at=now,
    )
    job.extract_runs.append(extract_run)
    save_job(job, settings=cfg)

    try:
        focused = extract_focused_amendment_text(pdf_path)
        extraction = extract_rules(
            focused.focused_text,
            amends_section_candidates=focused.amends_section_candidates,
            settings=cfg,
        )
        classified = classify_extracted_rules(extraction.rules)
        payload = [rule.model_dump(mode="json") for rule in classified]
        job.extracted_rules = {"rules": payload}

        job.rule_sources = [
            row
            for row in job.rule_sources
            if row.status != RuleSourceStatus.PENDING.value
        ]
        created: list[StoredRuleSourceRecord] = []
        for idx, rule in enumerate(classified):
            row = StoredRuleSourceRecord(
                id=uuid.uuid4(),
                amendment_job_id=job.id,
                extract_run_id=extract_run.id,
                sort_order=idx,
                section=rule.section,
                paragraph=rule.paragraph,
                rule_type=rule.rule_type,
                concept_id=rule.concept_id,
                condition=rule.condition,
                formula=rule.formula,
                threshold=rule.threshold,
                maximum=rule.maximum,
                effective_date=rule.effective_date,
                amends_section=rule.amends_section,
                source_quote=rule.source_quote,
                status=RuleSourceStatus.PENDING.value,
                created_at=now,
            )
            job.rule_sources.append(row)
            created.append(row)

        extract_run.model_name = extraction.model_name
        extract_run.prompt_version = extraction.prompt_version
        extract_run.status = AmendmentExtractRunStatus.COMPLETED.value
        extract_run.finished_at = datetime.now(timezone.utc)
        extract_run.warnings = (
            {"messages": extraction.warnings} if extraction.warnings else None
        )
        extract_run.metrics = {
            **extraction.metrics,
            "page_count": focused.page_count,
            "char_count_full": focused.char_count_full,
            "char_count_focused": focused.char_count_focused,
            "truncated": focused.truncated,
            "amends_section_candidates": focused.amends_section_candidates,
            "mode": extraction.mode,
        }
        extract_run.audit_payload = extraction.audit or None

        job.status = AmendmentJobStatus.EXTRACTED.value
        job.extracted_at = datetime.now(timezone.utc)
        job.updated_at = job.extracted_at
        job.rejection_reason = None
        save_job(job, settings=cfg)

        return FilePersistExtractionResult(
            job=job,
            extract_run=extract_run,
            rule_sources=created,
            focused=focused,
            extraction=extraction,
        )
    except (ExtractionError, OSError, ValueError) as exc:
        extract_run.status = AmendmentExtractRunStatus.FAILED.value
        extract_run.error_message = str(exc)
        extract_run.finished_at = datetime.now(timezone.utc)
        job.status = AmendmentJobStatus.FAILED.value
        job.updated_at = datetime.now(timezone.utc)
        save_job(job, settings=cfg)
        raise AmendmentExtractError(str(exc)) from exc

