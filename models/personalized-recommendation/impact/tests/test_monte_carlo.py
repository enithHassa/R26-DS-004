"""Unit tests for the Phase 5 Monte Carlo impact engine."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ML_ROOT = Path(__file__).resolve().parents[2]
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from impact.monte_carlo import median_projection, projection_bands, run_monte_carlo  # noqa: E402
from impact.strategy_effects import estimate_first_year_tax_savings  # noqa: E402
from impact.types import DeductionProfile, PathMatrices, ScenarioParams, SimulationSnapshot  # noqa: E402
from rules.engine import load_tax_rules  # noqa: E402


RULES_PATH = ML_ROOT / "rules" / "sl_tax_2024_25.yaml"


@pytest.fixture()
def rules_engine():
    from rules.engine import apply_deductions, compute_annual_tax

    rules = load_tax_rules(RULES_PATH)
    return rules, apply_deductions, compute_annual_tax


def test_insurance_strategy_reduces_tax(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    ctx = {
        "annual_income": 3_600_000.0,
        "life_insurance_premium_annual_lkr": 20_000.0,
        "health_insurance_premium_annual_lkr": 10_000.0,
        "rent_paid_annual_lkr": 0.0,
        "donations_annual_lkr": 0.0,
        "home_loan_interest_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
    }
    _, savings = estimate_first_year_tax_savings(
        strategy_id="S001_health_life_premium_optimisation",
        estimation_type="deduction_cap_gap",
        context=ctx,
        rules=rules,
    )
    assert savings > 0.0


def test_monte_carlo_reproducible_with_seed(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    snapshot = SimulationSnapshot(
        annual_income=2_400_000.0,
        monthly_expenses=120_000.0,
        monthly_debt_service=30_000.0,
        liquid_savings=500_000.0,
        existing_investments=200_000.0,
        baseline_deductions=DeductionProfile(),
        strategy_deductions=DeductionProfile(life_insurance_premium_annual=100_000.0),
    )
    scenario = ScenarioParams(adoption_success_prob=1.0)

    a = run_monte_carlo(
        snapshot,
        horizon_years=5,
        n_paths=200,
        scenario=scenario,
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=42,
    )
    b = run_monte_carlo(
        snapshot,
        horizon_years=5,
        n_paths=200,
        scenario=scenario,
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=42,
    )
    assert a.summary == b.summary
    assert a.baseline_paths.net_worth == b.baseline_paths.net_worth


def test_strategy_paths_beat_baseline_on_average_tax(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    snapshot = SimulationSnapshot(
        annual_income=4_800_000.0,
        monthly_expenses=150_000.0,
        monthly_debt_service=40_000.0,
        liquid_savings=800_000.0,
        existing_investments=300_000.0,
        baseline_deductions=DeductionProfile(life_insurance_premium_annual=10_000.0),
        strategy_deductions=DeductionProfile(life_insurance_premium_annual=100_000.0),
    )
    result = run_monte_carlo(
        snapshot,
        horizon_years=8,
        n_paths=500,
        scenario=ScenarioParams(adoption_success_prob=1.0),
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=7,
    )
    assert result.strategy_paths is not None
    assert result.summary["expected_total_savings"] > 0.0
    assert result.summary["probability_of_net_gain"] >= 0.0


def test_projection_bands_ordered(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    snapshot = SimulationSnapshot(
        annual_income=2_000_000.0,
        monthly_expenses=90_000.0,
        monthly_debt_service=20_000.0,
        liquid_savings=400_000.0,
        existing_investments=100_000.0,
        baseline_deductions=DeductionProfile(),
    )
    result = run_monte_carlo(
        snapshot,
        horizon_years=3,
        n_paths=300,
        scenario=ScenarioParams(),
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=99,
        include_strategy_paths=False,
    )
    med = median_projection(result.baseline_paths)
    bands = projection_bands(result.baseline_paths, field="net_worth")
    assert len(med) == 3
    assert len(bands) == 3
    for row in bands:
        assert row["p10"] <= row["p50"] <= row["p90"]


def test_withholding_strategy_reduces_median_tax(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    ctx = {
        "annual_income": 4_800_000.0,
        "life_insurance_premium_annual_lkr": 0.0,
        "health_insurance_premium_annual_lkr": 0.0,
        "rent_paid_annual_lkr": 0.0,
        "donations_annual_lkr": 0.0,
        "home_loan_interest_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
    }
    from impact.strategy_effects import build_strategy_snapshot

    base_snapshot = SimulationSnapshot(
        annual_income=4_800_000.0,
        monthly_expenses=150_000.0,
        monthly_debt_service=40_000.0,
        liquid_savings=800_000.0,
        existing_investments=300_000.0,
        baseline_deductions=DeductionProfile(),
    )
    snapshot = build_strategy_snapshot(
        strategy_id="S007_employment_withholding_reconciliation",
        estimation_type="withholding_gap_estimate",
        context=ctx,
        rules=rules,
        snapshot=base_snapshot,
    )
    assert snapshot.strategy_tax_savings_rate > 0.0

    result = run_monte_carlo(
        snapshot,
        horizon_years=2,
        n_paths=500,
        scenario=ScenarioParams(adoption_success_prob=1.0),
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=42,
    )
    assert result.strategy_paths is not None
    baseline_med = median_projection(result.baseline_paths)
    strategy_med = median_projection(result.strategy_paths)
    for base_row, strat_row in zip(baseline_med, strategy_med, strict=True):
        assert strat_row["projected_tax_liability"] < base_row["projected_tax_liability"]
    assert result.summary["expected_total_savings"] > 0.0


def test_strategy_paths_use_same_income_as_baseline(rules_engine) -> None:
    rules, apply_deductions, compute_annual_tax = rules_engine
    snapshot = SimulationSnapshot(
        annual_income=3_600_000.0,
        monthly_expenses=120_000.0,
        monthly_debt_service=30_000.0,
        liquid_savings=500_000.0,
        existing_investments=200_000.0,
        baseline_deductions=DeductionProfile(),
        strategy_deductions=DeductionProfile(),
    )
    result = run_monte_carlo(
        snapshot,
        horizon_years=2,
        n_paths=100,
        scenario=ScenarioParams(adoption_success_prob=1.0),
        rules=rules,
        apply_deductions=apply_deductions,
        compute_annual_tax=compute_annual_tax,
        random_seed=42,
    )
    assert result.strategy_paths is not None
    for year_idx in range(2):
        assert result.baseline_paths.salary[year_idx] == result.strategy_paths.salary[year_idx]


    """Bands must percentile across paths for each year, not across years."""
    paths = PathMatrices(
        years=[1, 2],
        salary=[[10.0, 10.0], [20.0, 20.0]],
        tax_liability=[[100.0, 300.0], [1000.0, 3000.0]],
        savings=[[0.0, 0.0], [0.0, 0.0]],
        net_worth=[[0.0, 0.0], [0.0, 0.0]],
    )
    bands = projection_bands(paths, field="tax_liability")
    assert bands[0]["p50"] == 200.0
    assert bands[1]["p50"] == 2000.0
    assert bands[0]["p10"] == 120.0
    assert bands[0]["p90"] == 280.0
