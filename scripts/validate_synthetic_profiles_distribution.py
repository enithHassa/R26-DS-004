"""Distribution validation: synthetic profiles vs mapped reference (statistical).

Runs Kolmogorov–Smirnov tests on continuous fields, chi-square on categorical
margins (merged sparse buckets), Jensen–Shannon divergence on income-source
signatures, and optional t-SNE overlap diagnostics.

Example::

    python scripts/validate_synthetic_profiles_distribution.py \\
        --reference-csv data/synthetic/reference_matched/ey_reference_profiles_fmt.csv \\
        --synthetic-csv data/synthetic/reference_matched/profiles_reference_matched.csv \\
        --report-json data/synthetic/reference_matched/validation_report.json

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import distance


def _col_present(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _income_signature(js: str) -> str:
    try:
        data = json.loads(js)
        kinds = sorted(str(x.get("kind", "")) for x in data)
        return "+".join(kinds)
    except json.JSONDecodeError:
        return "invalid"


def ks_report(real: np.ndarray, syn: np.ndarray, label: str) -> dict:
    real = np.asarray(real, dtype=float)
    syn = np.asarray(syn, dtype=float)
    real = real[np.isfinite(real)]
    syn = syn[np.isfinite(syn)]
    stat, p = stats.ks_2samp(real, syn, alternative="two-sided", mode="auto")
    return {"variable": label, "statistic": float(stat), "p_value": float(p), "n_real": len(real), "n_syn": len(syn)}


def chi_square_report(real: pd.Series, syn: pd.Series, label: str) -> dict:
    vc_ref = real.astype(str).value_counts()
    keep = set(vc_ref[vc_ref >= 5].index)

    def bucket(x: str) -> str:
        xs = str(x)
        return xs if xs in keep else "_other_"

    r = real.astype(str).map(bucket)
    s = syn.astype(str).map(bucket)
    cats = sorted(set(r.unique()) | set(s.unique()))
    obs = np.array([(s == c).sum() for c in cats], dtype=float)
    p_ref = np.array([(r == c).mean() for c in cats], dtype=float)
    expected = p_ref * obs.sum()
    mask = expected >= 5
    obs_m = obs[mask]
    exp_m = expected[mask]
    if len(obs_m) < 2 or exp_m.sum() == 0:
        return {"variable": label, "note": "too_sparse_after_merge", "p_value": None}
    chi2, p = stats.chisquare(obs_m, f_exp=exp_m)
    dof = len(obs_m) - 1
    return {
        "variable": label,
        "chi2": float(chi2),
        "dof": int(dof),
        "p_value": float(p),
        "categories_used": int(mask.sum()),
    }


def js_signature_report(real_js: pd.Series, syn_js: pd.Series) -> dict:
    r_sig = real_js.map(_income_signature)
    s_sig = syn_js.map(_income_signature)
    vocab = sorted(set(r_sig.unique()) | set(s_sig.unique()))
    pr = np.array([(r_sig == v).mean() for v in vocab], dtype=float)
    ps = np.array([(s_sig == v).mean() for v in vocab], dtype=float)
    ps = ps / ps.sum() if ps.sum() else ps
    pr = pr / pr.sum() if pr.sum() else pr
    # scipy expects finite positive distributions; pad epsilon
    eps = 1e-12
    pr = pr + eps
    ps = ps + eps
    pr /= pr.sum()
    ps /= ps.sum()
    jsd = float(distance.jensenshannon(pr, ps, base=2))
    return {"variable": "income_source_signature_js_divergence", "js_divergence_h": jsd, "vocab_size": len(vocab)}


def tsne_separation_summary(
    real_df: pd.DataFrame,
    syn_df: pd.DataFrame,
    seed: int,
    max_samples: int = 2500,
) -> dict:
    try:
        from sklearn.manifold import TSNE
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return {"note": "sklearn_not_installed"}

    num_cols = [
        "dependents",
        "years_employed",
        "gross_monthly_income_lkr",
        "monthly_expenses_lkr",
        "monthly_debt_service_lkr",
        "liquid_savings_lkr",
        "existing_investments_lkr",
        "total_debt_lkr",
        "epf_balance_lkr",
        "etf_balance_lkr",
        "baseline_tax_liability_lkr",
        "effective_tax_rate",
        "disposable_income_monthly_lkr",
        "savings_rate",
        "debt_to_income",
    ]
    rng = np.random.default_rng(seed)
    r_sub = real_df.sample(min(len(real_df), max_samples), random_state=int(seed))
    s_sub = syn_df.sample(min(len(syn_df), max_samples), random_state=int(seed) + 1)
    Xr = np.log1p(np.clip(r_sub[num_cols].to_numpy(dtype=float), 0, None))
    Xs = np.log1p(np.clip(s_sub[num_cols].to_numpy(dtype=float), 0, None))
    X = np.vstack([Xr, Xs])
    y = np.array([0] * len(Xr) + [1] * len(Xs))
    Xs_std = StandardScaler().fit_transform(X)
    embed = TSNE(n_components=2, perplexity=30, random_state=seed, max_iter=400).fit_transform(Xs_std)
    er = embed[y == 0]
    es = embed[y == 1]
    mr = er.mean(axis=0)
    ms = es.mean(axis=0)
    between = float(np.linalg.norm(mr - ms))
    intra_r = np.linalg.norm(er - mr, axis=1).mean()
    intra_s = np.linalg.norm(es - ms, axis=1).mean()
    intra = float((intra_r + intra_s) / 2)
    ratio = between / intra if intra > 1e-9 else None
    return {
        "method": "TSNE_log1p_numeric_features",
        "n_real_used": len(Xr),
        "n_syn_used": len(Xs),
        "mean_between_centroids": between,
        "mean_intra_cloud": intra,
        "between_over_intra": ratio,
        "interpretation_low_ratio_clusters_together": ratio is not None and ratio < 0.35,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-csv", type=Path, required=True)
    p.add_argument("--synthetic-csv", type=Path, required=True)
    p.add_argument("--report-json", type=Path, default=None)
    p.add_argument("--tsne", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ref = pd.read_csv(args.reference_csv)
    syn = pd.read_csv(args.synthetic_csv)

    results: dict = {
        "reference_rows": len(ref),
        "synthetic_rows": len(syn),
        "ks_continuous": [],
        "chi_square_categorical": [],
    }

    continuous = [
        "gross_monthly_income_lkr",
        "monthly_expenses_lkr",
        "monthly_debt_service_lkr",
        "liquid_savings_lkr",
        "existing_investments_lkr",
        "total_debt_lkr",
        "baseline_tax_liability_lkr",
        "effective_tax_rate",
        "gross_annual_taxable_income_lkr",
    ]
    for col in continuous:
        if col not in ref.columns or col not in syn.columns:
            continue
        results["ks_continuous"].append(
            ks_report(ref[col].to_numpy(), syn[col].to_numpy(), col)
        )

    # Prefer generalized fields if present (province over district, age_band over age_years).
    cat_specs: list[tuple[str, list[str]]] = [
        ("gender", ["gender"]),
        ("province", ["province", "district"]),
        ("marital_status", ["marital_status"]),
        ("occupation", ["occupation"]),
        ("archetype", ["archetype"]),
        ("age_band", ["age_band"]),
    ]
    for label, candidates in cat_specs:
        c_ref = _col_present(ref, candidates)
        c_syn = _col_present(syn, candidates)
        if not c_ref or not c_syn:
            continue
        results["chi_square_categorical"].append(
            chi_square_report(ref[c_ref], syn[c_syn], label)
        )

    results["income_structure"] = js_signature_report(ref["income_sources_json"], syn["income_sources_json"])

    if args.tsne:
        results["tsne"] = tsne_separation_summary(ref, syn, seed=args.seed)

    text = json.dumps(results, indent=2)
    print(text)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(text, encoding="utf-8")

    ks_ok = all(r["p_value"] > 0.01 for r in results["ks_continuous"] if r.get("p_value") is not None)
    chi_ok = all(
        (r.get("p_value") or 1.0) > 0.01
        for r in results["chi_square_categorical"]
        if r.get("p_value") is not None
    )
    js = results["income_structure"]["js_divergence_h"]
    js_ok = js < 0.12
    print("\n--- heuristic gates (dissertation-facing; tune thresholds) ---")
    print(f"KS p>0.01 for all tested margins: {ks_ok}")
    print(f"Chi-square p>0.01 where defined: {chi_ok}")
    print(f"JS(H) income signatures < 0.12: {js_ok} (got {js:.4f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
