"""Predictive Impact Engine endpoints (FR7, FR8). Phase 5 implementation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import (
    ImpactSimulationRequest,
    ImpactSimulationResponse,
    StrategyComparisonRequest,
)
from app.services.impact_service import (
    ImpactSimulationError,
    StrategyNotFoundError,
    compare_strategies,
    simulate_impact,
)
from app.services.profile_service import ProfileNotFoundError

router = APIRouter()


@router.post("/simulate", response_model=ImpactSimulationResponse)
def simulate(payload: ImpactSimulationRequest, db: Session = DBSession) -> ImpactSimulationResponse:
    """Run Monte Carlo simulation of a strategy's long-term impact on a profile."""
    try:
        return simulate_impact(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StrategyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ImpactSimulationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/compare", response_model=list[ImpactSimulationResponse])
def compare(payload: StrategyComparisonRequest, db: Session = DBSession) -> list[ImpactSimulationResponse]:
    """Compare multiple strategies against the same profile and horizon."""
    try:
        return compare_strategies(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StrategyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ImpactSimulationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
