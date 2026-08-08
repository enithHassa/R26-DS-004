"""Unit tests for amendment PDF storage helpers (no DB)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.services.storage import (
    AmendmentStorageError,
    build_storage_path,
    sanitize_filename,
    sha256_hex,
    store_amendment_pdf,
    validate_pdf_bytes,
)


def test_sha256_hex_stable() -> None:
    assert sha256_hex(b"abc") == sha256_hex(b"abc")
    assert sha256_hex(b"abc") != sha256_hex(b"abd")


def test_sanitize_filename_strips_unsafe_and_ensures_pdf() -> None:
    assert sanitize_filename("IR Act No. 02/2025 (E).pdf") == "IR_Act_No._02_2025_E.pdf"
    assert sanitize_filename("notes.txt").endswith(".pdf")


def test_validate_pdf_bytes_rejects_empty_and_non_pdf() -> None:
    with pytest.raises(AmendmentStorageError, match="empty"):
        validate_pdf_bytes(b"")
    with pytest.raises(AmendmentStorageError, match="not a PDF"):
        validate_pdf_bytes(b"hello world", filename="x.pdf")
    with pytest.raises(AmendmentStorageError, match="must end with .pdf"):
        validate_pdf_bytes(b"%PDF-1.4", filename="x.docx")
    validate_pdf_bytes(b"%PDF-1.7\n...", filename="act.pdf")


def test_build_storage_path_layout(tmp_path: Path) -> None:
    job_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    when = datetime(2026, 8, 2, tzinfo=timezone.utc)
    path = build_storage_path(
        upload_root=tmp_path,
        job_id=job_id,
        safe_name="act.pdf",
        when=when,
    )
    assert path == tmp_path / "2026" / "08" / "02" / f"{job_id}_act.pdf"


def test_store_amendment_pdf_writes_file_and_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_UPLOAD_ROOT", str(tmp_path))
    get_adaptive_tax_settings.cache_clear()

    db = MagicMock()
    db.scalars.return_value.first.return_value = None

    content = b"%PDF-1.4\n% fake amendment\n"
    result = store_amendment_pdf(
        db=db,
        content=content,
        filename="IR_Act_No_02-2025_E.pdf",
        content_type="application/pdf",
    )

    assert result.duplicate_hash_warning is None
    assert result.job.file_hash == sha256_hex(content)
    assert Path(result.job.storage_path).is_file()
    assert Path(result.job.storage_path).read_bytes() == content
    db.add.assert_called_once()
    db.flush.assert_called_once()
    get_adaptive_tax_settings.cache_clear()
