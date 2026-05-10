"""Ranked recommendation endpoints (FR5, FR6, FR9, FR10). Implemented in Phase 4 (WP6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import (
    FeedbackCreate,
    RecommendationExplanation,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services import (
    ArtifactLoadError,
    ProfileNotFoundError,
    RecommendationGenerationError,
    generate_recommendations,
)

router = APIRouter()


@router.post("", response_model=RecommendationResponse)
def rank(payload: RecommendationRequest, db: Session = DBSession) -> RecommendationResponse:
    """Produce top-K strategies using trained matcher + rule feasibility filters."""
    try:
        return generate_recommendations(
            db,
            profile_id=payload.profile_id,
            top_k=payload.top_k,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ArtifactLoadError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RecommendationGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


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
