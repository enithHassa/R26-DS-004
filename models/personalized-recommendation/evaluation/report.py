"""Evaluation report structures (Phase 6)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelScoreRow:
    """Metrics for one ablation arm or production model."""

    name: str
    metrics: dict[str, float]
    fairness: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Full Phase 6 offline evaluation output."""

    eval_split: str
    n_profiles: int
    n_strategies: int
    models: list[ModelScoreRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_split": self.eval_split,
            "n_profiles": self.n_profiles,
            "n_strategies": self.n_strategies,
            "models": [
                {"name": m.name, "metrics": m.metrics, "fairness": m.fairness}
                for m in self.models
            ],
            "notes": self.notes,
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def leaderboard(self) -> list[ModelScoreRow]:
        """Sort models by ndcg@5 descending."""
        return sorted(
            self.models,
            key=lambda m: m.metrics.get("ndcg@5", 0.0),
            reverse=True,
        )


__all__ = ["EvaluationReport", "ModelScoreRow"]
