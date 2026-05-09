"""Tax strategy catalog + generator contracts (FR3, FR4 — Component 3)."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.shared.schemas.common import ORMBase, RiskTolerance, TimestampedSchema


class StrategyCategory(StrEnum):
    DEDUCTION = "deduction"
    RELIEF = "relief"
    INVESTMENT = "investment"
    INSURANCE = "insurance"
    RETIREMENT = "retirement"
    STRUCTURE = "structure"
    OTHER = "other"


class EligibilityCheck(BaseModel):
    code: str
    description: str
    passed: bool
    value: float | str | None = None


class StrategyBase(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_\-]{2,40}$")
    name: str
    category: StrategyCategory
    description: str
    legal_reference: str | None = None
    min_income: Decimal | None = None
    max_income: Decimal | None = None
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    min_liquidity: Decimal | None = None
    risk_profile: RiskTolerance = RiskTolerance.MEDIUM
    effort_score: float = Field(ge=0, le=1, default=0.3)


class StrategyCreate(StrategyBase):
    pass


class Strategy(TimestampedSchema, StrategyBase):
    is_active: bool = True


class StrategyCandidate(ORMBase):
    """A strategy that passed feasibility checks for a given profile."""

    strategy: Strategy
    estimated_annual_savings: Decimal = Field(ge=0)
    estimated_annual_cost: Decimal = Field(ge=0, default=Decimal("0"))
    eligibility_checks: list[EligibilityCheck]
    feasibility_score: float = Field(ge=0, le=1)


class StrategyGenerationRequest(BaseModel):
    profile_id: str
    include_categories: list[StrategyCategory] | None = None
    exclude_codes: list[str] = Field(default_factory=list)


class StrategyGenerationResponse(BaseModel):
    profile_id: str
    candidates: list[StrategyCandidate]
    generated_at: str


__all__ = [
    "EligibilityCheck",
    "Strategy",
    "StrategyBase",
    "StrategyCandidate",
    "StrategyCategory",
    "StrategyCreate",
    "StrategyGenerationRequest",
    "StrategyGenerationResponse",
]
