"""Ranked recommendation endpoints (FR5, FR6, FR9, FR10). Implemented in Phase 4 (WP6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    FeedbackCreate,
    RecommendationExplanation,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter()


@router.post("", response_model=RecommendationResponse)
def rank(payload: RecommendationRequest) -> RecommendationResponse:
    """Produce the top-K ranked strategies fused from LambdaMART + adoption probability."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ranking engine is implemented in Phase 4 (WP6).",
    )


@router.get("/{recommendation_item_id}/explain", response_model=RecommendationExplanation)
def explain(recommendation_item_id: UUID) -> RecommendationExplanation:
    """SHAP-based explanation for a single recommendation item (FR10, NFR3)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Explanations are implemented in Phase 6 (WP8).",
    )


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
def submit_feedback(payload: FeedbackCreate) -> dict[str, str]:
    """Persist user feedback (accepted / dismissed / rating) for continual learning."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feedback persistence is implemented in Phase 4 (WP6).",
    )
