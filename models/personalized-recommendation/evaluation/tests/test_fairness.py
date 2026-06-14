"""Unit tests for fairness reporting."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parents[2]
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from evaluation.fairness import fairness_by_segment, income_decile_labels  # noqa: E402


def test_income_decile_labels_cover_all_rows() -> None:
    labels = income_decile_labels([100_000, 200_000, 500_000, 2_000_000, 3_000_000])
    assert len(labels) == 5
    assert all(l.startswith("D") for l in labels)


def test_fairness_disparity_non_negative() -> None:
    y_true = [
        np.array([0.0, 1.0, 2.0]),
        np.array([0.0, 1.0, 2.0]),
    ]
    y_score = [
        np.array([0.1, 0.2, 0.9]),
        np.array([0.9, 0.2, 0.1]),
    ]
    report = fairness_by_segment(
        y_true_groups=y_true,
        y_score_groups=y_score,
        segment_labels=["employee", "business_owner"],
    )
    assert report.disparity >= 0.0
    assert len(report.segments) == 2
