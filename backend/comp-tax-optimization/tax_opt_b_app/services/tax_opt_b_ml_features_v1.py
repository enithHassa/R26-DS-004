"""Function 3 — tabular feature rows aligned with ``feature_version: v1`` / ``v2`` training.

Values are **post-engine**: total tax and savings use deterministic computation only.
Training pipelines must use the same column order as ``ML_FEATURE_COLUMN_NAMES_V1`` (v1)
or ``ML_FEATURE_COLUMN_NAMES_V2`` (v2 — adds liquidity cost features for multi-objective
Pareto utility ranking).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import numpy as np

from tax_opt_b_app.services.tax_opt_b_search_strategies import PassingRowTuple, SearchPassingEvaluation
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBEmploymentTypeV1

ML_FEATURE_COLUMN_NAMES_V1: tuple[str, ...] = (
    "annual_gross_income",
    "annual_salary_income",
    "annual_business_income",
    "annual_other_income",
    "dependents",
    "employment_type_code",
    "n_ordered_relief_codes",
    "n_included_relief_codes",
    "candidate_mask",
    "total_tax_lkr",
    "baseline_tax_lkr",
    "savings_vs_baseline_lkr",
)

ML_FEATURE_COLUMN_NAMES_V1_NO_SAVINGS: tuple[str, ...] = ML_FEATURE_COLUMN_NAMES_V1[:-1]

# v2 layout: adds three liquidity cost features for multi-objective Pareto utility ranking.
# Target for v2 is utility_score (not savings), so all 14 columns are inputs (no exclusion).
ML_FEATURE_COLUMN_NAMES_V2: tuple[str, ...] = (
    "annual_gross_income",
    "annual_salary_income",
    "annual_business_income",
    "annual_other_income",
    "dependents",
    "employment_type_code",
    "n_ordered_relief_codes",
    "n_included_relief_codes",
    "candidate_mask",
    "total_tax_lkr",
    "baseline_tax_lkr",
    "liquidity_cost_lkr",       # weighted cash cost of claiming all included reliefs
    "liquidity_to_income_ratio", # liquidity_cost / gross_income (0..1 scale)
    "n_high_cost_reliefs",       # count of reliefs with liquidity weight >= 0.8
)

_EMP_CODE: dict[TaxOptBEmploymentTypeV1, float] = {
    TaxOptBEmploymentTypeV1.EMPLOYEE: 0.0,
    TaxOptBEmploymentTypeV1.SELF_EMPLOYED: 1.0,
    TaxOptBEmploymentTypeV1.BUSINESS_OWNER: 2.0,
    TaxOptBEmploymentTypeV1.OTHER: 3.0,
}

# How much of the claimed cap amount represents real upfront cash outflow.
# 1.0 = must spend / lock away the full claimed amount.
# 0.1 = already paying this cost (near-zero incremental cash needed).
# 0.0 = zero extra cash (paying rent regardless).
RELIEF_LIQUIDITY_WEIGHT: dict[str, float] = {
    "retirement_contribution": 1.0,   # must lock cash into retirement fund
    "life_insurance_premium": 1.0,    # must pay premium
    "charitable_donations": 1.0,      # real cash donated
    "health_insurance_premium": 0.8,  # may already have a policy; partial incremental cost
    "home_loan_interest": 0.1,        # already servicing the loan; near-zero extra cash
    "rent_relief": 0.0,               # already paying rent; zero incremental cash
}


def compute_liquidity_cost(
    included_relief_codes: tuple[str, ...],
    claimed_amounts: dict[str, Decimal],
) -> tuple[float, int]:
    """Return (weighted_liquidity_cost_lkr, n_high_cost_reliefs) for a candidate.

    ``claimed_amounts`` maps relief_code -> max-cap amount from the rules engine.
    High-cost reliefs are those with RELIEF_LIQUIDITY_WEIGHT >= 0.8.
    """
    total = 0.0
    high_cost_count = 0
    for code in included_relief_codes:
        claimed = float(claimed_amounts.get(code, Decimal(0)))
        weight = RELIEF_LIQUIDITY_WEIGHT.get(code, 0.5)
        total += claimed * weight
        if weight >= 0.8:
            high_cost_count += 1
    return total, high_cost_count


def build_ml_feature_matrix_v1(
    evaluation: SearchPassingEvaluation,
    passing_rows: list[PassingRowTuple],
    *,
    baseline_tax: Decimal | None,
    matrix_layout: Literal["v1_12_full", "v1_11_no_savings"] = "v1_12_full",
) -> np.ndarray:
    """One row per legal candidate in ``passing_rows`` order (float64).

    ``v1_12_full`` includes ``savings_vs_baseline_lkr`` (legacy / rank-only probes).
    ``v1_11_no_savings`` matches research regressors trained without target leakage.
    """
    fin = evaluation.financial_inputs
    profile = evaluation.profile
    ordered_n = len(evaluation.ordered_relief_codes)
    gross_f = float(profile.annual_gross_income)
    sal_f = float(fin.annual_salary_income)
    bus_f = float(fin.annual_business_income)
    oth_f = float(fin.annual_other_income)
    dep_f = float(profile.dependents)
    et = profile.employment_type
    et_code = _EMP_CODE.get(et, 3.0)
    base_f = float(baseline_tax) if baseline_tax is not None else float("nan")

    ncols = 12 if matrix_layout == "v1_12_full" else 11
    out = np.zeros((len(passing_rows), ncols), dtype=np.float64)
    for i, (spec, _out, tax) in enumerate(passing_rows):
        tax_f = float(tax)
        sav = float(baseline_tax - tax) if baseline_tax is not None else 0.0
        if sav < 0.0:
            sav = 0.0
        mask = int(spec.candidate_id.rsplit("_", 1)[-1], 10)
        row12 = (
            gross_f,
            sal_f,
            bus_f,
            oth_f,
            dep_f,
            et_code,
            float(ordered_n),
            float(len(spec.included_relief_codes)),
            float(mask),
            tax_f,
            base_f,
            sav,
        )
        if matrix_layout == "v1_12_full":
            out[i, :] = row12
        else:
            out[i, :] = row12[:-1]
    return out


def build_ml_feature_matrix_v2(
    evaluation: SearchPassingEvaluation,
    passing_rows: list[PassingRowTuple],
    *,
    baseline_tax: Decimal | None,
    claimed_amounts: dict[str, Decimal],
) -> np.ndarray:
    """v2 feature matrix: 14 columns including three liquidity cost features.

    Used with models trained on ``utility_score`` target (multi-objective Pareto ranking).
    ``claimed_amounts`` is the max-cap amount per relief code for this taxpayer profile,
    from ``relief_max_claim_amounts_by_code(profile, pack)``.

    Column order matches ``ML_FEATURE_COLUMN_NAMES_V2``.
    """
    fin = evaluation.financial_inputs
    profile = evaluation.profile
    ordered_n = len(evaluation.ordered_relief_codes)
    gross_f = float(profile.annual_gross_income)
    sal_f = float(fin.annual_salary_income)
    bus_f = float(fin.annual_business_income)
    oth_f = float(fin.annual_other_income)
    dep_f = float(profile.dependents)
    et = profile.employment_type
    et_code = _EMP_CODE.get(et, 3.0)
    base_f = float(baseline_tax) if baseline_tax is not None else float("nan")

    out = np.zeros((len(passing_rows), 14), dtype=np.float64)
    for i, (spec, _out, tax) in enumerate(passing_rows):
        tax_f = float(tax)
        mask = int(spec.candidate_id.rsplit("_", 1)[-1], 10)
        liq_cost, n_high = compute_liquidity_cost(spec.included_relief_codes, claimed_amounts)
        liq_ratio = (liq_cost / gross_f) if gross_f > 0.0 else 0.0
        out[i, :] = (
            gross_f,
            sal_f,
            bus_f,
            oth_f,
            dep_f,
            et_code,
            float(ordered_n),
            float(len(spec.included_relief_codes)),
            float(mask),
            tax_f,
            base_f,
            liq_cost,
            liq_ratio,
            float(n_high),
        )
    return out
