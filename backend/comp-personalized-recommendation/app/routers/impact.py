"""Predictive Impact Engine endpoints (FR7, FR8). Implemented in Phase 5 (WP7)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    ImpactSimulationRequest,
    ImpactSimulationResponse,
    StrategyComparisonRequest,
)

router = APIRouter()


@router.post("/simulate", response_model=ImpactSimulationResponse)
def simulate(payload: ImpactSimulationRequest) -> ImpactSimulationResponse:
    """Run Monte Carlo simulation of a strategy's long-term impact on a profile."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Monte Carlo impact engine is implemented in Phase 5 (WP7).",
    )


@router.post("/compare", response_model=list[ImpactSimulationResponse])
def compare(payload: StrategyComparisonRequest) -> list[ImpactSimulationResponse]:
    """Compare multiple strategies against the same profile and horizon."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Strategy comparison is implemented in Phase 5 (WP7).",
    )
