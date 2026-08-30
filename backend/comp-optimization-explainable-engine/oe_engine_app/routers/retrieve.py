"""GET /retrieve — hybrid keyword + embedding search over ingested chunks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.deps import get_session
from oe_engine_app.services.embedder import OpenAIEmbedder
from oe_engine_app.services.retrieve import hits_to_json, hybrid_retrieve

router = APIRouter(tags=["retrieve"])


class RetrieveBody(BaseModel):
    query: str
    source_doc_id: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)


def _query_embedding(query: str) -> list[float] | None:
    settings = get_oe_engine_settings()
    if not settings.OPENAI_API_KEY:
        return None
    embedder = OpenAIEmbedder(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OE_ENGINE_EMBEDDING_MODEL,
        batch_size=1,
    )
    vectors = embedder.embed_batch([query])
    return vectors[0] if vectors else None


def _run(query: str, source_doc_id: str | None, top_k: int) -> dict[str, Any]:
    session = get_session()
    try:
        embedding = _query_embedding(query)
        hits = hybrid_retrieve(
            session,
            query=query,
            query_embedding=embedding,
            source_doc_id=source_doc_id,
            top_k=top_k,
        )
        return {
            "query": query,
            "source_doc_id": source_doc_id,
            "hit_count": len(hits),
            "semantic": embedding is not None,
            "hits": hits_to_json(hits),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "query": query,
            "source_doc_id": source_doc_id,
            "hit_count": 0,
            "semantic": False,
            "hits": [],
            "detail": str(exc),
        }
    finally:
        session.close()


@router.get("/retrieve")
def get_retrieve(
    q: str = Query(..., min_length=2),
    source_doc_id: str | None = Query(default=None),
    top_k: int = Query(default=8, ge=1, le=50),
) -> dict[str, Any]:
    return _run(q, (source_doc_id or "").strip() or None, top_k)


@router.post("/retrieve")
def post_retrieve(body: RetrieveBody) -> dict[str, Any]:
    return _run(body.query, body.source_doc_id, body.top_k)
