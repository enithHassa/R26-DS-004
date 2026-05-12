"""Tax Filing 2025/26 — Random Forest tax prediction endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from tax_opt_b_app.services.tax_opt_b_rf_predictor import RfModelBundle, load_rf_bundle, predict_rf_tax
from tax_opt_b_app.tax_opt_b_schemas_rf_tax_v1 import (
    RF_TAX_DISCLAIMER,
    TaxOptBRfTaxPredictRequestV1,
    TaxOptBRfTaxPredictResponseV1,
)

router = APIRouter(tags=["tax-filing-2026"])


def _get_rf_bundle(request: Request) -> RfModelBundle:
    """Retrieve preloaded RF bundle from app state or raise 503."""
    bundle: RfModelBundle | None = getattr(request.app.state, "rf_tax_bundle", None)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RF tax model not loaded. Run tax_opt_b_rf_train.py to generate the artifact, "
                "then restart the server."
            ),
        )
    return bundle


@router.post(
    "/rf-predict",
    response_model=TaxOptBRfTaxPredictResponseV1,
    summary="Predict 2025/26 tax using Random Forest + SHAP explanation",
)
def rf_tax_predict(
    request: Request,
    body: TaxOptBRfTaxPredictRequestV1,
) -> TaxOptBRfTaxPredictResponseV1:
    if body.tax_year != "2025_26":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tax_year must be 2025_26 for this filing calculator.",
        )

    bundle = _get_rf_bundle(request)

    try:
        predicted_tax, shap_explanation = predict_rf_tax(body, bundle)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    total_gross = (
        float(body.annual_salary_income)
        + float(body.annual_business_income)
        + float(body.annual_investment_income)
        + float(body.annual_other_income)
    )
    total_relief = (
        float(body.relief_life_insurance_premium)
        + float(body.relief_health_insurance_premium)
        + float(body.relief_home_loan_interest)
        + float(body.relief_rent)
        + float(body.relief_charitable_donations)
        + float(body.relief_retirement_contribution)
    )

    return TaxOptBRfTaxPredictResponseV1(
        predicted_tax_lkr=str(int(predicted_tax)),
        total_gross_income_lkr=str(int(round(total_gross))),
        total_relief_claimed_lkr=str(int(round(total_relief))),
        shap_explanation=shap_explanation,
        model_id=bundle.model_id,
        feature_version=bundle.feature_version,
        disclaimer=RF_TAX_DISCLAIMER,
    )
