#!/usr/bin/env python3
"""IEEE compact hybrid methodology flowchart for Component 1.

Parser → lexicon rules + DistilBERT → fusion/confidence → IRA rules,
with a low-confidence review loop.

Example::

  MPLCONFIGDIR=/tmp/matplotlib \\
    .venv-ml/bin/python models/transaction-semantic/evaluation/generate_methodology_figure.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

_HERE = Path(__file__).resolve().parent
_DEFAULT_OUT = _HERE / "figures"
_DPI = 300
# Two-column IEEE figure* width; keep height small
_FIG_W = 7.16
_FIG_H = 2.55


def _apply_ieee_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 7.5,
            "figure.dpi": _DPI,
            "savefig.dpi": _DPI,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
        }
    )


def _box(ax, x, y, w, h, face: str, edge: str = "#2F3E46") -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            linewidth=0.85,
            facecolor=face,
            edgecolor=edge,
        )
    )


def _label(ax, x, y, w, h, title: str, sub: str | None = None) -> None:
    if sub:
        ax.text(
            x + w / 2,
            y + h * 0.64,
            title,
            ha="center",
            va="center",
            fontsize=7.4,
            fontweight="bold",
            color="#1B2630",
        )
        ax.text(
            x + w / 2,
            y + h * 0.28,
            sub,
            ha="center",
            va="center",
            fontsize=6.3,
            color="#3D4F5F",
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=7.4,
            fontweight="bold",
            color="#1B2630",
        )


def _arrow(ax, p0, p1, *, color="#2F3E46", style="-|>", rad: float = 0.0, lw: float = 1.0) -> None:
    conn = f"arc3,rad={rad}" if rad else "arc3,rad=0"
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle=style,
            mutation_scale=8,
            linewidth=lw,
            color=color,
            connectionstyle=conn,
            shrinkA=0.5,
            shrinkB=0.5,
        )
    )


def plot_methodology(out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
    ax.set_xlim(0, 7.16)
    ax.set_ylim(0, 2.55)
    ax.axis("off")

    h = 0.58
    y_mid = 1.42
    y_lex = 1.88
    y_clf = 0.96
    y_rev = 0.18

    # Boxes: (x, y, w, title, sub, face)
    boxes = {
        "A": (0.08, y_mid, 0.92, "Raw bank line", "statement narrative", "#F4F6F8"),
        "B": (1.18, y_mid, 1.05, "SL narration parser", "normalize + bank cues", "#F4F6F8"),
        "C": (2.48, y_lex, 1.18, "Lexicon + patterns", "heuristic rules", "#E8D5C4"),
        "D": (2.48, y_clf, 1.18, "DistilBERT", "multilingual classifier", "#D6E4F0"),
        "E": (3.92, y_mid, 1.18, "Fusion / routing", "confidence + guards", "#EEE0C9"),
        "F": (5.28, y_mid, 0.88, "IRD taxonomy", "20-class label", "#D6E4F0"),
        "G": (6.32, y_mid, 0.76, "IRA 2017 rules", "symbolic", "#E8D5C4"),
        "H": (6.32, y_rev, 0.76, "Taxable LKR", "amount + rationale", "#D9E8D3"),
        "I": (3.92, y_rev, 1.18, "Review queue", "low confidence", "#F7E1E1"),
        "J": (2.48, y_rev, 1.18, "Human correction", "retrain loop", "#F7E1E1"),
    }

    for key, (x, y, w, title, sub, face) in boxes.items():
        _box(ax, x, y, w, h, face)
        _label(ax, x, y, w, h, title, sub)

    def r(key: str) -> tuple[float, float, float, float]:
        x, y, w, _, _, _ = boxes[key]
        return x, y, w, h

    def right(key: str) -> tuple[float, float]:
        x, y, w, hh = r(key)
        return x + w, y + hh / 2

    def left(key: str) -> tuple[float, float]:
        x, y, w, hh = r(key)
        return x, y + hh / 2

    def top(key: str) -> tuple[float, float]:
        x, y, w, hh = r(key)
        return x + w / 2, y + hh

    def bottom(key: str) -> tuple[float, float]:
        x, y, w, hh = r(key)
        return x + w / 2, y

    # Main path
    _arrow(ax, right("A"), left("B"))
    _arrow(ax, (right("B")[0], right("B")[1] + 0.12), left("C"), rad=-0.12)
    _arrow(ax, (right("B")[0], right("B")[1] - 0.12), left("D"), rad=0.12)
    _arrow(ax, right("C"), (left("E")[0], left("E")[1] + 0.14), rad=0.12)
    _arrow(ax, right("D"), (left("E")[0], left("E")[1] - 0.14), rad=-0.12)
    _arrow(ax, right("E"), left("F"))
    _arrow(ax, right("F"), left("G"))
    _arrow(ax, bottom("G"), top("H"))

    # Review loop
    _arrow(ax, bottom("E"), top("I"), color="#9B3B3B")
    ax.text(
        4.52,
        0.92,
        "low confidence",
        ha="center",
        va="center",
        fontsize=6,
        color="#9B3B3B",
        style="italic",
    )
    _arrow(ax, left("I"), right("J"), color="#9B3B3B")
    _arrow(ax, top("J"), bottom("D"), color="#9B3B3B")
    ax.text(
        2.95,
        0.78,
        "correction",
        ha="left",
        va="center",
        fontsize=6,
        color="#9B3B3B",
        style="italic",
    )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()
    _apply_ieee_style()
    out = args.out_dir / "fig_methodology_pipeline.png"
    plot_methodology(out)
    print("Wrote:")
    print(" ", out)
    print(" ", out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
