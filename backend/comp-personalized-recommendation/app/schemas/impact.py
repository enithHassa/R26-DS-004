"""Predictive Impact Engine contracts (FR7, FR8 — Component 3 primary research)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class Scenario(BaseModel):
    name: str = Field(description="baseline|adopt_strategy|custom")
    salary_growth_mean: float = Field(ge=-0.5, le=1.0, default=0.06)
    salary_growth_std: float = Field(ge=0, le=1.0, default=0.03)
    inflation_mean: float = Field(ge=-0.5, le=1.0, default=0.06)
    investment_return_mean: float = Field(ge=-0.5, le=1.0, default=0.08)
    adoption_success_prob: float = Field(ge=0, le=1, default=1.0)


class ImpactSimulationRequest(BaseModel):
    profile_id: UUID
    strategy_id: UUID | None = None
    strategy_code: str | None = Field(
        default=None,
        description="Catalog strategy key, e.g. S001_health_life_premium_optimisation",
    )
    strategy_codes: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Apply multiple strategies together (merged deduction profile).",
    )
    horizon_years: int = Field(ge=1, le=40, default=10)
    n_paths: int = Field(ge=100, le=50_000, default=2_000)
    random_seed: int | None = None
    scenario: Scenario = Field(default_factory=lambda: Scenario(name="baseline"))

    @model_validator(mode="after")
    def _validate_strategy_selection(self) -> ImpactSimulationRequest:
        if self.strategy_codes and (self.strategy_code or self.strategy_id):
            raise ValueError("Use strategy_codes OR strategy_code/strategy_id, not both")
        if self.strategy_code and self.strategy_id:
            raise ValueError("Provide only one of strategy_code or strategy_id")
        return self


class YearlyProjection(BaseModel):
    year: int
    projected_salary: Decimal
    projected_tax_liability: Decimal
    projected_savings: Decimal
    net_worth: Decimal


class ProjectionBand(BaseModel):
    """Risk bands across Monte Carlo paths for a single year."""

    year: int
    p10: Decimal
    p50: Decimal
    p90: Decimal


class ImpactSummary(BaseModel):
    horizon_years: int
    expected_total_savings: Decimal
    expected_net_worth: Decimal
    savings_std: Decimal
    value_at_risk_p10: Decimal
    probability_of_net_gain: float = Field(ge=0, le=1)


class ImpactSimulationResponse(BaseModel):
    run_id: UUID
    profile_id: UUID
    strategy_id: UUID | None
    horizon_years: int
    n_paths: int
    baseline: list[YearlyProjection]
    strategy_path: list[YearlyProjection] | None = None
    net_worth_bands: list[ProjectionBand]
    tax_liability_bands: list[ProjectionBand]
    summary: ImpactSummary


class StrategyComparisonRequest(BaseModel):
    profile_id: UUID
    strategy_ids: list[UUID] = Field(default_factory=list, max_length=10)
    strategy_codes: list[str] = Field(default_factory=list, max_length=10)
    horizon_years: int = Field(ge=1, le=40, default=10)

    @model_validator(mode="after")
    def _require_strategies(self) -> StrategyComparisonRequest:
        if not self.strategy_ids and not self.strategy_codes:
            raise ValueError("At least one of strategy_ids or strategy_codes is required")
        return self


__all__ = [
    "ImpactSimulationRequest",
    "ImpactSimulationResponse",
    "ImpactSummary",
    "ProjectionBand",
    "Scenario",
    "StrategyComparisonRequest",
    "YearlyProjection",
]
