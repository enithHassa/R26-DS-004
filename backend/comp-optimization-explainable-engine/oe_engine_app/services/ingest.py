"""Ingest PDFs: sha256 identity, dual-text chunks, embeddings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from db.models import OeEngineChunk, OeEngineDocument
from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.services.chunker import build_chunks
from oe_engine_app.services.embedder import Embedder, estimate_embedding_usd
from oe_engine_app.services.manifest import manifest_documents, write_manifest_sha256
from oe_engine_app.services.pdf_extract import extract_dual_text


@dataclass
class IngestResult:
    source_doc_id: str
    status: str
    sha256: str
    chunk_count: int = 0
    page_count: int = 0
    embedding_usd: float = 0.0
    detail: str = ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _section_ref_text(raw: object) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "; ".join(str(item) for item in raw if item)
    return str(raw)


def ingest_pdf(
    session: Session,
    *,
    pdf_path: Path,
    row: dict[str, Any],
    embedder: Embedder,
    update_manifest: bool = True,
) -> IngestResult:
    source_doc_id = str(row["source_doc_id"])
    digest = sha256_file(pdf_path)
    existing_hash = (
        session.query(OeEngineDocument)
        .filter(OeEngineDocument.sha256 == digest)
        .one_or_none()
    )
    if existing_hash is not None:
        return IngestResult(
            source_doc_id=existing_hash.source_doc_id,
            status="skipped_sha256",
            sha256=digest,
            chunk_count=existing_hash.chunk_count,
            page_count=existing_hash.page_count,
            detail=f"hash already stored as {existing_hash.source_doc_id}",
        )

    existing_id = session.get(OeEngineDocument, source_doc_id)
    if existing_id is not None:
        session.query(OeEngineChunk).filter(
            OeEngineChunk.source_doc_id == source_doc_id
        ).delete()
        session.delete(existing_id)
        session.flush()

    extracted = extract_dual_text(pdf_path)
    settings = get_oe_engine_settings()
    chunks = build_chunks(
        pages=extracted.pages,
        source_doc_id=source_doc_id,
        title=str(row.get("title") or pdf_path.name),
        tier=str(row["tier"]),
        tables_by_page=extracted.tables_by_page,
        table_method=extracted.table_method,
        max_chars=settings.OE_ENGINE_MAX_CHUNK_CHARS,
        overlap=settings.OE_ENGINE_CHUNK_OVERLAP,
    )
    texts = [chunk["text"] for chunk in chunks]
    usd = estimate_embedding_usd(texts)
    embeddings = embedder.embed_batch(texts) if texts else []
    if texts and len(embeddings) != len(texts):
        raise RuntimeError(
            f"embedding count {len(embeddings)} != chunk count {len(texts)}"
        )

    doc = OeEngineDocument(
        source_doc_id=source_doc_id,
        file_name=pdf_path.name,
        title=str(row.get("title") or pdf_path.name),
        tier=str(row["tier"]),
        instrument_type=str(row.get("instrument_type") or "") or None,
        sha256=digest,
        byte_size=pdf_path.stat().st_size,
        page_count=extracted.page_count,
        chunk_count=len(chunks),
        embedding_model=embedder.model,
    )
    session.add(doc)
    session.flush()
    for chunk, vector in zip(chunks, embeddings, strict=True):
        extra = {
            key: chunk.get(key)
            for key in (
                "schedule_ref",
                "paragraph_ref",
                "parent_provision_id",
                "is_operative_provision",
                "chunk_schema_version",
            )
            if chunk.get(key) is not None
        }
        session.add(
            OeEngineChunk(
                chunk_id=str(chunk["chunk_id"]),
                source_doc_id=source_doc_id,
                channel=str(chunk.get("channel") or "text_stream"),
                page=int(chunk.get("page") or 0),
                chunk_index=int(chunk.get("chunk_index") or 0),
                text=str(chunk["text"]),
                section_ref=_section_ref_text(chunk.get("section_ref")),
                parent_provision_id=chunk.get("parent_provision_id"),
                embedding_json=json.dumps(vector),
                embedding_model=embedder.model,
                extra=extra or None,
            )
        )
    session.commit()
    if update_manifest:
        write_manifest_sha256(source_doc_id, digest)
    return IngestResult(
        source_doc_id=source_doc_id,
        status="ingested",
        sha256=digest,
        chunk_count=len(chunks),
        page_count=extracted.page_count,
        embedding_usd=usd,
        detail="; ".join(extracted.warnings),
    )


def ingest_manifest(
    session: Session,
    *,
    embedder: Embedder,
    source_doc_id: str | None = None,
    pdf_root: Path | None = None,
    update_manifest: bool = True,
) -> list[IngestResult]:
    settings = get_oe_engine_settings()
    root = pdf_root or settings.OE_ENGINE_PDF_ROOT
    results: list[IngestResult] = []
    for row in manifest_documents():
        doc_id = str(row["source_doc_id"])
        if source_doc_id and doc_id != source_doc_id:
            continue
        pdf_path = root / str(row["file_name"])
        if not pdf_path.is_file():
            results.append(
                IngestResult(
                    source_doc_id=doc_id,
                    status="missing_pdf",
                    sha256="",
                    detail=str(pdf_path),
                )
            )
            continue
        results.append(
            ingest_pdf(
                session,
                pdf_path=pdf_path,
                row=row,
                embedder=embedder,
                update_manifest=update_manifest,
            )
        )
    return results
