"""Hybrid recommendation endpoint: LambdaMART (0.7) + RAG TF-IDF (0.3)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.services.hybrid_service import HybridResult, hybrid_query
from app.services.profile_service import ProfileNotFoundError

router = APIRouter()


class HybridQueryRequest(BaseModel):
    profile_id: str
    top_k: int = Field(default=5, ge=1, le=10)
    lambda_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    rules_source: Literal["default", "catalog"] = "default"
    assessment_year: str | None = Field(default=None, pattern=r"^\d{4}_\d{2}$")


class HybridRulesContext(BaseModel):
    rules_source: str
    rules_version: str
    assessment_year: str | None
    baseline_tax_lkr: float
    catalog_promoted_at: str | None = None
    catalog_act: str | None = None
    mapped_fields: list[str] = Field(default_factory=list)


class HybridResultItem(BaseModel):
    rank: int
    strategy_id: str
    name: str
    category: str
    description: str
    hybrid_score: float
    retrieval_hybrid_score: float
    fusion_score: float
    lambdamart_score: float
    rag_similarity_score: float
    adoption_probability: float
    estimated_annual_savings: float
    confidence: float
    risk_score: float
    ird_reference: str
    required_docs: list[str]
    why_relevant: str
    detailed_explanation: dict[str, str]


class HybridQueryResponse(BaseModel):
    profile_id: str
    query_text: str
    lambda_weight: float
    rag_weight: float
    rules_context: HybridRulesContext
    items: list[HybridResultItem]


@router.post("", response_model=HybridQueryResponse)
def hybrid_recommend(
    payload: HybridQueryRequest, db: Session = DBSession
) -> HybridQueryResponse:
    """Hybrid: LambdaMART score × lambda_weight + RAG similarity × (1-lambda_weight).

    Pass ``rules_source=catalog`` and ``assessment_year`` to preview recommendations
    with opt-in catalog rules (after syncing via ``/admin/catalog-rules/sync``).
    Default behaviour is unchanged when ``rules_source`` is omitted.
    """
    try:
        results, query_text, rules_context = hybrid_query(
            db,
            profile_id=payload.profile_id,
            top_k=payload.top_k,
            lambda_weight=payload.lambda_weight,
            rules_source=payload.rules_source,
            assessment_year=payload.assessment_year,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return HybridQueryResponse(
        profile_id=payload.profile_id,
        query_text=query_text,
        lambda_weight=payload.lambda_weight,
        rag_weight=round(1.0 - payload.lambda_weight, 2),
        rules_context=HybridRulesContext(**rules_context),
        items=[
            HybridResultItem(
                rank=r.rank,
                strategy_id=r.strategy_id,
                name=r.name,
                category=r.category,
                description=r.description,
                hybrid_score=r.hybrid_score,
                retrieval_hybrid_score=r.retrieval_hybrid_score,
                fusion_score=r.fusion_score,
                lambdamart_score=r.lambdamart_score,
                rag_similarity_score=r.rag_similarity_score,
                adoption_probability=r.adoption_probability,
                estimated_annual_savings=r.estimated_annual_savings,
                confidence=r.confidence,
                risk_score=r.risk_score,
                ird_reference=r.ird_reference,
                required_docs=r.required_docs,
                why_relevant=r.why_relevant,
                detailed_explanation=r.detailed_explanation,
            )
            for r in results
        ],
    )
