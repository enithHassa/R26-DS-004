#!/usr/bin/env python3
"""Generate IEEE-ready figures for Component 1 Results (one-column width).

Fig. 1 — grouped bars: macro-F1 vs weighted-F1 (shared test split)
Fig. 2 — DistilBERT confusion matrix (test set)

Example::

  MPLCONFIGDIR=/tmp/matplotlib \\
  .venv-ml/bin/python models/transaction-semantic/evaluation/generate_paper_figures.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_DEFAULT_COMPARE = _HERE / "model_runs_compare.csv"
_DEFAULT_CM = (
    _REPO
    / "models/transaction-semantic/artifacts/distilbert_multilingual/v0.1.0/export"
    / "confusion_matrix_test.csv"
)
_DEFAULT_OUT = _HERE / "figures"

# Display names for paper (stable order)
_MODEL_ORDER = (
    "tfidf_logreg",
    "xlm_roberta_hf",
    "distilbert_multilingual_hf",
)
_MODEL_LABELS = {
    "tfidf_logreg": "TF-IDF + LR",
    "xlm_roberta_hf": "XLM-RoBERTa",
    "distilbert_multilingual_hf": "DistilBERT",
}
_CLASS_SHORT = {
    "business_profit": "Bus. profit",
    "inter_account_transfer": "Transfer",
    "interest_income": "Interest",
    "unknown": "Unknown",
}

# Single IEEE column ≈ 3.5 in; keep figures compact for half-page layout
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
            "axes.grid": False,
        }
    )


def _latest_rows(compare_csv: Path) -> pd.DataFrame:
    """Keep the latest run per model_id (master CSV may append retrains)."""
    df = pd.read_csv(compare_csv)
    df = df[df["model_id"].isin(_MODEL_ORDER)].copy()
    if "run_timestamp_utc" in df.columns:
        df["run_timestamp_utc"] = pd.to_datetime(df["run_timestamp_utc"], utc=True)
        df = df.sort_values("run_timestamp_utc").groupby("model_id", as_index=False).tail(1)
    order = {m: i for i, m in enumerate(_MODEL_ORDER)}
    df["_ord"] = df["model_id"].map(order)
    return df.sort_values("_ord").drop(columns=["_ord"])


def plot_f1_comparison(compare_csv: Path, out_path: Path) -> None:
    df = _latest_rows(compare_csv)
    labels = [_MODEL_LABELS[m] for m in df["model_id"]]
    macro = df["macro_f1_test"].astype(float).to_numpy()
    weighted = df["weighted_f1_test"].astype(float).to_numpy()

    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(_COL_W, 2.35))
    bars_m = ax.bar(x - width / 2, macro, width, label="Macro-F1", color="#4C72B0")
    bars_w = ax.bar(x + width / 2, weighted, width, label="Weighted-F1", color="#DD8452")

    ax.set_ylabel("F1 score")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0.0, 1.05)
    ax.legend(loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    for bars in (bars_m, bars_w):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=6,
            )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def plot_confusion_matrix(cm_csv: Path, out_path: Path, *, drop_empty: bool = True) -> None:
    raw = pd.read_csv(cm_csv, index_col=0)
    cm = raw.to_numpy(dtype=float)
    classes = list(raw.index.astype(str))

    if drop_empty:
        row_keep = cm.sum(axis=1) > 0
        # Also drop columns that only exist for empty true classes if unused
        col_keep = cm.sum(axis=0) > 0
        keep = row_keep | col_keep
        # Prefer: keep any class that appears as true or predicted
        keep = (cm.sum(axis=1) > 0) | (cm.sum(axis=0) > 0)
        cm = cm[np.ix_(keep, keep)]
        classes = [c for c, k in zip(classes, keep) if k]

    short = [_CLASS_SHORT.get(c, c) for c in classes]

    fig, ax = plt.subplots(figsize=(_COL_W, 2.7))
    im = ax.imshow(cm, cmap="Blues", aspect="equal")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=6)

    ax.set_xticks(np.arange(len(short)))
    ax.set_yticks(np.arange(len(short)))
    ax.set_xticklabels(short, rotation=30, ha="right")
    ax.set_yticklabels(short)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")

    thresh = cm.max() / 2.0 if cm.size else 0.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val = int(cm[i, j])
            ax.text(
                j,
                i,
                str(val),
                ha="center",
                va="center",
                color="white" if cm[i, j] > thresh else "black",
                fontsize=7,
            )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-csv", type=Path, default=_DEFAULT_COMPARE)
    parser.add_argument("--confusion-csv", type=Path, default=_DEFAULT_CM)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    _apply_ieee_style()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    fig1 = out_dir / "fig1_model_f1_comparison.png"
    fig2 = out_dir / "fig2_distilbert_confusion_matrix.png"

    plot_f1_comparison(args.compare_csv, fig1)
    plot_confusion_matrix(args.confusion_csv, fig2)

    print("Wrote:")
    print(" ", fig1)
    print(" ", fig1.with_suffix(".pdf"))
    print(" ", fig2)
    print(" ", fig2.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
