"""Generate the v2 training table parquet for Function 3 ML ranking.

Reads taxpayer personas from the Excel file, runs the backend tax engine for each persona
over all 2^n strategy candidates, and writes a long-format parquet with one row per
(taxpayer, candidate) pair.

New in v2: adds ``liquidity_cost_lkr``, ``liquidity_to_income_ratio``, ``n_high_cost_reliefs``
columns so the training script can build the multi-objective utility target.

Usage
-----
    python models/tax-optimization/datasets/build_training_table_v2.py \\
        --out models/tax-optimization/datasets/ml/training_v2.parquet

Requires the backend package to be importable (run from repo root with the venv activated):
    cd d:/R26-DS-004/R26-DS-004
    pip install -e backend/comp-tax-optimization
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── backend path setup ────────────────────────────────────────────────────────
# Supports running directly from repo root without editable install.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_SRC = _REPO_ROOT / "backend" / "comp-tax-optimization"
if _BACKEND_SRC.is_dir():
    sys.path.insert(0, str(_BACKEND_SRC))

# ── backend imports ────────────────────────────────────────────────────────────
try:
    from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import (
        profile_from_financial_inputs,
        relief_max_claim_amounts_by_code,
    )
    from tax_opt_b_app.services.tax_opt_b_ml_features_v1 import (
        RELIEF_LIQUIDITY_WEIGHT,
        compute_liquidity_cost,
    )
    from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules_cached as load_rules_pack
    from tax_opt_b_app.services.tax_opt_b_search_strategies import (
        enumerate_candidate_specs,
    )
    from tax_opt_b_app.services.tax_opt_b_tax_computation import run_compliance_and_compute_tax
    from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
except ImportError as exc:
    print(
        f"error: cannot import backend modules — {exc}\n"
        "Run from the repo root with the backend virtualenv active:\n"
        "  pip install -e backend/comp-tax-optimization",
        file=sys.stderr,
    )
    sys.exit(1)

DEFAULT_PERSONAS_XLSX = (
    Path(__file__).resolve().parent / "ml" / "training_persona_5000_taxpayers.xlsx"
)
DEFAULT_RULES_YAML = (
    Path(__file__).resolve().parents[1]
    / "rules" / "compiled" / "it22064486_2024_25.yaml"
)
DEFAULT_OUT = Path(__file__).resolve().parent / "ml" / "training_v2.parquet"
MAX_CANDIDATES = 256


def _load_personas(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _persona_to_financial_inputs(row: pd.Series) -> TaxOptBFinancialInputsV1:
    return TaxOptBFinancialInputsV1(
        tax_year=str(row["tax_year"]),
        employment_type=str(row["employment_type"]),
        dependents=int(row.get("dependents", 0) or 0),
        annual_salary_income=str(int(row.get("annual_salary_income", 0) or 0)),
        annual_business_income=str(int(row.get("annual_business_income", 0) or 0)),
        annual_other_income=str(int(row.get("annual_other_income", 0) or 0)),
    )


def build_table(
    personas: pd.DataFrame,
    rules_yaml: Path,
    *,
    max_taxpayers: int | None,
    random_state: int,
) -> pd.DataFrame:
    pack = load_rules_pack(rules_yaml)
    ordered_codes = sorted(relief_max_claim_amounts_by_code(
        profile_from_financial_inputs(
            _persona_to_financial_inputs(personas.iloc[0])
        ),
        pack,
    ).keys())

    if max_taxpayers is not None and max_taxpayers < len(personas):
        rng = np.random.default_rng(random_state)
        idx = rng.choice(len(personas), size=max_taxpayers, replace=False)
        personas = personas.iloc[sorted(idx)].reset_index(drop=True)

    records: list[dict] = []
    n_taxpayers = len(personas)

    for i, (_, row) in enumerate(personas.iterrows()):
        if i % 500 == 0:
            print(f"  {i}/{n_taxpayers} taxpayers processed...", file=sys.stderr)

        taxpayer_id = str(row["taxpayer_id"])
        try:
            fin = _persona_to_financial_inputs(row)
            profile = profile_from_financial_inputs(fin)
            amounts = relief_max_claim_amounts_by_code(profile, pack)
            specs = enumerate_candidate_specs(profile, pack, max_candidates=MAX_CANDIDATES)
        except Exception as exc:
            print(f"  skip {taxpayer_id}: {exc}", file=sys.stderr)
            continue

        # Baseline tax (cap_subset_0 = no reliefs)
        baseline_spec = specs[0]
        baseline_strategy = baseline_spec.to_strategy_proposal(amounts)
        baseline_out = run_compliance_and_compute_tax(profile, baseline_strategy, pack)
        if not baseline_out.compliance.passed or baseline_out.tax_computation is None:
            continue
        baseline_tax = float(baseline_out.tax_computation.total_tax)

        gross = float(profile.annual_gross_income)
        sal = float(fin.annual_salary_income)
        bus = float(fin.annual_business_income)
        oth = float(fin.annual_other_income)
        n_ordered = len(ordered_codes)

        # Rule rank counter (for secondary target)
        passing_taxes: list[tuple[float, int]] = []  # (tax, mask)

        for spec in specs:
            strategy = spec.to_strategy_proposal(amounts)
            out = run_compliance_and_compute_tax(profile, strategy, pack)
            if not out.compliance.passed or out.tax_computation is None:
                continue

            tax = float(out.tax_computation.total_tax)
            mask = int(spec.candidate_id.rsplit("_", 1)[-1], 10)
            savings = max(baseline_tax - tax, 0.0)

            # Liquidity cost features
            liq_cost, n_high = compute_liquidity_cost(spec.included_relief_codes, amounts)
            liq_ratio = liq_cost / gross if gross > 0.0 else 0.0

            passing_taxes.append((tax, mask))
            records.append(
                {
                    "taxpayer_id": taxpayer_id,
                    "tax_year": fin.tax_year,
                    "employment_type": str(profile.employment_type.value),
                    "dependents": profile.dependents,
                    "annual_salary_income": sal,
                    "annual_business_income": bus,
                    "annual_other_income": oth,
                    "annual_gross_income": gross,
                    "n_ordered_relief_codes": n_ordered,
                    "n_included_relief_codes": len(spec.included_relief_codes),
                    "candidate_mask": mask,
                    "included_relief_codes": ",".join(sorted(spec.included_relief_codes)),
                    "total_tax_lkr": tax,
                    "baseline_tax_lkr": baseline_tax,
                    "savings_vs_baseline_lkr": savings,
                    # v2 liquidity features
                    "liquidity_cost_lkr": liq_cost,
                    "liquidity_to_income_ratio": liq_ratio,
                    "n_high_cost_reliefs": float(n_high),
                }
            )

        # Assign rule_rank_among_passing (sort by total_tax asc, mask tie-break)
        passing_taxes_sorted = sorted(passing_taxes, key=lambda t: (t[0], t[1]))
        rank_map = {mask: rank + 1 for rank, (_, mask) in enumerate(passing_taxes_sorted)}
        for rec in records[-len(passing_taxes):]:
            rec["rule_rank_among_passing"] = rank_map[rec["candidate_mask"]]

    df = pd.DataFrame(records)
    print(f"\nGenerated {len(df)} rows from {n_taxpayers} taxpayers.", file=sys.stderr)
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--personas", type=Path, default=DEFAULT_PERSONAS_XLSX)
    ap.add_argument("--rules-yaml", type=Path, default=DEFAULT_RULES_YAML)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-taxpayers", type=int, default=None)
    ap.add_argument("--random-state", type=int, default=42)
    args = ap.parse_args(argv)

    personas = _load_personas(args.personas)
    print(f"Loaded {len(personas)} personas from {args.personas}", file=sys.stderr)

    df = build_table(
        personas,
        args.rules_yaml,
        max_taxpayers=args.max_taxpayers,
        random_state=args.random_state,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"Wrote {args.out} ({len(df)} rows, {df.shape[1]} columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
