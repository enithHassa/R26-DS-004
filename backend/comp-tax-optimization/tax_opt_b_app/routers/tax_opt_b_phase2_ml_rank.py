"""Phase 2 — ML-assisted strategy ranking with personalization."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from starlette.status import HTTP_424_FAILED_DEPENDENCY

from tax_opt_b_app.config import get_component_settings
from tax_opt_b_app.routers.tax_opt_b_compliance import _rules_pack_for_request
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import validate_relief_codes_used
from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService
from tax_opt_b_app.services.tax_opt_b_search_strategies import (
    evaluate_search_passing_rows,
    sort_passing_rows_rule_only,
)
from tax_opt_b_app.tax_opt_b_schemas_ml_rank_v1 import (
    MLRankRequestV1,
    MLRankResponseV1,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBSearchStrategiesMlRankRequestV1,
)

router = APIRouter(tags=["tax-opt-b-phase2-ml"])


def _convert_search_request_to_ml_rank_request(
    search_req: TaxOptBSearchStrategiesMlRankRequestV1,
) -> MLRankRequestV1:
    """Convert search request to ML rank request."""
    return MLRankRequestV1(
        tax_year=search_req.tax_year,
        salary=search_req.profile.annual_salary or 0,
        rental_income=search_req.profile.annual_rental_income or 0,
        interest_income=search_req.profile.annual_interest_income or 0,
        business_income=search_req.profile.annual_business_income or 0,
        life_insurance_premium=search_req.deductions.life_insurance_premium or 0,
        health_insurance_premium=search_req.deductions.health_insurance_premium or 0,
        home_loan_interest=search_req.deductions.home_loan_interest or 0,
        rent_relief=search_req.deductions.rent_relief or 0,
        charitable_donations=search_req.deductions.charitable_donations or 0,
        retirement_contribution=search_req.deductions.retirement_contribution or 0,
        complexity_tolerance=getattr(search_req, "complexity_tolerance", 3),
        audit_risk_tolerance=getattr(search_req, "audit_risk_tolerance", 3),
        time_available=getattr(search_req, "time_available", 3),
    )


@router.post(
    "/phase2-ml-rank",
    response_model=MLRankResponseV1,
    summary="Phase 2 ML-assisted ranking with personalization",
)
def phase2_ml_rank_strategies(
    request: Request,
    body: TaxOptBSearchStrategiesMlRankRequestV1,
) -> MLRankResponseV1:
    """
    Rank strategies using Phase 2 ML models with personalization.

    This endpoint:
    - Uses ML strategy ranking for more intelligent prioritization
    - Incorporates user complexity and risk preferences
    - Provides legal explanations for each strategy
    - Returns more distinct scores than simple rule-based ranking
    """

    # Validate relief codes
    pack = _rules_pack_for_request(request, body.tax_year)
    unknown = validate_relief_codes_used(body, pack.allowed_relief_codes)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unknown or disallowed relief_code in deductions or investments "
                f"(not in active rules pack): {', '.join(repr(c) for c in unknown)}"
            ),
        )

    # Check Phase 2 components are available
    ml_ranker = getattr(request.app.state, "ml_strategy_ranker", None)
    feature_engineer = getattr(request.app.state, "feature_engineer", None)
    legal_rag = getattr(request.app.state, "legal_rag", None)

    if not ml_ranker or not feature_engineer or not legal_rag:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Phase 2 ML components not loaded. Check server logs for initialization errors.",
        )

    try:
        # Evaluate passing strategies using compliance rules
        evaluation = evaluate_search_passing_rows(body, pack)
        gross = evaluation.profile.annual_gross_income

        # Sort strategies by rules first
        passing_sorted = sort_passing_rows_rule_only(
            list(evaluation.passing_rows),
            rank_by=body.rank_by,
            gross=gross,
        )

        if not passing_sorted:
            raise ValueError("No strategies passed compliance evaluation")

        # Convert to strategy grid format for ML ranker
        strategies_grid = []
        for row in passing_sorted:
            candidate = row[0]
            strategies_grid.append({
                "id": candidate.candidate_id,
                "name": candidate.candidate_display_name,
                "reliefs": candidate.reliefs,
                "description": candidate.candidate_display_name,
            })

        # Convert request format
        ml_rank_request = _convert_search_request_to_ml_rank_request(body)

        # Use ML ranking service
        ml_service = MLRankingService(
            ml_strategy_ranker=ml_ranker,
            feature_engineer=feature_engineer,
            legal_rag=legal_rag,
        )

        response = ml_service.rank_strategies(
            request=ml_rank_request,
            rules_pack=pack,
            strategies_grid=strategies_grid,
        )

        return response

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML ranking failed: {str(exc)}",
        ) from exc
