"""Shared law-grounded query pipeline for /query and /chat routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import LanguageModelSettings
from app.schemas.graph_v1 import GraphContext
from app.schemas.proof_map_v1 import ProofMap
from app.schemas.query_v1 import Citation, QueryResponse
from app.services.answer_synthesis import synthesize_plain_answer
from app.services.domain_gate import assess_domain
from app.services.lex_rank import rerank_hits
from app.services.proof_map import build_proof_map
from app.services.query_preprocess import normalize_query
from app.services.think_twice import apply_think_twice


def _excerpt(text: str, max_chars: int) -> str:
    t = text.replace("\r\n", "\n").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


@dataclass(frozen=True, slots=True)
class QueryPipelineResult:
    response: QueryResponse
    proof_map: ProofMap | None


async def run_query_pipeline(
    request: Request,
    settings: LanguageModelSettings,
    *,
    question: str,
    top_k: int | None,
    synthesize_answer: bool,
    assessment_year_hint: str | None = None,
    include_proof_map: bool = True,
    retrieval_question: str | None = None,
) -> QueryPipelineResult:
    """Run the full query pipeline.

    `question` is used for domain assessment and displayed to the user.
    `retrieval_question` (optional) is used for retrieval only — pass the
    contextual multi-turn string from the chat router so follow-up questions
    get better recall without bypassing the domain gate.
    """
    index = getattr(request.app.state, "retrieval_index", None)
    chunk_texts: dict[str, str] = getattr(request.app.state, "chunk_text_by_id", {}) or {}
    join_map: dict[str, dict[str, str | None]] = getattr(
        request.app.state, "chunk_kg_join_by_id", None
    ) or {}
    graph_service = getattr(request.app.state, "graph_service", None)

    normalized = normalize_query(question)
    normalized_retrieval = normalize_query(retrieval_question) if retrieval_question else normalized
    k = top_k or settings.COMP_LLM_RETRIEVAL_TOP_K
    cap = settings.COMP_LLM_QUERY_CITATION_MAX_CHARS
    model_id = "dense-baseline" if settings.COMP_LLM_RETRIEVAL_BACKEND == "dense" else "tfidf-baseline"

    if index is None:
        domain = assess_domain(
            normalized,
            None,
            enabled=settings.COMP_LLM_DOMAIN_GATE_ENABLED,
            min_retrieval_score=settings.COMP_LLM_MIN_RETRIEVAL_SCORE,
            require_tax_hints=settings.COMP_LLM_DOMAIN_REQUIRE_TAX_HINTS,
        )
        response = QueryResponse(
            question=question,
            normalized_question=normalized,
            top_k=k,
            citations=[],
            retrieval_model="stub-no-corpus",
            domain_status=domain.status,
            domain_message=domain.message,
            validation_status="not_run",
        )
        proof = (
            build_proof_map(
                question=question,
                normalized_question=normalized,
                retrieval_model="stub-no-corpus",
                citations=[],
                graph_context=None,
                validation=None,
                validation_status="not_run",
                plain_answer=None,
            )
            if include_proof_map and settings.COMP_LLM_PROOF_MAP_ENABLED
            else None
        )
        return QueryPipelineResult(response=response, proof_map=proof)

    hits = index.search(normalized_retrieval, k)
    if settings.COMP_LLM_LEX_SPECIALIS_RERANK:
        hits = rerank_hits(hits, join_map)

    top_score = hits[0][1] if hits else None
    top_excerpt = chunk_texts.get(hits[0][0], "") if hits else None
    domain = assess_domain(
        normalized,
        top_score,
        enabled=settings.COMP_LLM_DOMAIN_GATE_ENABLED,
        min_retrieval_score=settings.COMP_LLM_MIN_RETRIEVAL_SCORE,
        require_tax_hints=settings.COMP_LLM_DOMAIN_REQUIRE_TAX_HINTS,
        top_excerpt=top_excerpt,
        min_question_overlap=settings.COMP_LLM_DOMAIN_MIN_QUESTION_OVERLAP,
    )

    if domain.status != "in_domain":
        response = QueryResponse(
            question=question,
            normalized_question=normalized,
            top_k=k,
            citations=[],
            retrieval_model=model_id,
            graph_context=None,
            domain_status=domain.status,
            domain_message=domain.message,
            validation_status="not_run",
        )
        proof = (
            build_proof_map(
                question=question,
                normalized_question=normalized,
                retrieval_model=model_id,
                citations=[],
                graph_context=None,
                validation=None,
                validation_status="not_run",
                plain_answer=None,
            )
            if include_proof_map and settings.COMP_LLM_PROOF_MAP_ENABLED
            else None
        )
        return QueryPipelineResult(response=response, proof_map=proof)

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
    validation_status = "not_run"
    think_validation = None

    if synthesize_answer:
        draft, answer_provider, answer_model = await synthesize_plain_answer(
            settings,
            normalized,
            citations,
            graph_context,
        )
        think = apply_think_twice(
            settings,
            draft,
            assessment_year_hint=assessment_year_hint,
        )
        plain_answer = think.answer_text
        think_validation = think.validation
        validation_status = think.validation_status

    response = QueryResponse(
        question=question,
        normalized_question=normalized,
        top_k=k,
        citations=citations,
        retrieval_model=model_id,
        graph_context=graph_context,
        plain_answer=plain_answer,
        answer_provider=answer_provider,
        answer_model=answer_model,
        domain_status=domain.status,
        domain_message=domain.message,
        validation_status=validation_status,
    )

    proof = None
    if include_proof_map and settings.COMP_LLM_PROOF_MAP_ENABLED:
        proof = build_proof_map(
            question=question,
            normalized_question=normalized,
            retrieval_model=model_id,
            citations=citations,
            graph_context=graph_context,
            validation=think_validation,
            validation_status=validation_status,
            plain_answer=plain_answer,
        )

    return QueryPipelineResult(response=response, proof_map=proof)
