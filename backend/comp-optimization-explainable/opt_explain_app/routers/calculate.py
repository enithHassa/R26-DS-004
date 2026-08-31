"""POST /calculate — tax from RAG caps and slabs for one assessment year."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from opt_explain_app.services import calculate as calc_engine
from opt_explain_app.services import rag_index

router = APIRouter(tags=["calculate"])


class IncomeIn(BaseModel):
    employment: int = 0
    business: int = 0
    investment: int = 0
    other: int = 0
    interest: int = 0
    rents: int = 0


class ClaimIn(BaseModel):
    entry_id: str
    amount: int = 0
    affirmed: bool | None = None
    skipped: bool = False


class CalculateRequest(BaseModel):
    assessment_year: str
    income: IncomeIn
    claims: list[ClaimIn] = Field(default_factory=list)
    exclude_source_doc_id: str | None = None


@router.post("/calculate")
def post_calculate(body: CalculateRequest) -> dict[str, Any]:
    rag_index.ensure_index()
    try:
        return calc_engine.calculate(
            assessment_year=body.assessment_year,
            income=body.income.model_dump(),
            claims=[c.model_dump() for c in body.claims],
            exclude_source_doc_id=body.exclude_source_doc_id,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No RAG index for assessment_year {body.assessment_year!r}",
        ) from None
    except ValueError as exc:
        if str(exc) == "no_rate_bands":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No rate bands remain for this year after filters.",
            ) from None
        raise
