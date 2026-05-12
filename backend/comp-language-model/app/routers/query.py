"""Law-grounded query route: retrieval + citation excerpts (Phase 2 Step 14)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_lm_settings
from app.schemas.query_v1 import Citation, QueryRequest, QueryResponse

router = APIRouter(prefix="/api/v1", tags=["query"])


def _excerpt(text: str, max_chars: int) -> str:
    t = text.replace("\r\n", "\n").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


@router.post("/query", response_model=QueryResponse)
def query_with_citations(request: Request, body: QueryRequest) -> QueryResponse:
    index = getattr(request.app.state, "retrieval_index", None)
    chunk_texts: dict[str, str] = getattr(request.app.state, "chunk_text_by_id", {}) or {}
    join_map: dict[str, dict[str, str | None]] = getattr(
        request.app.state, "chunk_kg_join_by_id", None
    ) or {}
    settings = get_lm_settings()
    k = body.top_k or settings.COMP_LLM_RETRIEVAL_TOP_K
    cap = settings.COMP_LLM_QUERY_CITATION_MAX_CHARS

    if index is None:
        return QueryResponse(
            question=body.question,
            top_k=k,
            citations=[],
            retrieval_model="stub-no-corpus",
        )

    hits = index.search(body.question, k)
    citations: list[Citation] = []
    for cid, score in hits:
        raw = chunk_texts.get(cid, "")
        m = join_map.get(cid) or {}
        citations.append(
            Citation(
                chunk_id=cid,
                score=score,
                text=_excerpt(raw, cap) if raw else "",
                source_doc_id=m.get("source_doc_id"),
                section_uid=m.get("section_uid"),
                section_label=m.get("section_label"),
                tier=m.get("tier"),
                instrument_type=m.get("instrument_type"),
                content_kind=m.get("content_kind"),
            )
        )

    if settings.COMP_LLM_RETRIEVAL_BACKEND == "dense":
        model_id = "dense-baseline"
    else:
        model_id = "tfidf-baseline"

    return QueryResponse(
        question=body.question,
        top_k=k,
        citations=citations,
        retrieval_model=model_id,
    )
