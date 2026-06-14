"""Unit tests for evaluation metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parents[2]
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from evaluation.metrics import group_by_query, ranking_metrics  # noqa: E402


def test_perfect_ranking_gets_high_ndcg() -> None:
    y_true = [np.array([0.0, 1.0, 2.0, 3.0])]
    y_score = [np.array([0.1, 0.2, 0.3, 0.9])]
    m = ranking_metrics(y_true, y_score)
    assert m["ndcg@5"] >= 0.99


def test_group_by_query_splits_flat_vector() -> None:
    flat = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    groups = np.array([2, 1, 3])
    parts = group_by_query(flat, groups)
    assert len(parts) == 3
    assert parts[0].tolist() == [1.0, 2.0]
    assert parts[2].tolist() == [4.0, 5.0, 6.0]
