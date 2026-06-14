"""Fairness diagnostics across occupation and income segments (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from evaluation.metrics import group_by_query, ranking_metrics


@dataclass
class SegmentMetrics:
    segment: str
    n_profiles: int
    metrics: dict[str, float]


@dataclass
class FairnessReport:
    """Disparity summary across segments for one scoring system."""

    metric_name: str = "ndcg@5"
    segments: list[SegmentMetrics] = field(default_factory=list)
    best_segment: str = ""
    worst_segment: str = ""
    disparity: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "segments": [
                {"segment": s.segment, "n_profiles": s.n_profiles, "metrics": s.metrics}
                for s in self.segments
            ],
            "best_segment": self.best_segment,
            "worst_segment": self.worst_segment,
            "disparity": self.disparity,
            "min_value": self.min_value,
            "max_value": self.max_value,
        }


def income_decile_labels(incomes: list[float]) -> list[str]:
    """Assign decile bucket labels D1 (lowest) … D10 (highest)."""
    arr = np.asarray(incomes, dtype=np.float64)
    if len(arr) == 0:
        return []
    if len(arr) < 10:
        edges = np.quantile(arr, np.linspace(0, 1, min(len(arr), 5)))
    else:
        edges = np.quantile(arr, np.linspace(0, 1, 11))
    edges = np.unique(edges)
    if len(edges) < 2:
        return ["D1" for _ in arr]
    bins = np.digitize(arr, edges[1:-1], right=True)
    return [f"D{int(b) + 1}" for b in bins]


def fairness_by_segment(
    *,
    y_true_groups: list[np.ndarray],
    y_score_groups: list[np.ndarray],
    segment_labels: list[str],
    metric_key: str = "ndcg@5",
) -> FairnessReport:
    """Compute ranking metrics per segment label and disparity (max − min)."""
    buckets: dict[str, tuple[list[np.ndarray], list[np.ndarray]]] = {}
    for label, y_true, y_score in zip(segment_labels, y_true_groups, y_score_groups):
        buckets.setdefault(label, ([], []))
        buckets[label][0].append(y_true)
        buckets[label][1].append(y_score)

    segments: list[SegmentMetrics] = []
    values: dict[str, float] = {}
    for label, (trues, scores) in sorted(buckets.items()):
        m = ranking_metrics(trues, scores)
        segments.append(SegmentMetrics(segment=label, n_profiles=len(trues), metrics=m))
        values[label] = m.get(metric_key, 0.0)

    if not values:
        return FairnessReport(metric_name=metric_key)

    best = max(values, key=values.get)
    worst = min(values, key=values.get)
    vmin = values[worst]
    vmax = values[best]
    return FairnessReport(
        metric_name=metric_key,
        segments=segments,
        best_segment=best,
        worst_segment=worst,
        disparity=round(vmax - vmin, 6),
        min_value=round(vmin, 6),
        max_value=round(vmax, 6),
    )


def fairness_reports_for_eval(
    flat_scores: np.ndarray,
    group_sizes: np.ndarray,
    y_rank: np.ndarray,
    occupations: list[str],
    incomes: list[float],
) -> dict[str, FairnessReport]:
    """Occupation- and income-decile fairness for one flat score vector."""
    y_groups = group_by_query(y_rank.astype(float), group_sizes)
    score_groups = group_by_query(flat_scores, group_sizes)
    deciles = income_decile_labels(incomes)
    return {
        "occupation": fairness_by_segment(
            y_true_groups=y_groups,
            y_score_groups=score_groups,
            segment_labels=occupations,
        ),
        "income_decile": fairness_by_segment(
            y_true_groups=y_groups,
            y_score_groups=score_groups,
            segment_labels=deciles,
        ),
    }


__all__ = [
    "FairnessReport",
    "SegmentMetrics",
    "fairness_by_segment",
    "fairness_reports_for_eval",
    "income_decile_labels",
]
