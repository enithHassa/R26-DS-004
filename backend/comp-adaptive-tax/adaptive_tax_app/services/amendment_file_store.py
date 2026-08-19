"""File-based amendment job store (JSON on disk) — temporary demo without PostgreSQL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.db_loader import AmendmentJobStatus, RuleSourceStatus, RuleType
from adaptive_tax_app.services.storage import (
    AmendmentStorageError,
    build_storage_path,
    sanitize_filename,
    sha256_hex,
    validate_pdf_bytes,
)


class AmendmentFileStoreError(RuntimeError):
    """Raised when a file-store amendment operation fails."""


class StoredRuleSourceRecord(BaseModel):
    id: uuid.UUID
    amendment_job_id: uuid.UUID
    extract_run_id: uuid.UUID | None = None
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
    status: str = "pending"
    created_at: datetime


class StoredExtractRunRecord(BaseModel):
    id: uuid.UUID
    amendment_job_id: uuid.UUID
    model_name: str
    prompt_version: str | None = None
    status: str
    warnings: dict[str, Any] | list[str] | None = None
    metrics: dict[str, Any] | None = None
    audit_payload: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class StoredRuleVersionRecord(BaseModel):
    id: uuid.UUID
    rule_source_id: uuid.UUID
    amendment_job_id: uuid.UUID
    version: int = 1
    params: dict[str, Any]
    created_at: datetime


class StoredAmendmentJob(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str | None = None
    size_bytes: int
    file_hash: str
    storage_path: str
    status: str
    extracted_rules: dict[str, Any] | list[Any] | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    extracted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rule_sources: list[StoredRuleSourceRecord] = Field(default_factory=list)
    extract_runs: list[StoredExtractRunRecord] = Field(default_factory=list)
    rule_versions: list[StoredRuleVersionRecord] = Field(default_factory=list)


@dataclass
class FileRuleSourceAdapter:
    """ORM-shaped adapter for merge / param_store (file-mode approve)."""

    id: uuid.UUID
    amendment_job_id: uuid.UUID
    extract_run_id: uuid.UUID | None
    sort_order: int
    section: str
    paragraph: str | None
    rule_type: RuleType
    concept_id: str | None
    condition: str | None
    formula: str | None
    threshold: float | None
    maximum: float | None
    effective_date: date | None
    amends_section: str | None
    source_quote: str
    status: RuleSourceStatus
    created_at: datetime


@dataclass
class FileRuleVersionAdapter:
    id: uuid.UUID
    rule_source_id: uuid.UUID
    amendment_job_id: uuid.UUID
    version: int
    params: dict[str, Any]
    created_at: datetime


def _job_path(store_dir: Path, job_id: uuid.UUID) -> Path:
    store_dir = store_dir.resolve()
    path = (store_dir / f"{job_id}.json").resolve()
    if path.parent != store_dir:
        raise ValueError("job_id resolves outside store directory")
    return path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def save_job(
    job: StoredAmendmentJob,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> None:
    cfg = settings or get_adaptive_tax_settings()
    store_dir = cfg.amendment_store_dir
    store_dir.mkdir(parents=True, exist_ok=True)
    path = _job_path(store_dir, job.id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def load_job(
    job_id: uuid.UUID,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> StoredAmendmentJob | None:
    cfg = settings or get_adaptive_tax_settings()
    path = _job_path(cfg.amendment_store_dir, job_id)
    if not path.is_file():
        return None
    return StoredAmendmentJob.model_validate_json(path.read_text(encoding="utf-8"))


def list_jobs(*, settings: AdaptiveTaxSettings | None = None) -> list[StoredAmendmentJob]:
    cfg = settings or get_adaptive_tax_settings()
    store_dir = cfg.amendment_store_dir
    if not store_dir.is_dir():
        return []
    jobs: list[StoredAmendmentJob] = []
    for path in sorted(store_dir.glob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        try:
            jobs.append(StoredAmendmentJob.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — skip corrupt files
            continue
    return jobs


def find_duplicate_hash(
    file_hash: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> uuid.UUID | None:
    for job in list_jobs(settings=settings):
        if job.file_hash == file_hash:
            return job.id
    return None


@dataclass(frozen=True)
class FileStoreAmendmentResult:
    job: StoredAmendmentJob
    duplicate_hash_warning: str | None = None


def store_amendment_pdf_file(
    *,
    content: bytes,
    filename: str,
    content_type: str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> FileStoreAmendmentResult:
    """Write PDF to disk and create a JSON job record (status=uploaded)."""
    cfg = settings or get_adaptive_tax_settings()
    validate_pdf_bytes(content, filename=filename)

    job_id = uuid.uuid4()
    safe_name = sanitize_filename(filename or "amendment.pdf")
    file_hash = sha256_hex(content)
    storage_path = build_storage_path(
        upload_root=cfg.upload_root,
        job_id=job_id,
        safe_name=safe_name,
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    duplicate_warning: str | None = None
    existing = find_duplicate_hash(file_hash, settings=cfg)
    if existing is not None:
        duplicate_warning = (
            f"Duplicate file hash {file_hash[:12]}… already stored as job {existing}."
        )

    now = _utcnow()
    stored = StoredAmendmentJob(
        id=job_id,
        original_filename=Path(filename).name[:255] if filename else safe_name,
        content_type=content_type or "application/pdf",
        size_bytes=len(content),
        file_hash=file_hash,
        storage_path=str(storage_path),
        status=AmendmentJobStatus.UPLOADED.value,
        created_at=now,
        updated_at=now,
    )
    save_job(stored, settings=cfg)
    return FileStoreAmendmentResult(job=stored, duplicate_hash_warning=duplicate_warning)


def get_latest_extract_run(job: StoredAmendmentJob) -> StoredExtractRunRecord | None:
    if not job.extract_runs:
        return None
    return max(job.extract_runs, key=lambda r: r.started_at)


def rule_source_adapters(job: StoredAmendmentJob) -> list[FileRuleSourceAdapter]:
    return [_to_rule_adapter(row) for row in job.rule_sources]


def rule_version_adapters(job: StoredAmendmentJob) -> list[FileRuleVersionAdapter]:
    return [
        FileRuleVersionAdapter(
            id=row.id,
            rule_source_id=row.rule_source_id,
            amendment_job_id=row.amendment_job_id,
            version=row.version,
            params=row.params,
            created_at=row.created_at,
        )
        for row in job.rule_versions
    ]


def _to_rule_adapter(row: StoredRuleSourceRecord) -> FileRuleSourceAdapter:
    return FileRuleSourceAdapter(
        id=row.id,
        amendment_job_id=row.amendment_job_id,
        extract_run_id=row.extract_run_id,
        sort_order=row.sort_order,
        section=row.section,
        paragraph=row.paragraph,
        rule_type=RuleType(row.rule_type),
        concept_id=row.concept_id,
        condition=row.condition,
        formula=row.formula,
        threshold=row.threshold,
        maximum=row.maximum,
        effective_date=row.effective_date,
        amends_section=row.amends_section,
        source_quote=row.source_quote,
        status=RuleSourceStatus(row.status),
        created_at=row.created_at,
    )


def phase5_fields_from_stored_job(job: StoredAmendmentJob, sort_order: int) -> dict[str, Any]:
    raw = job.extracted_rules if isinstance(job.extracted_rules, dict) else {}
    rules = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    if sort_order < 0 or sort_order >= len(rules):
        return {}
    row = rules[sort_order]
    if not isinstance(row, dict):
        return {}
    keys = (
        "assessment_years",
        "executable",
        "engine_handler",
        "schedule_ref",
        "cross_refs",
        "applies_to_taxpayer",
        "relationship_hints",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if key in row and row[key] is not None:
            out[key] = row[key]
    if raw.get("source_doc_id"):
        out["source_doc_id"] = raw["source_doc_id"]
    return out
