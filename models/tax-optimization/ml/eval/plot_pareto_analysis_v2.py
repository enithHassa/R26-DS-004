"""Research visualisation for the v2 multi-objective Pareto utility model.

Produces three figures for the dissertation / paper:

Figure 1 — Pareto Frontier
    Tax savings (LKR) vs. Liquidity cost (LKR) for all passing strategy candidates
    across a sample of taxpayers. Highlights the Pareto-efficient frontier and marks
    which strategy ML (v2) ranked #1 vs. which strategy rule-based sort ranked #1.

Figure 2 — Disagreement Analysis
    For each taxpayer where ML top-1 ≠ rule-based top-1, plot the difference in
    savings and liquidity cost. Clustered by income bracket to show that ML prefers
    lower-cost strategies for lower-income taxpayers.

Figure 3 — Alpha Sensitivity
    Table showing how the fraction of taxpayers where ML top-1 ≠ rule-based top-1
    changes as alpha varies from 0.5 to 1.0.

Usage
-----
    python models/tax-optimization/ml/eval/plot_pareto_analysis_v2.py \\
        --parquet models/tax-optimization/datasets/ml/training_v2.parquet \\
        --out-dir models/tax-optimization/artifacts/figures

Requires: matplotlib, pandas, numpy, scikit-learn (already in ML env).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── path setup ─────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_SRC = _REPO_ROOT / "backend" / "comp-tax-optimization"
if _BACKEND_SRC.is_dir():
    sys.path.insert(0, str(_BACKEND_SRC))

try:
    from models.tax_optimization.ml.train.train_tax_opt_models_v1 import (  # type: ignore[import]
        compute_utility_score,
    )
except ImportError:
    # Fallback inline definition matching the training script
    def compute_utility_score(savings_lkr, liquidity_cost_lkr, gross_income, alpha=0.7):
        if gross_income <= 0.0:
            return 0.0
        return alpha * (savings_lkr / gross_income) - (1.0 - alpha) * (liquidity_cost_lkr / gross_income)


DEFAULT_PARQUET = _REPO_ROOT / "models" / "tax-optimization" / "datasets" / "ml" / "training_v2.parquet"
DEFAULT_OUT_DIR = _REPO_ROOT / "models" / "tax-optimization" / "artifacts" / "figures"
ALPHA_DEFAULT = 0.7
INCOME_BRACKETS = [
    (0, 1_500_000, "Low (<1.5M)"),
    (1_500_000, 3_000_000, "Mid (1.5–3M)"),
    (3_000_000, float("inf"), "High (>3M)"),
]


def _income_bracket(gross: float) -> str:
    for lo, hi, label in INCOME_BRACKETS:
        if lo <= gross < hi:
            return label
    return "High (>3M)"


def _pareto_front(savings: np.ndarray, liquidity: np.ndarray) -> np.ndarray:
    """Return boolean mask of Pareto-efficient points (maximise savings, minimise liquidity)."""
    n = len(savings)
    is_pareto = np.ones(n, dtype=bool)
    for i in range(n):
        if not is_pareto[i]:
            continue
        dominated = (savings >= savings[i]) & (liquidity <= liquidity[i]) & (
            (savings > savings[i]) | (liquidity < liquidity[i])
        )
        dominated[i] = False
        is_pareto[is_pareto] = ~dominated[is_pareto]
    return is_pareto


def build_taxpayer_comparison(df: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """For each taxpayer compute: rule top-1 candidate and ML top-1 candidate."""
    records = []
    for tid, gdf in df.groupby("taxpayer_id"):
        if len(gdf) == 0:
            continue
        gross = gdf["annual_gross_income"].iloc[0]
        # Rule top-1: lowest total_tax (then lowest mask for tie-break)
        rule_top = gdf.sort_values(["total_tax_lkr", "candidate_mask"]).iloc[0]
        # ML top-1: highest utility_score
        gdf = gdf.copy()
        gdf["_util"] = gdf.apply(
            lambda r: compute_utility_score(r["savings_vs_baseline_lkr"], r["liquidity_cost_lkr"], gross, alpha),
            axis=1,
        )
        ml_top = gdf.sort_values("_util", ascending=False).iloc[0]
        records.append(
            {
                "taxpayer_id": tid,
                "gross_income": gross,
                "income_bracket": _income_bracket(gross),
                "rule_top_savings": rule_top["savings_vs_baseline_lkr"],
                "rule_top_liquidity": rule_top["liquidity_cost_lkr"],
                "rule_top_mask": rule_top["candidate_mask"],
                "ml_top_savings": ml_top["savings_vs_baseline_lkr"],
                "ml_top_liquidity": ml_top["liquidity_cost_lkr"],
                "ml_top_mask": ml_top["candidate_mask"],
                "disagree": rule_top["candidate_mask"] != ml_top["candidate_mask"],
                "ml_saves_liquidity": ml_top["liquidity_cost_lkr"] - rule_top["liquidity_cost_lkr"],
                "ml_loses_savings": rule_top["savings_vs_baseline_lkr"] - ml_top["savings_vs_baseline_lkr"],
            }
        )
    return pd.DataFrame(records)


def plot_pareto_frontier(df: pd.DataFrame, cmp: pd.DataFrame, out_dir: Path, alpha: float) -> None:
    sample_tids = df["taxpayer_id"].unique()[:100]  # 100 taxpayers for clarity
    sub = df[df["taxpayer_id"].isin(sample_tids)]

    fig, ax = plt.subplots(figsize=(10, 7))

    # All candidates (grey)
    ax.scatter(
        sub["liquidity_cost_lkr"] / 1000,
        sub["savings_vs_baseline_lkr"] / 1000,
        alpha=0.15, s=8, color="lightgrey", label="All candidates",
    )

    # Pareto-efficient points
    savings_arr = sub["savings_vs_baseline_lkr"].to_numpy()
    liq_arr = sub["liquidity_cost_lkr"].to_numpy()
    pareto_mask = _pareto_front(savings_arr, liq_arr)
    pareto_sub = sub[pareto_mask].sort_values("liquidity_cost_lkr")
    ax.scatter(
        pareto_sub["liquidity_cost_lkr"] / 1000,
        pareto_sub["savings_vs_baseline_lkr"] / 1000,
        alpha=0.7, s=20, color="steelblue", zorder=3, label="Pareto frontier",
    )
    ax.plot(
        pareto_sub["liquidity_cost_lkr"] / 1000,
        pareto_sub["savings_vs_baseline_lkr"] / 1000,
        color="steelblue", alpha=0.4, linewidth=1,
    )

    # Rule top-1 per taxpayer
    rule_tops = cmp[cmp["taxpayer_id"].isin(sample_tids)]
    ax.scatter(
        rule_tops["rule_top_liquidity"] / 1000,
        rule_tops["rule_top_savings"] / 1000,
        marker="^", s=60, color="orangered", zorder=4, label="Rule-based top-1",
    )

    # ML top-1 per taxpayer
    ax.scatter(
        rule_tops["ml_top_liquidity"] / 1000,
        rule_tops["ml_top_savings"] / 1000,
        marker="*", s=80, color="green", zorder=5, label=f"ML top-1 (α={alpha})",
    )

    ax.set_xlabel("Liquidity Cost (LKR thousands)", fontsize=12)
    ax.set_ylabel("Tax Savings vs. Baseline (LKR thousands)", fontsize=12)
    ax.set_title(f"Pareto Frontier: Tax Savings vs. Liquidity Cost\n(100 taxpayer sample, α={alpha})", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    path = out_dir / "fig1_pareto_frontier.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_disagreement_analysis(cmp: pd.DataFrame, out_dir: Path, alpha: float) -> None:
    disagree = cmp[cmp["disagree"]].copy()
    if len(disagree) == 0:
        print("No disagreements found — all taxpayers have same ML and rule top-1.")
        return

    bracket_colors = {"Low (<1.5M)": "#e74c3c", "Mid (1.5–3M)": "#f39c12", "High (>3M)": "#2ecc71"}
    fig, ax = plt.subplots(figsize=(10, 7))
    for bracket, color in bracket_colors.items():
        sub = disagree[disagree["income_bracket"] == bracket]
        if len(sub) == 0:
            continue
        ax.scatter(
            sub["ml_saves_liquidity"] / 1000,   # negative = ML chose LESS liquidity cost
            sub["ml_loses_savings"] / 1000,     # positive = ML chose LESS savings
            alpha=0.6, s=40, color=color, label=f"{bracket} (n={len(sub)})",
        )

    ax.axvline(0, color="grey", linestyle="--", linewidth=0.8)
    ax.axhline(0, color="grey", linestyle="--", linewidth=0.8)
    ax.set_xlabel("ML liquidity cost change vs. rule top-1 (LKR thousands, −=less cash needed)", fontsize=11)
    ax.set_ylabel("ML savings reduction vs. rule top-1 (LKR thousands, +=lower savings)", fontsize=11)
    ax.set_title(f"Disagreement Analysis: When ML top-1 ≠ Rule top-1 (α={alpha})\n"
                 f"Bottom-left quadrant = ML chose less-costly strategy with similar savings", fontsize=12)
    ax.legend(title="Income bracket", fontsize=10)
    ax.grid(True, alpha=0.3)

    pct = 100 * len(disagree) / len(cmp)
    ax.text(
        0.02, 0.97,
        f"{len(disagree)}/{len(cmp)} taxpayers disagree ({pct:.1f}%)",
        transform=ax.transAxes, fontsize=10, va="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    path = out_dir / "fig2_disagreement_analysis.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_alpha_sensitivity(df: pd.DataFrame, out_dir: Path) -> None:
    alphas = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    disagree_pcts = []
    avg_liq_reductions = []

    for a in alphas:
        cmp = build_taxpayer_comparison(df, alpha=a)
        disagree = cmp[cmp["disagree"]]
        disagree_pcts.append(100 * len(disagree) / max(len(cmp), 1))
        if len(disagree) > 0:
            avg_liq_reductions.append(-disagree["ml_saves_liquidity"].mean() / 1000)
        else:
            avg_liq_reductions.append(0.0)

    fig, ax1 = plt.subplots(figsize=(9, 5))
    color1, color2 = "steelblue", "orangered"
    ax2 = ax1.twinx()

    ax1.plot(alphas, disagree_pcts, "o-", color=color1, linewidth=2, markersize=7, label="% taxpayers where ML≠rule")
    ax1.set_xlabel("Alpha (savings weight)", fontsize=12)
    ax1.set_ylabel("Taxpayers with different top-1 (%)", color=color1, fontsize=11)
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2.plot(alphas, avg_liq_reductions, "s--", color=color2, linewidth=2, markersize=7,
             label="Avg liquidity reduction (LKR k)")
    ax2.set_ylabel("Avg. liquidity cost reduction (LKR thousands)", color=color2, fontsize=11)
    ax2.tick_params(axis="y", labelcolor=color2)

    ax1.set_title("Alpha Sensitivity: How α changes ML vs. Rule disagreement rate", fontsize=13)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc="upper left")
    ax1.grid(True, alpha=0.3)

    path = out_dir / "fig3_alpha_sensitivity.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")

    # Print table for paper
    print("\nAlpha Sensitivity Table:")
    print(f"{'Alpha':>6}  {'Disagree%':>10}  {'Avg LIQ reduction (LKR k)':>26}")
    for a, dp, lr in zip(alphas, disagree_pcts, avg_liq_reductions):
        print(f"{a:>6.1f}  {dp:>10.1f}  {lr:>26.1f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--alpha", type=float, default=ALPHA_DEFAULT)
    ap.add_argument("--max-taxpayers", type=int, default=None,
                    help="Subsample for faster plotting (default: all)")
    ap.add_argument("--skip-sensitivity", action="store_true",
                    help="Skip alpha sensitivity figure (slow on large datasets)")
    args = ap.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.parquet}...")
    df = pd.read_parquet(args.parquet)

    if args.max_taxpayers is not None:
        tids = df["taxpayer_id"].unique()
        rng = np.random.default_rng(42)
        pick = rng.choice(tids, size=min(args.max_taxpayers, len(tids)), replace=False)
        df = df[df["taxpayer_id"].isin(pick)].reset_index(drop=True)

    print(f"  {len(df)} rows, {df['taxpayer_id'].nunique()} taxpayers")

    print("Building taxpayer comparison table...")
    cmp = build_taxpayer_comparison(df, alpha=args.alpha)

    print("Plotting Figure 1: Pareto Frontier...")
    plot_pareto_frontier(df, cmp, args.out_dir, args.alpha)

    print("Plotting Figure 2: Disagreement Analysis...")
    plot_disagreement_analysis(cmp, args.out_dir, args.alpha)

    if not args.skip_sensitivity:
        print("Plotting Figure 3: Alpha Sensitivity (this may take a minute)...")
        plot_alpha_sensitivity(df, args.out_dir)

    print(f"\nAll figures saved to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
