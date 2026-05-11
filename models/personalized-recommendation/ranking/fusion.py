"""Multi-objective score fusion (Phase 4 / WP6 — Objectives 2.2.1/2.2.2/2.2.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class FusionWeights:
    w_savings: float
    w_adoption: float
    w_feasibility: float
    w_risk_penalty: float

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FusionWeights":
        return cls(
            w_savings=float(raw.get("w_savings", 0.40)),
            w_adoption=float(raw.get("w_adoption", 0.30)),
            w_feasibility=float(raw.get("w_feasibility", 0.20)),
            w_risk_penalty=float(raw.get("w_risk_penalty", 0.10)),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "FusionWeights":
        data = yaml.safe_load(open(path, encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Fusion weights YAML must be a mapping")
        return cls.from_dict(data)


def fuse_scores(
    *,
    tax_savings_norm: float,
    adoption_prob: float,
    feasibility: float,
    risk_penalty: float,
    weights: FusionWeights,
) -> float:
    """Weighted linear fusion (same shape as component FastAPI settings)."""
    return (
        weights.w_savings * tax_savings_norm
        + weights.w_adoption * adoption_prob
        + weights.w_feasibility * feasibility
        - weights.w_risk_penalty * risk_penalty
    )


def min_max_norm(values: list[float]) -> list[float]:
    """Normalize to [0, 1]; constant vectors become all 0.5."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]
