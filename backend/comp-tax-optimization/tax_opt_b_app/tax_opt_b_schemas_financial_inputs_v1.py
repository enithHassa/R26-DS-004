"""Structured financial intake (Phase A) — maps to ``TaxOptBProfileV1`` + ``TaxOptBStrategyProposalV1``."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBEmploymentTypeV1


class TaxOptBInvestmentTaxTreatmentV1(StrEnum):
    """How an investment line participates in the MVP compliance path."""

    INFORMATIONAL = "informational"
    MAP_TO_RELIEF = "map_to_relief"


class TaxOptBDeductionLineV1(BaseModel):
    """User-facing deduction row; ``relief_code`` must match the active rules YAML."""

    model_config = ConfigDict(str_strip_whitespace=True)

    relief_code: str = Field(min_length=1, max_length=64)
    amount_annual: Decimal = Field(ge=0, description="Annual LKR amount proposed for this relief.")
    description: str | None = Field(default=None, max_length=256)


class TaxOptBInvestmentLineV1(BaseModel):
    """Investment / savings line; optional mapping into a statutory relief claim."""

    model_config = ConfigDict(str_strip_whitespace=True)

    investment_type: str = Field(min_length=1, max_length=128)
    amount_annual: Decimal = Field(ge=0)
    tax_treatment: TaxOptBInvestmentTaxTreatmentV1 = TaxOptBInvestmentTaxTreatmentV1.INFORMATIONAL
    relief_code: str | None = Field(
        default=None,
        max_length=64,
        description="Required when tax_treatment is map_to_relief (e.g. retirement_contribution).",
    )

    @model_validator(mode="after")
    def _relief_when_mapped(self) -> TaxOptBInvestmentLineV1:
        if self.tax_treatment == TaxOptBInvestmentTaxTreatmentV1.MAP_TO_RELIEF:
            if not self.relief_code or not self.relief_code.strip():
                raise ValueError("relief_code is required when tax_treatment is map_to_relief")
        return self


class TaxOptBFinancialInputsV1(BaseModel):
    """Sectioned financial questionnaire aligned with dissertation Step 1.

    Income basis for slabs and donation % caps is **gross only** (salary + business + other);
    there is no separate estimated taxable field (Option A).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    tax_year: str = Field(default="2024_25", pattern=r"^\d{4}_\d{2}$")
    employment_type: TaxOptBEmploymentTypeV1 = TaxOptBEmploymentTypeV1.EMPLOYEE
    dependents: int = Field(default=0, ge=0, le=20)

    annual_salary_income: Decimal = Field(default=Decimal("0"), ge=0)
    annual_business_income: Decimal = Field(default=Decimal("0"), ge=0)
    annual_investment_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Investment income (dividends, interest, rent) — IRD Form IT01 separate source.",
    )
    annual_other_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Other annual inflows included in gross for MVP caps.",
    )
    residency: str = Field(
        default="resident",
        description="'resident' (global income taxed) or 'non_resident' (Sri Lanka source only).",
        pattern=r"^(resident|non_resident)$",
    )

    deductions: list[TaxOptBDeductionLineV1] = Field(default_factory=list)
    investments: list[TaxOptBInvestmentLineV1] = Field(default_factory=list)
    strategy_notes: str | None = Field(default=None, max_length=2000)


__all__ = [
    "TaxOptBDeductionLineV1",
    "TaxOptBFinancialInputsV1",
    "TaxOptBInvestmentLineV1",
    "TaxOptBInvestmentTaxTreatmentV1",
]
