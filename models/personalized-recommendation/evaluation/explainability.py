"""SHAP-based explanations for pair-wise LambdaMART scores (Phase 6 / FR10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    import shap
except ImportError:  # pragma: no cover
    shap = None  # type: ignore[assignment]


@dataclass(frozen=True)
class FeatureAttribution:
    feature: str
    shap_value: float
    direction: str


@dataclass(frozen=True)
class PairExplanation:
    top_reasons: list[FeatureAttribution]
    bottom_reasons: list[FeatureAttribution]
    narrative: str | None = None

    def as_api_dict(self) -> dict[str, Any]:
        return {
            "top_reasons": [
                {"feature": r.feature, "shap_value": r.shap_value, "direction": r.direction}
                for r in self.top_reasons
            ],
            "bottom_reasons": [
                {"feature": r.feature, "shap_value": r.shap_value, "direction": r.direction}
                for r in self.bottom_reasons
            ],
            "narrative": self.narrative,
        }


def _transform_pair_features(pipeline: Any, pair_df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    prep = pipeline.named_steps["prep"]
    names = [str(x) for x in prep.get_feature_names_out()]
    X = prep.transform(pair_df)
    if hasattr(X, "toarray"):
        X = X.toarray()
    return np.asarray(X, dtype=np.float64), names


def _tree_estimator(pipeline: Any) -> Any:
    """Resolve the fitted tree model step (training uses ``('rank', ...)``)."""
    steps = pipeline.named_steps
    for key in ("rank", "model", "ranker"):
        if key in steps:
            return steps[key]
    for name, est in steps.items():
        if name != "prep":
            return est
    raise KeyError(f"No tree estimator step found in pipeline: {list(steps)}")


def explain_pair_ranking(
    ranker_pipeline: Any,
    pair_df: pd.DataFrame,
    *,
    strategy_row_index: int = 0,
    top_k: int = 5,
) -> PairExplanation:
    """Explain one user×strategy row from a fitted sklearn Pipeline (prep + LGBMRanker)."""
    if shap is None:
        raise RuntimeError("shap is not installed; pip install shap")

    model = _tree_estimator(ranker_pipeline)
    X, names = _transform_pair_features(ranker_pipeline, pair_df)
    row = X[strategy_row_index : strategy_row_index + 1]
    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(row)
    if isinstance(values, list):
        values = values[0]
    shap_row = np.asarray(values).reshape(-1)

    order = np.argsort(-np.abs(shap_row))
    top_idx = order[:top_k]
    bottom_idx = order[-top_k:][::-1]

    def _attr(i: int) -> FeatureAttribution:
        v = float(shap_row[i])
        return FeatureAttribution(
            feature=names[i] if i < len(names) else f"feature_{i}",
            shap_value=round(v, 6),
            direction="positive" if v >= 0 else "negative",
        )

    top = [_attr(int(i)) for i in top_idx]
    bottom = [_attr(int(i)) for i in bottom_idx]
    narrative = (
        f"Top drivers for this strategy's ranking score: "
        f"{', '.join(r.feature for r in top[:3])}."
    )
    return PairExplanation(top_reasons=top, bottom_reasons=bottom, narrative=narrative)


__all__ = [
    "FeatureAttribution",
    "PairExplanation",
    "explain_pair_ranking",
]
