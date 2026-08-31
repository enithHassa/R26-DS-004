"""POST /api/v1/explain — RAG-grounded tax narrative (Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from adaptive_tax_app.schemas.explain import ExplainTaxRequestV1, ExplainTaxResponseV1
from adaptive_tax_app.services.explain import ExplainError, explain_tax
from backend.shared.config.database import get_db

router = APIRouter(tags=["explain"])


@router.post(
    "/explain",
    response_model=ExplainTaxResponseV1,
    summary="Explain a calculation using RAG + rule_source evidence only",
)
def explain_calculation(
    body: ExplainTaxRequestV1,
    db: Session = Depends(get_db),
) -> ExplainTaxResponseV1:
    """Prefer ``calc_id`` from POST /calculate; returns insufficient_evidence if no RAG/quotes."""
    try:
        return explain_tax(body, db=db)
    except ExplainError as exc:
        detail = str(exc)
        code = status.HTTP_400_BAD_REQUEST
        lower = detail.lower()
        if "not found" in lower:
            code = status.HTTP_404_NOT_FOUND
        elif "openai" in lower or "unavailable" in lower:
            code = status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=detail) from exc
