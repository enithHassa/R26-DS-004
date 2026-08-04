"""POST /api/v1/calculate — Adaptive Tax Phase 3 rule engine (+ Phase 4 calc_id)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, CalculateTaxResponseV1
from adaptive_tax_app.services.calc_store import CalcStoreError, save as save_calculation
from adaptive_tax_app.services.rule_engine import calculate

router = APIRouter(tags=["calculate"])


@router.post(
    "/calculate",
    response_model=CalculateTaxResponseV1,
    summary="Calculate tax with explainable rule-engine trace",
)
def calculate_tax(body: CalculateTaxRequestV1) -> CalculateTaxResponseV1:
    """Pure-Python tax calculation driven by KG + param JSON; persists under calc_id."""
    try:
        result = calculate(body)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        # Typically Neo4j unavailable when COMP_ADAPTIVE_TAX_KG_MODE=neo4j.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        calc_id = save_calculation(body, result)
    except CalcStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return result.model_copy(update={"calc_id": calc_id})
