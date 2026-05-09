"""Function 3 — tabular feature rows aligned with ``feature_version: v1`` training.

Values are **post-engine**: total tax and savings use deterministic computation only.
Training pipelines must use the same column order as ``ML_FEATURE_COLUMN_NAMES_V1``.
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

_EMP_CODE: dict[TaxOptBEmploymentTypeV1, float] = {
    TaxOptBEmploymentTypeV1.EMPLOYEE: 0.0,
    TaxOptBEmploymentTypeV1.SELF_EMPLOYED: 1.0,
    TaxOptBEmploymentTypeV1.BUSINESS_OWNER: 2.0,
    TaxOptBEmploymentTypeV1.OTHER: 3.0,
}


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
