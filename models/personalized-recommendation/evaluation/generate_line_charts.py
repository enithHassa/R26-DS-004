#!/usr/bin/env python3
"""IEEE one-column LINE figures for Component 3 Results (Personalized Recommendation).

Companion to ``generate_paper_figures.py`` (which draws the bar/schematic
figures). This script draws the three line charts commonly needed in a
Results and Validation chapter:

  Fig. 4 — Monte Carlo convergence (summary stats vs. number of simulated paths)
  Fig. 5 — Monte Carlo percentile fan chart (P10/P50/P90 net worth or tax
           liability per year, baseline vs. strategy)
  Fig. 6 — Ranking / adoption-model learning curve (train vs. validation
           metric per boosting round or epoch)

Every chart reads from a real JSON file you produce yourself (see the
``--help`` for each input's expected shape, and the worked examples below).
Nothing here fabricates data — if an input file is missing, that figure is
skipped and the script tells you so, rather than drawing a placeholder.

Example — run all three once you have the input files ready::

  MPLCONFIGDIR=/tmp/matplotlib \\
    .venv-ml/bin/python models/personalized-recommendation/evaluation/generate_line_charts.py \\
    --convergence-json reports/mc_convergence.json \\
    --fanchart-json reports/mc_fanchart.json \\
    --learning-curve-json reports/ranking_learning_curve.json

Each input is optional — pass only the ones you have; the others are skipped.

--- Expected input shapes ---

--convergence-json (Monte Carlo convergence, Fig. 4):
  Run ``run_monte_carlo`` (models/personalized-recommendation/impact/monte_carlo.py)
  at a few increasing ``n_paths`` values for the SAME profile/strategy/seed,
  and record ``result.summary`` at each one, e.g.:

  {
    "n_paths": [100, 500, 1000, 5000, 10000],
    "expected_total_savings": [.., .., .., .., ..],
    "expected_net_worth":     [.., .., .., .., ..],
    "probability_of_net_gain":[.., .., .., .., ..]
  }

--fanchart-json (Monte Carlo percentile fan chart, Fig. 5):
  Call ``projection_bands(paths, field="net_worth")`` (same module) for both
  ``baseline_paths`` and ``strategy_paths`` from one ``run_monte_carlo`` call,
  e.g.:

  {
    "field": "net_worth",
    "baseline": [{"year": 1, "p10": .., "p50": .., "p90": ..}, ...],
    "strategy": [{"year": 1, "p10": .., "p50": .., "p90": ..}, ...]
  }

--learning-curve-json (ranking/adoption learning curve, Fig. 6):
  LightGBM's ``evals_result_`` (or your own logged per-round/epoch metric),
  e.g.:

  {
    "metric_name": "ndcg@10",
    "iteration": [0, 1, 2, ..., 199],
    "train": [.., .., .., ...],
    "valid": [.., .., .., ...]
  }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

_HERE = Path(__file__).resolve().parent
_DEFAULT_OUT = _HERE / "figures"
_COL_W = 3.4
_DPI = 300


def _apply_ieee_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "figure.dpi": _DPI,
            "savefig.dpi": _DPI,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
        }
    )


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def _style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)


def plot_mc_convergence(data_json: Path, out_path: Path) -> bool:
    """Fig. 4 — summary statistics vs. number of simulated Monte Carlo paths."""
    if not data_json.is_file():
        return False
    data = json.loads(data_json.read_text(encoding="utf-8"))
    n_paths = data["n_paths"]

    series = [
        ("expected_total_savings", "Expected total savings", "#4C72B0"),
        ("expected_net_worth", "Expected net worth", "#55A868"),
        ("probability_of_net_gain", "P(net gain)", "#C44E52"),
    ]
    series = [(k, label, color) for k, label, color in series if k in data]
    if not series:
        return False

    fig, ax1 = plt.subplots(figsize=(_COL_W, 2.5))
    ax2 = ax1.twinx()
    lines = []
    for key, label, color in series:
        target_ax = ax2 if key == "probability_of_net_gain" else ax1
        (line,) = target_ax.plot(
            n_paths, data[key], marker="o", markersize=3, linewidth=1.2, color=color, label=label
        )
        lines.append(line)

    ax1.set_xlabel("Number of simulated paths")
    ax1.set_ylabel("Value (currency units)")
    ax2.set_ylabel("Probability")
    ax1.set_xscale("log")
    _style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    ax1.legend(lines, [line.get_label() for line in lines], loc="best", frameon=False)
    fig.tight_layout()
    _save(fig, out_path)
    return True


def plot_mc_fanchart(data_json: Path, out_path: Path) -> bool:
    """Fig. 5 — P10/P50/P90 fan chart per year, baseline vs. strategy."""
    if not data_json.is_file():
        return False
    data = json.loads(data_json.read_text(encoding="utf-8"))
    field = data.get("field", "net_worth")
    baseline = data.get("baseline") or []
    strategy = data.get("strategy") or []
    if not baseline:
        return False

    fig, ax = plt.subplots(figsize=(_COL_W, 2.6))

    def _draw(rows: list[dict], color: str, label_prefix: str) -> None:
        years = [r["year"] for r in rows]
        p10 = [r["p10"] for r in rows]
        p50 = [r["p50"] for r in rows]
        p90 = [r["p90"] for r in rows]
        ax.fill_between(years, p10, p90, color=color, alpha=0.18, linewidth=0)
        ax.plot(years, p50, color=color, linewidth=1.4, label=f"{label_prefix} P50")
        ax.plot(years, p10, color=color, linewidth=0.7, linestyle="--", alpha=0.7)
        ax.plot(years, p90, color=color, linewidth=0.7, linestyle="--", alpha=0.7)

    _draw(baseline, "#4C72B0", "Baseline")
    if strategy:
        _draw(strategy, "#C44E52", "Strategy")

    ax.set_xlabel("Year")
    label = "Net worth" if field == "net_worth" else "Tax liability"
    ax.set_ylabel(f"{label} (currency units)")
    _style_axes(ax)
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    _save(fig, out_path)
    return True


def plot_learning_curve(data_json: Path, out_path: Path) -> bool:
    """Fig. 6 — train vs. validation metric per boosting round / epoch."""
    if not data_json.is_file():
        return False
    data = json.loads(data_json.read_text(encoding="utf-8"))
    iteration = data["iteration"]
    metric_name = data.get("metric_name", "metric")

    fig, ax = plt.subplots(figsize=(_COL_W, 2.5))
    if "train" in data:
        ax.plot(iteration, data["train"], color="#4C72B0", linewidth=1.3, label="Train")
    if "valid" in data:
        ax.plot(iteration, data["valid"], color="#DD8452", linewidth=1.3, label="Validation")

    ax.set_xlabel("Boosting round / epoch")
    ax.set_ylabel(metric_name)
    _style_axes(ax)
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    _save(fig, out_path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--convergence-json", type=Path, default=None)
    parser.add_argument("--fanchart-json", type=Path, default=None)
    parser.add_argument("--learning-curve-json", type=Path, default=None)
    args = parser.parse_args()

    _apply_ieee_style()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    wrote_any = False

    if args.convergence_json:
        f4 = out / "fig4_mc_convergence.png"
        if plot_mc_convergence(args.convergence_json, f4):
            print("Wrote:", f4, "/", f4.with_suffix(".pdf"))
            wrote_any = True
        else:
            print(f"Skipped Fig. 4 — {args.convergence_json} missing or unusable")

    if args.fanchart_json:
        f5 = out / "fig5_mc_fanchart.png"
        if plot_mc_fanchart(args.fanchart_json, f5):
            print("Wrote:", f5, "/", f5.with_suffix(".pdf"))
            wrote_any = True
        else:
            print(f"Skipped Fig. 5 — {args.fanchart_json} missing or unusable")

    if args.learning_curve_json:
        f6 = out / "fig6_learning_curve.png"
        if plot_learning_curve(args.learning_curve_json, f6):
            print("Wrote:", f6, "/", f6.with_suffix(".pdf"))
            wrote_any = True
        else:
            print(f"Skipped Fig. 6 — {args.learning_curve_json} missing or unusable")

    if not wrote_any:
        print("No input JSON files given/found — pass --convergence-json / --fanchart-json / --learning-curve-json")


if __name__ == "__main__":
    main()
