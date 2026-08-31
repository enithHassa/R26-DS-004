"""GET /api/v1/calculations/{calc_id} — reload a persisted calculation for the report page."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from adaptive_tax_app.schemas.calculate import StoredCalculationV1
from adaptive_tax_app.schemas.reasoning_graph import ReasoningGraphResponseV1
from adaptive_tax_app.services.calc_store import CalcStoreError, load as load_calculation
from adaptive_tax_app.services.reasoning_graph import build_reasoning_graph

router = APIRouter(prefix="/calculations", tags=["calculations"])


@router.get(
    "/{calc_id}",
    response_model=StoredCalculationV1,
    summary="Load a persisted calculation by calc_id",
)
def get_calculation(calc_id: str) -> StoredCalculationV1:
    """Return the stored request/response bundle for Phase 4 report UI."""
    try:
        record = load_calculation(calc_id)
    except CalcStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"calculation not found: {calc_id}",
        )
    return record


@router.get(
    "/{calc_id}/reasoning-graph",
    response_model=ReasoningGraphResponseV1,
    summary="Deterministic legal reasoning graph for report viva panel (Phase 6.8)",
)
def get_reasoning_graph(calc_id: str) -> ReasoningGraphResponseV1:
    try:
        record = load_calculation(calc_id)
    except CalcStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"calculation not found: {calc_id}",
        )
    return build_reasoning_graph(record)
