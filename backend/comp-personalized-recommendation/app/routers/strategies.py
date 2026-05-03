"""Tax Strategy Generation endpoints (FR3, FR4). Implemented in Phase 3 (WP5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    StrategyGenerationRequest,
    StrategyGenerationResponse,
)

router = APIRouter()


@router.post("/generate", response_model=StrategyGenerationResponse)
def generate_strategies(payload: StrategyGenerationRequest) -> StrategyGenerationResponse:
    """Generate candidate strategies for a given profile using the rules engine."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Strategy generator is implemented in Phase 3 (WP5).",
    )
