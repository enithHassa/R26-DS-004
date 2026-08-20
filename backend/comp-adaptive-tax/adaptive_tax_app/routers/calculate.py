"""POST /api/v1/calculate — Adaptive Tax Phase 3 rule engine (+ Phase 4 calc_id)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, CalculateTaxResponseV1
from adaptive_tax_app.services.calc_store import CalcStoreError, save as save_calculation
from adaptive_tax_app.services.kg_client import get_kg_client
from adaptive_tax_app.services.provenance import ProvenanceError
from adaptive_tax_app.services.rule_engine import calculate

router = APIRouter(tags=["calculate"])


@router.post(
    "/calculate",
    response_model=CalculateTaxResponseV1,
    summary="Calculate tax with explainable rule-engine trace",
)
def calculate_tax(body: CalculateTaxRequestV1) -> CalculateTaxResponseV1:
    """Tax calculation via Neo4j KG + param JSON; persists under calc_id.

    Requires a reachable Neo4j instance (no file-ontology fallback on this route).
    """
    try:
        result = calculate(body, kg=get_kg_client(mode="neo4j"))
    except ProvenanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        name = type(exc).__name__
        if name in {"ServiceUnavailable", "Neo4jError"} or "neo4j" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Neo4j is unavailable. Start Neo4j Desktop (bolt://127.0.0.1:7687) "
                    "and ensure NEO4J_PASSWORD is set before calculating."
                ),
            ) from exc
        # Connection refused / WinError when Desktop is down.
        msg = str(exc).lower()
        if any(
            needle in msg
            for needle in (
                "couldn't connect",
                "connection refused",
                "failed to establish connection",
                "actively refused",
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Neo4j is unavailable. Start Neo4j Desktop (bolt://127.0.0.1:7687) "
                    "and ensure NEO4J_PASSWORD is set before calculating."
                ),
            ) from exc
        raise

    try:
        calc_id = save_calculation(body, result)
    except CalcStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return result.model_copy(update={"calc_id": calc_id})
