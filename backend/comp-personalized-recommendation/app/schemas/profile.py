"""Financial profile contracts (FR1, FR2 — Component 3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.shared.schemas.common import Currency, ORMBase, RiskTolerance, TimestampedSchema


class Occupation(StrEnum):
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    BUSINESS_OWNER = "business_owner"
    INVESTOR = "investor"
    PROFESSIONAL = "professional"
    OTHER = "other"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MaritalStatus(StrEnum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class IncomeSource(BaseModel):
    kind: str = Field(description="employment|business|rental|interest|dividend|capital_gain|other")
    monthly_amount: Decimal = Field(ge=0)
    currency: Currency = Currency.LKR
    is_taxable: bool = True


class FinancialProfileBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date
    gender: Gender = Gender.OTHER
    district: str = Field(default="Colombo", max_length=64)
    marital_status: MaritalStatus = MaritalStatus.SINGLE
    occupation: Occupation
    dependents: int = Field(ge=0, le=20, default=0)
    years_employed: int = Field(ge=0, le=60, default=0)

    gross_monthly_income: Decimal = Field(ge=0)
    monthly_expenses: Decimal = Field(ge=0)
    monthly_debt_service: Decimal = Field(ge=0, default=Decimal("0"))
    liquid_savings: Decimal = Field(ge=0, default=Decimal("0"))
    existing_investments: Decimal = Field(ge=0, default=Decimal("0"))
    total_debt: Decimal = Field(ge=0, default=Decimal("0"))
    epf_balance: Decimal = Field(ge=0, default=Decimal("0"))
    etf_balance: Decimal = Field(ge=0, default=Decimal("0"))

    health_insurance: bool = False
    life_insurance_premium_annual: Decimal = Field(ge=0, default=Decimal("0"))
    home_loan_interest_annual: Decimal = Field(ge=0, default=Decimal("0"))
    donations_annual: Decimal = Field(ge=0, default=Decimal("0"))

    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    investment_horizon_years: int = Field(ge=0, le=50, default=10)
    income_sources: list[IncomeSource] = Field(default_factory=list)

    tax_year: str = Field(default="2024_25", pattern=r"^\d{4}_\d{2}$")


class FinancialProfileCreate(FinancialProfileBase):
    pass


class FinancialProfileUpdate(BaseModel):
    full_name: str | None = None
    gender: Gender | None = None
    district: str | None = Field(default=None, max_length=64)
    marital_status: MaritalStatus | None = None
    occupation: Occupation | None = None
    dependents: int | None = Field(default=None, ge=0, le=20)
    years_employed: int | None = Field(default=None, ge=0, le=60)
    gross_monthly_income: Decimal | None = Field(default=None, ge=0)
    monthly_expenses: Decimal | None = Field(default=None, ge=0)
    monthly_debt_service: Decimal | None = Field(default=None, ge=0)
    liquid_savings: Decimal | None = Field(default=None, ge=0)
    existing_investments: Decimal | None = Field(default=None, ge=0)
    total_debt: Decimal | None = Field(default=None, ge=0)
    epf_balance: Decimal | None = Field(default=None, ge=0)
    etf_balance: Decimal | None = Field(default=None, ge=0)
    health_insurance: bool | None = None
    life_insurance_premium_annual: Decimal | None = Field(default=None, ge=0)
    home_loan_interest_annual: Decimal | None = Field(default=None, ge=0)
    donations_annual: Decimal | None = Field(default=None, ge=0)
    risk_tolerance: RiskTolerance | None = None
    investment_horizon_years: int | None = Field(default=None, ge=0, le=50)
    income_sources: list[IncomeSource] | None = None
    tax_year: str | None = Field(default=None, pattern=r"^\d{4}_\d{2}$")


class FinancialProfile(TimestampedSchema, FinancialProfileBase):
    """Full profile response."""


class DerivedFeatures(ORMBase):
    """Features computed from a profile for the ranker and impact engine."""

    profile_id: str
    age_years: int = Field(ge=0, le=120)
    disposable_income_monthly: Decimal
    disposable_income_annual: Decimal
    savings_rate: float = Field(ge=0, le=1)
    debt_to_income: float = Field(ge=0)
    liquidity_ratio: float = Field(ge=0)
    gross_annual_taxable_income: Decimal
    baseline_tax_liability_annual: Decimal
    effective_tax_rate: float = Field(ge=0, le=1)
    eligibility_flags: dict[str, bool] = Field(default_factory=dict)


__all__ = [
    "DerivedFeatures",
    "FinancialProfile",
    "FinancialProfileBase",
    "FinancialProfileCreate",
    "FinancialProfileUpdate",
    "Gender",
    "IncomeSource",
    "MaritalStatus",
    "Occupation",
]
