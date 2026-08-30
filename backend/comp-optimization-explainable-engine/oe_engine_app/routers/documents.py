"""GET /documents — ingested corpus rows."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from oe_engine_app.deps import get_session
from db.models import OeEngineChunk, OeEngineDocument

router = APIRouter(tags=["corpus"])


@router.get("/documents")
def get_documents() -> dict[str, Any]:
    session = get_session()
    try:
        rows = session.query(OeEngineDocument).order_by(OeEngineDocument.source_doc_id).all()
        documents = [
            {
                "source_doc_id": row.source_doc_id,
                "file_name": row.file_name,
                "title": row.title,
                "tier": row.tier,
                "sha256": row.sha256,
                "page_count": row.page_count,
                "chunk_count": row.chunk_count,
                "embedding_model": row.embedding_model,
            }
            for row in rows
        ]
        chunk_count = session.query(OeEngineChunk).count()
        return {
            "documents": documents,
            "document_count": len(documents),
            "chunk_count": chunk_count,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "documents": [],
            "document_count": 0,
            "chunk_count": 0,
            "detail": str(exc),
        }
    finally:
        session.close()
