"""Schemas for the Random Forest tax prediction endpoint (2025/26 filing calculator)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBEmploymentTypeV1
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import TaxOptBShapExplanationV1

RF_TAX_DISCLAIMER = (
    "This estimate is produced by a Random Forest model trained on synthetic Sri Lankan "
    "APIT-style data for the 2025/26 assessment year. It is not legal or filing advice. "
    "Verify all figures against current Inland Revenue notices before any real filing."
)

RF_FEATURE_VERSION = "rf_v1"

RF_FEATURE_NAMES: tuple[str, ...] = (
    "annual_salary_income",
    "annual_business_income",
    "annual_investment_income",
    "annual_other_income",
    "dependents",
    "employment_type_code",
    "relief_life_insurance_premium",
    "relief_health_insurance_premium",
    "relief_home_loan_interest",
    "relief_rent",
    "relief_charitable_donations",
    "relief_retirement_contribution",
    "total_gross_income",
    "total_relief_claimed",
)


class TaxOptBRfTaxPredictRequestV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tax_year: str = Field(
        default="2025_26",
        description="Assessment year — fixed to 2025_26 for this filing calculator.",
    )
    employment_type: TaxOptBEmploymentTypeV1 = TaxOptBEmploymentTypeV1.EMPLOYEE
    dependents: int = Field(default=0, ge=0, le=20)

    annual_salary_income: Decimal = Field(default=Decimal("0"), ge=0)
    annual_business_income: Decimal = Field(default=Decimal("0"), ge=0)
    annual_investment_income: Decimal = Field(default=Decimal("0"), ge=0)
    annual_other_income: Decimal = Field(default=Decimal("0"), ge=0)

    # Relief amounts — no cap hints surfaced to the user; model and engine handle limits
    relief_life_insurance_premium: Decimal = Field(default=Decimal("0"), ge=0)
    relief_health_insurance_premium: Decimal = Field(default=Decimal("0"), ge=0)
    relief_home_loan_interest: Decimal = Field(default=Decimal("0"), ge=0)
    relief_rent: Decimal = Field(default=Decimal("0"), ge=0)
    relief_charitable_donations: Decimal = Field(default=Decimal("0"), ge=0)
    relief_retirement_contribution: Decimal = Field(default=Decimal("0"), ge=0)


class TaxOptBRfTaxPredictResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    predicted_tax_lkr: str = Field(description="RF-predicted annual tax (LKR, rounded to nearest rupee).")
    total_gross_income_lkr: str
    total_relief_claimed_lkr: str
    shap_explanation: TaxOptBShapExplanationV1
    model_id: str
    feature_version: str
    disclaimer: str = RF_TAX_DISCLAIMER


__all__ = [
    "RF_FEATURE_NAMES",
    "RF_FEATURE_VERSION",
    "RF_TAX_DISCLAIMER",
    "TaxOptBRfTaxPredictRequestV1",
    "TaxOptBRfTaxPredictResponseV1",
]
