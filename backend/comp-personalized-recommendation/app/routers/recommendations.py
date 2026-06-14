"""Ranked recommendation endpoints (FR5, FR6, FR9, FR10)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import (
    ExplainRequest,
    FeedbackCreate,
    RecommendationExplanation,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services import (
    ArtifactLoadError,
    ExplanationError,
    ProfileNotFoundError,
    RecommendationGenerationError,
    StrategyNotFoundError,
    explain_strategy_for_profile,
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


@router.post("/explain", response_model=RecommendationExplanation)
def explain(payload: ExplainRequest, db: Session = DBSession) -> RecommendationExplanation:
    """SHAP-based explanation for a profile×strategy pair (Phase 6 / FR10)."""
    try:
        return explain_strategy_for_profile(
            db,
            profile_id=payload.profile_id,
            strategy_code=payload.strategy_code,
            top_k=payload.top_k,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StrategyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExplanationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ArtifactLoadError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{recommendation_item_id}/explain", response_model=RecommendationExplanation)
def explain_by_item_id(recommendation_item_id: UUID) -> RecommendationExplanation:
    """Legacy path — recommendation items are not persisted; use POST /explain."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Recommendation items are not persisted. "
            "Use POST /api/v1/recommendations/explain with profile_id and strategy_code."
        ),
    )


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
def submit_feedback(payload: FeedbackCreate) -> dict[str, str]:
    """Persist user feedback (accepted / dismissed / rating) for continual learning."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feedback persistence is planned for a later phase.",
    )
