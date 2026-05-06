"""Post-hoc recalibration of synthetic numeric marginals to reference.

Uses rank-based quantile mapping so selected synthetic columns closely match
the reference distribution while preserving row ordering/monotonic relations.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def quantile_map_to_reference(syn: pd.Series, ref: pd.Series) -> pd.Series:
    x = syn.to_numpy(dtype=float)
    r = ref.to_numpy(dtype=float)
    x = np.where(np.isfinite(x), x, 0.0)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return pd.Series(x, index=syn.index)
    r_sorted = np.sort(r)
    n = len(x)
    # rank positions in [0,1]
    order = np.argsort(x, kind="mergesort")
    q = (np.arange(n, dtype=float) + 0.5) / n
    mapped = np.empty(n, dtype=float)
    mapped_vals = np.quantile(r_sorted, q, method="linear")
    mapped[order] = mapped_vals
    return pd.Series(mapped, index=syn.index)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-csv", type=Path, required=True)
    p.add_argument("--synthetic-csv", type=Path, required=True)
    p.add_argument("--out-csv", type=Path, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ref = pd.read_csv(args.reference_csv)
    syn = pd.read_csv(args.synthetic_csv)

    target_cols = [
        "gross_monthly_income_lkr",
        "monthly_expenses_lkr",
        "liquid_savings_lkr",
        "gross_annual_taxable_income_lkr",
    ]
    for c in target_cols:
        if c in ref.columns and c in syn.columns:
            syn[c] = quantile_map_to_reference(syn[c], ref[c]).clip(lower=0.0).round(2)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    syn.to_csv(args.out_csv, index=False)
    print(f"[recalibrate] wrote {args.out_csv} rows={len(syn)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

