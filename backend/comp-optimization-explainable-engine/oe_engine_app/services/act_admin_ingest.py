"""Ingest uploaded Act PDFs without editing corpus_manifest.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from oe_engine_app.services.ingest import IngestResult, ingest_pdf, sha256_file


def extract_source_doc_id(requested: str, ingest_result: IngestResult) -> str:
    """Use the canonical ingested doc when this PDF hash already exists in the corpus."""
    if ingest_result.status == "skipped_sha256":
        return ingest_result.source_doc_id
    return requested


def _rewrite_draft_ids(draft: dict[str, Any], *, job_sid: str, extract_sid: str) -> None:
    draft["source_doc_id"] = job_sid
    if extract_sid == job_sid:
        return
    for entity in draft.get("entities") or []:
        if str(entity.get("source_doc_id") or "") == extract_sid:
            entity["source_doc_id"] = job_sid


def ingest_uploaded_pdf(
    session: Session,
    *,
    pdf_path: Path,
    source_doc_id: str,
    title: str | None = None,
    embedder: Any,
) -> IngestResult:
    """Register and chunk an uploaded Act; never touches corpus_manifest.json."""
    row: dict[str, Any] = {
        "source_doc_id": source_doc_id,
        "title": title or pdf_path.name,
        "tier": "act",
        "instrument_type": "uploaded_act",
    }
    return ingest_pdf(
        session,
        pdf_path=pdf_path,
        row=row,
        embedder=embedder,
        update_manifest=False,
    )


def pdf_sha256(path: Path) -> str:
    return sha256_file(path)
