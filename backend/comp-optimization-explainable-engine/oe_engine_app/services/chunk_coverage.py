"""Promoted Acts must still have ingested chunks (Phase 7 /ready)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from db.models import OeEngineChunk
from db.year_views import OeEnginePromotedRun


def chunk_coverage_report(session: Session) -> dict[str, Any]:
    chunk_count = session.query(OeEngineChunk).count()
    promoted_ids = [
        row.source_doc_id for row in session.query(OeEnginePromotedRun).all()
    ]
    missing: list[str] = []
    covered: list[dict[str, Any]] = []
    for source_doc_id in sorted(promoted_ids):
        n = (
            session.query(OeEngineChunk)
            .filter(OeEngineChunk.source_doc_id == source_doc_id)
            .count()
        )
        if n < 1:
            missing.append(source_doc_id)
        else:
            covered.append({"source_doc_id": source_doc_id, "chunk_count": n})
    return {
        "chunk_count": chunk_count,
        "promoted_doc_count": len(promoted_ids),
        "covered": covered,
        "promoted_without_chunks": missing,
        "ok": not missing,
    }


def ready_checks(session: Session) -> dict[str, Any]:
    coverage = chunk_coverage_report(session)
    return {
        "api_bootstrap": True,
        "rag_index": coverage["chunk_count"] > 0,
        "chunk_coverage": coverage["ok"],
        "chunk_count": coverage["chunk_count"],
        "promoted_doc_count": coverage["promoted_doc_count"],
        "promoted_without_chunks": coverage["promoted_without_chunks"],
    }
