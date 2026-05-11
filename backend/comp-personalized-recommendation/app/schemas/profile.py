"""Financial profile contracts (FR1, FR2 — Component 3)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from backend.shared.schemas.common import Currency, ORMBase, RiskTolerance, TimestampedSchema


_PROVINCE_TO_DISTRICT: dict[str, str] = {
    "Western": "Colombo",
    "Central": "Kandy",
    "Southern": "Galle",
    "Northern": "Jaffna",
    "Eastern": "Trincomalee",
    "North Western": "Kurunegala",
    "North Central": "Anuradhapura",
    "Uva": "Badulla",
    "Sabaragamuwa": "Ratnapura",
}


def _age_band_midpoint(age_band: str) -> int:
    cleaned = age_band.strip()
    if cleaned.endswith("+"):
        return int(cleaned[:-1])
    if "-" in cleaned:
        lo, hi = cleaned.split("-", 1)
        return (int(lo) + int(hi)) // 2
    return int(cleaned)


def _normalize_profile_payload(data: object) -> object:
    """Accept both API-native and corrected synthetic CSV field names."""
    if not isinstance(data, dict):
        return data
    d = dict(data)

    # Province → district fallback.
    if ("district" not in d or not d.get("district")) and d.get("province"):
        d["district"] = _PROVINCE_TO_DISTRICT.get(str(d["province"]), "Colombo")

    # age_band → date_of_birth derivation.
    if not d.get("date_of_birth"):
        if d.get("age_band"):
            age_mid = _age_band_midpoint(str(d["age_band"]))
            snapshot_year = int(str(d.get("tax_year", "2024_25")).split("_", 1)[0]) + 1
            d["date_of_birth"] = date(snapshot_year - age_mid, 6, 30).isoformat()

    # Accept income_sources_json string and map to income_sources list.
    if "income_sources" not in d and d.get("income_sources_json"):
        try:
            d["income_sources"] = json.loads(str(d["income_sources_json"]))
        except json.JSONDecodeError:
            d["income_sources"] = []

    return d


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

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, data: object) -> object:
        return _normalize_profile_payload(data)


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

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, data: object) -> object:
        return _normalize_profile_payload(data)


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
