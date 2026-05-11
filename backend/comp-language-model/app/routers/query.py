"""Law-grounded query route: retrieval + citation excerpts + graph context (Phase 2 + Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_lm_settings
from app.schemas.graph_v1 import GraphContext
from app.schemas.query_v1 import Citation, QueryRequest, QueryResponse
from app.services.answer_synthesis import synthesize_plain_answer
from app.services.domain_gate import assess_domain

router = APIRouter(prefix="/api/v1", tags=["query"])


def _excerpt(text: str, max_chars: int) -> str:
    t = text.replace("\r\n", "\n").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


@router.post("/query", response_model=QueryResponse)
async def query_with_citations(request: Request, body: QueryRequest) -> QueryResponse:
    index = getattr(request.app.state, "retrieval_index", None)
    chunk_texts: dict[str, str] = getattr(request.app.state, "chunk_text_by_id", {}) or {}
    join_map: dict[str, dict[str, str | None]] = getattr(
        request.app.state, "chunk_kg_join_by_id", None
    ) or {}
    graph_service = getattr(request.app.state, "graph_service", None)
    settings = get_lm_settings()
    k = body.top_k or settings.COMP_LLM_RETRIEVAL_TOP_K
    cap = settings.COMP_LLM_QUERY_CITATION_MAX_CHARS

    model_id = "dense-baseline" if settings.COMP_LLM_RETRIEVAL_BACKEND == "dense" else "tfidf-baseline"

    if index is None:
        domain = assess_domain(
            body.question,
            None,
            enabled=settings.COMP_LLM_DOMAIN_GATE_ENABLED,
            min_retrieval_score=settings.COMP_LLM_MIN_RETRIEVAL_SCORE,
            require_tax_hints=settings.COMP_LLM_DOMAIN_REQUIRE_TAX_HINTS,
        )
        return QueryResponse(
            question=body.question,
            top_k=k,
            citations=[],
            retrieval_model="stub-no-corpus",
            domain_status=domain.status,
            domain_message=domain.message,
        )

    hits = index.search(body.question, k)
    top_score = hits[0][1] if hits else None
    top_excerpt = chunk_texts.get(hits[0][0], "") if hits else None
    domain = assess_domain(
        body.question,
        top_score,
        enabled=settings.COMP_LLM_DOMAIN_GATE_ENABLED,
        min_retrieval_score=settings.COMP_LLM_MIN_RETRIEVAL_SCORE,
        require_tax_hints=settings.COMP_LLM_DOMAIN_REQUIRE_TAX_HINTS,
        top_excerpt=top_excerpt,
        min_question_overlap=settings.COMP_LLM_DOMAIN_MIN_QUESTION_OVERLAP,
    )
    if domain.status != "in_domain":
        return QueryResponse(
            question=body.question,
            top_k=k,
            citations=[],
            retrieval_model=model_id,
            graph_context=None,
            domain_status=domain.status,
            domain_message=domain.message,
        )

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

    # Phase 4 — graph enrichment
    graph_context: GraphContext | None = None
    if graph_service is not None:
        chunk_ids = [cid for cid, _ in hits]
        section_uids = [
            m.get("section_uid")
            for cid in chunk_ids
            if (m := join_map.get(cid) or {}) and m.get("section_uid")
        ]
        graph_context = await graph_service.enrich_from_chunks(chunk_ids, section_uids or None)

    plain_answer: str | None = None
    answer_provider: str | None = None
    answer_model: str | None = None
    if body.synthesize_answer:
        plain_answer, answer_provider, answer_model = await synthesize_plain_answer(
            settings,
            body.question,
            citations,
            graph_context,
        )

    return QueryResponse(
        question=body.question,
        top_k=k,
        citations=citations,
        retrieval_model=model_id,
        graph_context=graph_context,
        plain_answer=plain_answer,
        answer_provider=answer_provider,
        answer_model=answer_model,
        domain_status=domain.status,
        domain_message=domain.message,
    )
