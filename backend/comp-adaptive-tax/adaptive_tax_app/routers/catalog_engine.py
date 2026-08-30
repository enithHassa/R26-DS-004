"""POST /api/v1/catalog-engine/calculate — Phase 8 catalog rate tax.

Additive router. Does not modify ``/calculate`` or its YA enum.
Engine years still use ``/calculate`` as the verified figure; catalog is an
additional interview estimate for those years.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from adaptive_tax_app.services.catalog_rate_engine import (
    CATALOG_YAS,
    ENGINE_AUTHORITY_YAS,
    CatalogCalculateInput,
    CatalogClaim,
    CatalogEngineError,
    CatalogEngineGateError,
    accuracy_gate_passed,
    calculate_from_catalog,
)

router = APIRouter(prefix="/catalog-engine", tags=["catalog-engine"])


def _dec(value: str | int | float | Decimal | None, field_name: str) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid decimal for {field_name}",
        ) from exc


class CatalogClaimIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    compare_group_id: str
    amount: str = "0"


class CatalogCalculateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    assessment_year: str = Field(
        description=(
            "Interview YA (2018_19–2025_26). Engine years still use "
            "/calculate as the verified figure."
        )
    )
    employment_income: str = "0"
    business_income: str = "0"
    investment_income: str = "0"
    other_income: str = "0"
    solar_panel_relief: str = "0"
    rent_relief: str = "0"
    senior_citizen_interest_relief: str = "0"
    claims: list[CatalogClaimIn] = Field(default_factory=list)


@router.get(
    "/status",
    summary="Phase 8 catalog engine status (accuracy gate + supported years)",
)
def catalog_engine_status() -> dict[str, Any]:
    return {
        "engine": "catalog_rates_v1",
        "accuracy_gate_passed": accuracy_gate_passed(),
        "supported_assessment_years": list(CATALOG_YAS),
        "authority_years_use_calculate": sorted(ENGINE_AUTHORITY_YAS),
        "notes": (
            "POST /calculate remains the verified figure for 2024_25 / 2025_26. "
            "Catalog is an additional interview estimate for those years. "
            "Non-engine results carry an expandable "
            "'extracted from source, not independently verified' badge until "
            "rates/{ya}.json has needs_manual_verification cleared."
        ),
    }


@router.post(
    "/calculate",
    summary="Catalog-rate tax from extracted approved/rates JSON",
)
def catalog_calculate(body: CatalogCalculateRequest) -> dict[str, Any]:
    try:
        result = calculate_from_catalog(
            CatalogCalculateInput(
                assessment_year=body.assessment_year,
                employment_income=_dec(body.employment_income, "employment_income"),
                business_income=_dec(body.business_income, "business_income"),
                investment_income=_dec(body.investment_income, "investment_income"),
                other_income=_dec(body.other_income, "other_income"),
                solar_panel_relief=_dec(body.solar_panel_relief, "solar_panel_relief"),
                rent_relief=_dec(body.rent_relief, "rent_relief"),
                senior_citizen_interest_relief=_dec(
                    body.senior_citizen_interest_relief,
                    "senior_citizen_interest_relief",
                ),
                claims=tuple(
                    CatalogClaim(
                        compare_group_id=row.compare_group_id,
                        amount=_dec(row.amount, f"claims[{idx}].amount"),
                    )
                    for idx, row in enumerate(body.claims)
                ),
            )
        )
    except CatalogEngineGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except CatalogEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return result
