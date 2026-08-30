"""Law-grounded query route: retrieval + citation excerpts + graph context + Proof Map."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_lm_settings
from app.schemas.query_v1 import QueryRequest, QueryResponse
from app.services.query_pipeline import run_query_pipeline

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_with_citations(request: Request, body: QueryRequest) -> QueryResponse:
    settings = get_lm_settings()
    result = await run_query_pipeline(
        request,
        settings,
        question=body.question,
        top_k=body.top_k,
        synthesize_answer=body.synthesize_answer,
        assessment_year_hint=body.assessment_year_hint,
        include_proof_map=body.include_proof_map,
    )
    response = result.response
    if result.proof_map is not None:
        response.proof_map = result.proof_map
    return response
