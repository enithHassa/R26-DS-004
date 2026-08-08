"""Amendment PDF filesystem storage + amendment_jobs row creation."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import AmendmentJob, AmendmentJobStatus

_PDF_MAGIC = b"%PDF"
_MAX_FILENAME_LEN = 180


class AmendmentStorageError(ValueError):
    """Raised when an upload cannot be stored (empty, non-PDF, etc.)."""


@dataclass(frozen=True)
class StoreAmendmentResult:
    job: AmendmentJob
    duplicate_hash_warning: str | None = None


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Keep a filesystem-safe basename; always ends with ``.pdf`` when possible.

    Slashes in names like ``Act No. 02/2025.pdf`` become underscores (not path seps).
    """
    base = filename.strip().replace("\x00", "")
    base = re.sub(r"[\\/]+", "_", base).replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", base) or "amendment.pdf"
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned[:_MAX_FILENAME_LEN]


def validate_pdf_bytes(content: bytes, *, filename: str | None = None) -> None:
    if not content:
        raise AmendmentStorageError("Uploaded file is empty.")
    if not content.lstrip().startswith(_PDF_MAGIC):
        raise AmendmentStorageError("Uploaded file is not a PDF (missing %PDF header).")
    if filename:
        lower = filename.lower().strip()
        if lower and not lower.endswith(".pdf"):
            raise AmendmentStorageError("Filename must end with .pdf.")


def build_storage_path(
    *,
    upload_root: Path,
    job_id: uuid.UUID,
    safe_name: str,
    when: datetime | None = None,
) -> Path:
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y/%m/%d")
    return upload_root / stamp / f"{job_id}_{safe_name}"


def store_amendment_pdf(
    *,
    db: Session,
    content: bytes,
    filename: str,
    content_type: str | None = None,
) -> StoreAmendmentResult:
    """Write PDF to disk and insert an ``amendment_jobs`` row (status=uploaded)."""
    validate_pdf_bytes(content, filename=filename)

    settings = get_adaptive_tax_settings()
    job_id = uuid.uuid4()
    safe_name = sanitize_filename(filename or "amendment.pdf")
    file_hash = sha256_hex(content)
    storage_path = build_storage_path(
        upload_root=settings.upload_root,
        job_id=job_id,
        safe_name=safe_name,
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    duplicate_warning: str | None = None
    existing = db.scalars(
        select(AmendmentJob.id).where(AmendmentJob.file_hash == file_hash).limit(1),
    ).first()
    if existing is not None:
        duplicate_warning = (
            f"Duplicate file hash {file_hash[:12]}… already stored as job {existing}."
        )

    job = AmendmentJob(
        id=job_id,
        original_filename=Path(filename).name[:255] if filename else safe_name,
        content_type=content_type or "application/pdf",
        size_bytes=len(content),
        file_hash=file_hash,
        storage_path=str(storage_path),
        status=AmendmentJobStatus.UPLOADED,
    )
    db.add(job)
    db.flush()
    return StoreAmendmentResult(job=job, duplicate_hash_warning=duplicate_warning)
