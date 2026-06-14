"""RAG-based strategy retrieval endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.services.profile_service import ProfileNotFoundError
from app.services.rag_service import RagResult, rag_query

router = APIRouter()


class RagQueryRequest(BaseModel):
    profile_id: str
    top_k: int = Field(default=5, ge=1, le=10)


class RagResultItem(BaseModel):
    strategy_id: str
    name: str
    category: str
    description: str
    similarity_score: float
    ird_reference: str
    required_docs: list[str]
    why_relevant: str
    detailed_explanation: dict[str, str]


class RagQueryResponse(BaseModel):
    profile_id: str
    query_text: str
    retrieval_method: str
    items: list[RagResultItem]


@router.post("", response_model=RagQueryResponse)
def rag_recommend(payload: RagQueryRequest, db: Session = DBSession) -> RagQueryResponse:
    """Retrieve top-K strategies using TF-IDF semantic similarity (RAG prototype)."""
    try:
        results, query_text = rag_query(db, profile_id=payload.profile_id, top_k=payload.top_k)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return RagQueryResponse(
        profile_id=payload.profile_id,
        query_text=query_text,
        retrieval_method="TF-IDF cosine similarity (RAG prototype)",
        items=[
            RagResultItem(
                strategy_id=r.strategy_id,
                name=r.name,
                category=r.category,
                description=r.description,
                similarity_score=r.similarity_score,
                ird_reference=r.ird_reference,
                required_docs=r.required_docs,
                why_relevant=r.why_relevant,
                detailed_explanation=r.detailed_explanation,
            )
            for r in results
        ],
    )
