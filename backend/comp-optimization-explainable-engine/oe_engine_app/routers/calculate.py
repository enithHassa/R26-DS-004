"""POST /calculate — year-view caps and First Schedule slabs + APIT/WHT credits."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from oe_engine_app.deps import get_session
from oe_engine_app.services import calculate as calc_engine

router = APIRouter(tags=["calculate"])


class TerminalBenefitIn(BaseModel):
    type: str | None = None
    amount: int = 0
    employment_period_over_20_years: bool | None = None
    loss_of_office_scheme_approved: bool | None = None
    terminal_benefit_period: str | None = None


class IncomeIn(BaseModel):
    employment: int = 0
    business: int = 0
    investment: int = 0
    other: int = 0
    interest: int = 0
    rents: int = 0
    wht_already_paid: int = 0
    apit_already_paid: int = 0
    terminal_benefits: list[TerminalBenefitIn] = Field(default_factory=list)
    terminal_benefit_amount: int = 0
    terminal_benefit_type: str | None = None
    employment_period_over_20_years: bool | None = None
    loss_of_office_scheme_approved: bool | None = None
    terminal_benefit_period: str | None = None


class ComponentClaimIn(BaseModel):
    """One rupee amount against one enumerated recipient of a relief."""

    component_id: str
    amount: int = 0


class ClaimIn(BaseModel):
    entry_id: str
    amount: int = 0
    affirmed: bool | None = None
    skipped: bool = False
    components: list[ComponentClaimIn] = Field(default_factory=list)


class CalculateRequest(BaseModel):
    assessment_year: str
    income: IncomeIn
    claims: list[ClaimIn] = Field(default_factory=list)
    exclude_source_doc_id: str | None = None
    wht_already_paid: int = 0
    apit_already_paid: int = 0


@router.post("/calculate")
def post_calculate(body: CalculateRequest) -> dict[str, Any]:
    session = get_session()
    try:
        return calc_engine.calculate(
            session,
            assessment_year=body.assessment_year,
            income=body.income.model_dump(),
            claims=[c.model_dump() for c in body.claims],
            exclude_source_doc_id=body.exclude_source_doc_id,
            wht_already_paid=body.wht_already_paid or body.income.wht_already_paid,
            apit_already_paid=body.apit_already_paid or body.income.apit_already_paid,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No year view for assessment_year {body.assessment_year!r}",
        ) from None
    except ValueError as exc:
        if str(exc) == "no_rate_bands":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No rate bands remain for this year after filters.",
            ) from None
        raise
    finally:
        session.close()
