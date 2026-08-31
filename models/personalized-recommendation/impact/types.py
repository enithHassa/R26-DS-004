"""Internal types for the Phase 5 predictive impact engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeductionProfile:
    """Annual deduction inputs passed to the rules engine."""

    rent_paid_annual: float = 0.0
    life_insurance_premium_annual: float = 0.0
    health_insurance_premium_annual: float = 0.0
    home_loan_interest_annual: float = 0.0
    donations_annual: float = 0.0
    retirement_contribution_annual: float = 0.0


@dataclass(frozen=True)
class SimulationSnapshot:
    """Starting financial state for a Monte Carlo run."""

    annual_income: float
    monthly_expenses: float
    monthly_debt_service: float
    liquid_savings: float
    existing_investments: float
    baseline_deductions: DeductionProfile
    strategy_deductions: DeductionProfile | None = None
    strategy_tax_savings_rate: float = 0.0


@dataclass(frozen=True)
class ScenarioParams:
    """Stochastic scenario knobs (mirrors API ``Scenario``)."""

    name: str = "baseline"
    salary_growth_mean: float = 0.06
    salary_growth_std: float = 0.03
    inflation_mean: float = 0.06
    investment_return_mean: float = 0.08
    investment_return_std: float = 0.04
    adoption_success_prob: float = 1.0


@dataclass
class YearSeries:
    """Per-year cross-path arrays (shape ``n_paths``)."""

    years: list[int] = field(default_factory=list)
    salary: list[float] = field(default_factory=list)
    tax_liability: list[float] = field(default_factory=list)
    savings: list[float] = field(default_factory=list)
    net_worth: list[float] = field(default_factory=list)


@dataclass
class PathMatrices:
    """Raw path-level outputs before aggregation."""

    years: list[int]
    salary: list[list[float]]
    tax_liability: list[list[float]]
    savings: list[list[float]]
    net_worth: list[list[float]]


@dataclass
class SimulationResult:
    """Aggregated Monte Carlo output."""

    baseline_paths: PathMatrices
    strategy_paths: PathMatrices | None
    summary: dict[str, float]


__all__ = [
    "DeductionProfile",
    "PathMatrices",
    "ScenarioParams",
    "SimulationResult",
    "SimulationSnapshot",
    "YearSeries",
]
