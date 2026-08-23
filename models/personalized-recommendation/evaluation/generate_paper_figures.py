#!/usr/bin/env python3
"""IEEE one-column figures for Component 3 Results (Personalized Recommendation).

Interim figures (no Phase-6 scores required):
  Fig. 1 — Multi-objective fusion weights (from scoring_weights.yaml)
  Fig. 2 — Hybrid pipeline / ablation stages (schematic)

When ``reports/phase6_eval.json`` (or ``--metrics-json``) exists with model rows,
also writes comparison bars (NDCG@5/10, MAP@5, P@5) for the paper table.

Example::

  MPLCONFIGDIR=/tmp/matplotlib \\
    .venv-ml/bin/python models/personalized-recommendation/evaluation/generate_paper_figures.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_DEFAULT_WEIGHTS = (
    _REPO
    / "backend/comp-personalized-recommendation/app/artifacts/scoring_weights.yaml"
)
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


def plot_fusion_weights(weights_yaml: Path, out_path: Path) -> None:
    raw = yaml.safe_load(weights_yaml.read_text(encoding="utf-8"))
    items = [
        ("Savings", float(raw["w_savings"])),
        ("Adoption", float(raw["w_adoption"])),
        ("Feasibility", float(raw["w_feasibility"])),
        ("Risk pen.", float(raw["w_risk_penalty"])),
    ]
    labels = [x[0] for x in items]
    vals = [x[1] for x in items]
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B3"]

    fig, ax = plt.subplots(figsize=(_COL_W, 2.35))
    x = np.arange(len(labels))
    bars = ax.bar(x, vals, color=colors, width=0.65)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Fusion weight")
    ax.set_ylim(0, 0.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for bar, v in zip(bars, vals):
        ax.annotate(
            f"{v:.2f}",
            xy=(bar.get_x() + bar.get_width() / 2, v),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    fig.tight_layout()
    _save(fig, out_path)


def plot_hybrid_ablation_schematic(out_path: Path) -> None:
    """Stage diagram: what each ablation arm adds (not fabricated metric lifts)."""
    stages = [
        "Rules\n(eligibility)",
        "+ Feasibility\nheuristic",
        "+ LambdaMART\nranker",
        "+ Adoption\n+ fusion",
        "+ Monte Carlo\nimpact",
    ]
    # Cumulative “capability index” for visual hierarchy only (not eval scores).
    levels = [1, 2, 3, 4, 5]

    fig, ax = plt.subplots(figsize=(_COL_W, 2.5))
    y = np.arange(len(stages))
    ax.barh(y, levels, color="#4C72B0", height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(stages)
    ax.invert_yaxis()
    ax.set_xlabel("Pipeline stage (ablation order)")
    ax.set_xticks([])
    ax.set_xlim(0, 5.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    for i, lab in enumerate(
        ["A0", "A1", "A2", "A3", "Full"]
    ):
        ax.text(levels[i] + 0.12, i, lab, va="center", fontsize=7)
    fig.tight_layout()
    _save(fig, out_path)


def plot_metrics_comparison(metrics_json: Path, out_path: Path) -> bool:
    """Optional: Phase-6 / model-comparison JSON → grouped bars.

    Expected shape (flexible)::

      {"models": [{"name": "...", "ndcg@5": 0.1, "ndcg@10": 0.1,
                   "map@5": 0.1, "p@5": 0.1, "adoption_f1": 0.1}, ...]}
    """
    if not metrics_json.is_file():
        return False
    data = json.loads(metrics_json.read_text(encoding="utf-8"))
    rows = data.get("models") or data.get("results") or []
    if not rows:
        return False

    names = [str(r.get("name") or r.get("model") or f"m{i}") for i, r in enumerate(rows)]
    metric_keys = [
        ("ndcg@5", "NDCG@5"),
        ("ndcg@10", "NDCG@10"),
        ("map@5", "MAP@5"),
        ("p@5", "P@5"),
    ]
    # Also accept alternate keys from EvaluationReport
    alt = {
        "ndcg@5": ["ndcg_at_5", "ndcg5"],
        "ndcg@10": ["ndcg_at_10", "ndcg10"],
        "map@5": ["map_at_5", "map5"],
        "p@5": ["precision_at_5", "p5", "precision@5"],
    }

    def _get(row: dict, key: str) -> float | None:
        if key in row and row[key] is not None:
            return float(row[key])
        for a in alt.get(key, []):
            if a in row and row[a] is not None:
                return float(row[a])
        metrics = row.get("metrics") or {}
        if key in metrics:
            return float(metrics[key])
        for a in alt.get(key, []):
            if a in metrics:
                return float(metrics[a])
        return None

    fig, ax = plt.subplots(figsize=(_COL_W, 2.5))
    x = np.arange(len(names))
    n_m = len(metric_keys)
    width = 0.8 / n_m
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

    for i, (key, label) in enumerate(metric_keys):
        vals = [_get(r, key) for r in rows]
        if any(v is None for v in vals):
            continue
        offset = (i - (n_m - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=label, color=colors[i % len(colors)])

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, out_path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights-yaml", type=Path, default=_DEFAULT_WEIGHTS)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    parser.add_argument(
        "--metrics-json",
        type=Path,
        default=_REPO / "reports/phase6_eval.json",
        help="Optional Phase-6 JSON for metric comparison bars",
    )
    args = parser.parse_args()

    _apply_ieee_style()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    f1 = out / "fig1_fusion_weights.png"
    f2 = out / "fig2_hybrid_ablation_stages.png"
    f3 = out / "fig3_model_metrics_comparison.png"

    plot_fusion_weights(args.weights_yaml, f1)
    plot_hybrid_ablation_schematic(f2)
    wrote_metrics = plot_metrics_comparison(args.metrics_json, f3)

    print("Wrote:")
    print(" ", f1)
    print(" ", f1.with_suffix(".pdf"))
    print(" ", f2)
    print(" ", f2.with_suffix(".pdf"))
    if wrote_metrics:
        print(" ", f3)
        print(" ", f3.with_suffix(".pdf"))
    else:
        print(" (skipped metric bars — no usable --metrics-json yet)")


if __name__ == "__main__":
    main()
