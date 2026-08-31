"""Monte Carlo projection of salary, tax, savings, and net worth (FR7, FR8)."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from impact.types import DeductionProfile, PathMatrices, ScenarioParams, SimulationResult, SimulationSnapshot


def _tax_vector(
    annual_income: np.ndarray,
    deductions: DeductionProfile,
    *,
    apply_deductions: Callable[..., float],
    compute_annual_tax: Callable[..., float],
    rules: Any,
) -> np.ndarray:
    out = np.empty(annual_income.shape[0], dtype=np.float64)
    for i, income in enumerate(annual_income):
        taxable = apply_deductions(
            annual_income=float(income),
            rules=rules,
            rent_paid_annual=deductions.rent_paid_annual,
            life_insurance_premium_annual=deductions.life_insurance_premium_annual,
            health_insurance_premium_annual=deductions.health_insurance_premium_annual,
            home_loan_interest_annual=deductions.home_loan_interest_annual,
            donations_annual=deductions.donations_annual,
            retirement_contribution_annual=deductions.retirement_contribution_annual,
        )
        out[i] = compute_annual_tax(taxable, rules)
    return out


def _run_paths(
    snapshot: SimulationSnapshot,
    *,
    horizon_years: int,
    n_paths: int,
    scenario: ScenarioParams,
    rules: Any,
    apply_deductions: Callable[..., float],
    compute_annual_tax: Callable[..., float],
    rng: np.random.Generator,
    use_strategy: bool,
    income_paths: list[list[float]] | None = None,
    adopted_mask: np.ndarray | None = None,
) -> PathMatrices:
    income = np.full(n_paths, snapshot.annual_income, dtype=np.float64)
    net_worth = np.full(
        n_paths,
        snapshot.liquid_savings + snapshot.existing_investments,
        dtype=np.float64,
    )
    monthly_exp = float(snapshot.monthly_expenses)
    monthly_debt = float(snapshot.monthly_debt_service)

    adopted = np.zeros(n_paths, dtype=bool)
    if adopted_mask is not None:
        adopted = adopted_mask.astype(bool, copy=False)
    elif use_strategy and snapshot.strategy_deductions is not None:
        adopted = rng.random(n_paths) < float(scenario.adoption_success_prob)

    years: list[int] = []
    salary_rows: list[list[float]] = []
    tax_rows: list[list[float]] = []
    savings_rows: list[list[float]] = []
    nw_rows: list[list[float]] = []

    for year in range(1, horizon_years + 1):
        if income_paths is not None:
            income = np.asarray(income_paths[year - 1], dtype=np.float64)
        else:
            growth = rng.normal(scenario.salary_growth_mean, scenario.salary_growth_std, size=n_paths)
            growth = np.clip(growth, -0.35, 0.50)
            income = np.maximum(0.0, income * (1.0 + growth))

        tax = np.zeros(n_paths, dtype=np.float64)
        for i in range(n_paths):
            ded = (
                snapshot.strategy_deductions
                if adopted[i] and snapshot.strategy_deductions is not None
                else snapshot.baseline_deductions
            )
            tax[i] = _tax_vector(
                np.array([income[i]]),
                ded,
                apply_deductions=apply_deductions,
                compute_annual_tax=compute_annual_tax,
                rules=rules,
            )[0]
            if adopted[i] and snapshot.strategy_tax_savings_rate > 0:
                tax[i] = max(
                    0.0,
                    tax[i] * (1.0 - float(snapshot.strategy_tax_savings_rate)),
                )

        infl = (1.0 + scenario.inflation_mean) ** year
        annual_expenses = monthly_exp * infl * 12.0
        annual_debt = monthly_debt * 12.0
        disposable = income - annual_expenses - annual_debt - tax
        savings = np.maximum(0.0, disposable)

        inv_ret = rng.normal(
            scenario.investment_return_mean,
            scenario.investment_return_std,
            size=n_paths,
        )
        inv_ret = np.clip(inv_ret, -0.40, 0.45)
        net_worth = np.maximum(0.0, net_worth * (1.0 + inv_ret) + savings)

        years.append(year)
        salary_rows.append(income.tolist())
        tax_rows.append(tax.tolist())
        savings_rows.append(savings.tolist())
        nw_rows.append(net_worth.tolist())

    return PathMatrices(
        years=years,
        salary=salary_rows,
        tax_liability=tax_rows,
        savings=savings_rows,
        net_worth=nw_rows,
    )


def _percentile(rows: list[list[float]], q: float) -> list[float]:
    """Percentile across *paths* for each year.

    ``rows`` is shaped ``(horizon_years, n_paths)``. Axis 1 is the path axis;
    axis 0 would percentile across years and then the yearly chart would plot
    the first ``horizon_years`` path-level values instead of a real fan chart.
    """
    arr = np.asarray(rows, dtype=np.float64)
    if arr.size == 0:
        return []
    axis = 1 if arr.ndim == 2 else 0
    return [float(x) for x in np.percentile(arr, q, axis=axis)]


def _summary_from_paths(
    baseline: PathMatrices,
    strategy: PathMatrices | None,
) -> dict[str, float]:
    if not baseline.years:
        return {
            "expected_total_savings": 0.0,
            "expected_net_worth": 0.0,
            "savings_std": 0.0,
            "value_at_risk_p10": 0.0,
            "probability_of_net_gain": 0.0,
        }

    base_tax = np.asarray(baseline.tax_liability, dtype=np.float64)
    base_nw = np.asarray(baseline.net_worth, dtype=np.float64)
    total_base_tax = base_tax.sum(axis=0)
    final_base_nw = base_nw[-1]

    if strategy is None:
        total_savings = np.zeros_like(total_base_tax)
        final_strat_nw = final_base_nw
    else:
        strat_tax = np.asarray(strategy.tax_liability, dtype=np.float64)
        strat_nw = np.asarray(strategy.net_worth, dtype=np.float64)
        total_savings = total_base_tax - strat_tax.sum(axis=0)
        final_strat_nw = strat_nw[-1]

    net_gain = final_strat_nw - final_base_nw
    return {
        "expected_total_savings": float(np.mean(total_savings)),
        "expected_net_worth": float(np.mean(final_strat_nw)),
        "savings_std": float(np.std(total_savings)),
        "value_at_risk_p10": float(np.percentile(net_gain, 10)),
        "probability_of_net_gain": float(np.mean(net_gain > 0)),
    }


def run_monte_carlo(
    snapshot: SimulationSnapshot,
    *,
    horizon_years: int,
    n_paths: int,
    scenario: ScenarioParams,
    rules: Any,
    apply_deductions: Callable[..., float],
    compute_annual_tax: Callable[..., float],
    random_seed: int | None = None,
    include_strategy_paths: bool = True,
) -> SimulationResult:
    """Simulate baseline and optional strategy paths."""
    rng = np.random.default_rng(random_seed)
    baseline_paths = _run_paths(
        snapshot,
        horizon_years=horizon_years,
        n_paths=n_paths,
        scenario=scenario,
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        rng=rng,
        use_strategy=False,
    )

    strategy_paths = None
    if include_strategy_paths and snapshot.strategy_deductions is not None:
        adopt_seed = None if random_seed is None else random_seed + 1
        adopt_rng = np.random.default_rng(adopt_seed)
        adopted_mask = adopt_rng.random(n_paths) < float(scenario.adoption_success_prob)
        inv_seed = None if random_seed is None else random_seed + 2
        inv_rng = np.random.default_rng(inv_seed)
        strategy_paths = _run_paths(
            snapshot,
            horizon_years=horizon_years,
            n_paths=n_paths,
            scenario=scenario,
            rules=rules,
            apply_deductions=apply_deductions,
            compute_annual_tax=compute_annual_tax,
            rng=inv_rng,
            use_strategy=True,
            income_paths=baseline_paths.salary,
            adopted_mask=adopted_mask.astype(bool),
        )

    return SimulationResult(
        baseline_paths=baseline_paths,
        strategy_paths=strategy_paths,
        summary=_summary_from_paths(baseline_paths, strategy_paths),
    )


def median_projection(paths: PathMatrices) -> list[dict[str, float]]:
    """P50 (median) yearly projection across paths."""
    if not paths.years:
        return []
    p50_salary = _percentile(paths.salary, 50)
    p50_tax = _percentile(paths.tax_liability, 50)
    p50_savings = _percentile(paths.savings, 50)
    p50_nw = _percentile(paths.net_worth, 50)
    return [
        {
            "year": paths.years[i],
            "projected_salary": p50_salary[i],
            "projected_tax_liability": p50_tax[i],
            "projected_savings": p50_savings[i],
            "net_worth": p50_nw[i],
        }
        for i in range(len(paths.years))
    ]


def projection_bands(paths: PathMatrices, *, field: str) -> list[dict[str, float]]:
    """P10 / P50 / P90 bands for net worth or tax liability."""
    rows = paths.net_worth if field == "net_worth" else paths.tax_liability
    p10 = _percentile(rows, 10)
    p50 = _percentile(rows, 50)
    p90 = _percentile(rows, 90)
    return [
        {"year": paths.years[i], "p10": p10[i], "p50": p50[i], "p90": p90[i]}
        for i in range(len(paths.years))
    ]


__all__ = [
    "median_projection",
    "projection_bands",
    "run_monte_carlo",
]
