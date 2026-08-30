"""Ablation arms isolating rules, feasibility, adoption, and ranker (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRanker
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from evaluation.dataset import build_eval_dataset
from evaluation.fairness import fairness_reports_for_eval
from evaluation.metrics import adoption_metrics, group_by_query, ranking_metrics
from evaluation.report import EvaluationReport, ModelScoreRow
from strategy_gen.catalog import StrategyCatalog


def _pair_pipeline(estimator: Any, pair_num: list[str], pair_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), pair_cat)],
        remainder="passthrough",
    )
    return Pipeline([("prep", pre), ("model", estimator)])


def _user_pipeline(estimator: Any, user_num: list[str], user_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), user_cat)],
        remainder="passthrough",
    )
    return Pipeline([("prep", pre), ("model", estimator)])


@dataclass(frozen=True)
class AblationConfig:
    train_limit: int = 8000
    eval_limit: int = 1500
    eval_split: str = "val"
    include_retrained_baselines: bool = True


def _score_row(
    name: str,
    flat_scores: np.ndarray,
    data: dict[str, Any],
    adopt_probs: np.ndarray | None = None,
) -> ModelScoreRow:
    y_groups = group_by_query(data["y_rank"].astype(float), data["group"])
    score_groups = group_by_query(flat_scores, data["group"])
    metrics = ranking_metrics(y_groups, score_groups)
    if adopt_probs is not None:
        metrics.update(adoption_metrics(data["y_adopt"], adopt_probs))
    fairness = fairness_reports_for_eval(
        flat_scores,
        data["group"],
        data["y_rank"],
        data["occupations"],
        data["incomes"],
    )
    return ModelScoreRow(
        name=name,
        metrics=metrics,
        fairness={k: v.to_dict() for k, v in fairness.items()},
    )


def run_ablation_study(
    *,
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    catalog: StrategyCatalog,
    user_num: list[str],
    user_cat: list[str],
    config: AblationConfig | None = None,
    extra_arms: list[tuple[str, Callable[[dict[str, Any]], np.ndarray]]] | None = None,
) -> EvaluationReport:
    """Train/evaluate ablation arms on held-out profiles."""
    config = config or AblationConfig()
    train_data = build_eval_dataset(train_df, catalog, user_num, user_cat)
    eval_data = build_eval_dataset(eval_df, catalog, user_num, user_cat)
    n_s = int(eval_data["n_strategies"])
    report = EvaluationReport(
        eval_split=config.eval_split,
        n_profiles=len(eval_df),
        n_strategies=n_s,
    )

    report.models.append(_score_row("Catalog priority (rules)", eval_data["rule_scores"], eval_data))
    report.models.append(_score_row("Feasibility heuristic", eval_data["feas_scores"], eval_data))

    if extra_arms:
        for name, fn in extra_arms:
            report.models.append(_score_row(name, fn(eval_data), eval_data))

    if not config.include_retrained_baselines:
        return report

    pair_num = eval_data["pair_num"]
    pair_cat = eval_data["pair_cat"]
    x_rank_tr = train_data["x_rank"]
    y_rank_tr = train_data["y_rank"]
    group_tr = train_data["group"]
    x_rank_ev = eval_data["x_rank"]
    x_adopt_tr = train_data["x_adopt"]
    y_adopt_tr = train_data["y_adopt"]
    x_adopt_ev = eval_data["x_adopt"]

    ranker = _pair_pipeline(
        LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            verbose=-1,
        ),
        pair_num,
        pair_cat,
    )
    ranker.fit(x_rank_tr, y_rank_tr, model__group=group_tr)
    rank_scores = ranker.predict(x_rank_ev)
    report.models.append(_score_row("LightGBM LambdaMART (retrained)", rank_scores, eval_data))

    lgb_cls = _user_pipeline(
        MultiOutputClassifier(
            LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=42,
                verbose=-1,
            )
        ),
        user_num,
        user_cat,
    )
    lgb_cls.fit(x_adopt_tr, y_adopt_tr)
    proba = lgb_cls.predict_proba(x_adopt_ev)
    prob_cols = np.column_stack([p[:, 1] for p in proba])
    flat_adopt = np.repeat(prob_cols, n_s, axis=0).reshape(-1)
    report.models.append(
        _score_row("LightGBM adoption (retrained)", flat_adopt, eval_data, prob_cols)
    )

    hgb = _pair_pipeline(HistGradientBoostingRegressor(random_state=42), pair_num, pair_cat)
    hgb.fit(x_rank_tr, y_rank_tr)
    report.models.append(_score_row("HistGradientBoosting pair regressor", hgb.predict(x_rank_ev), eval_data))

    return report


def evaluate_frozen_ranker(
    ranker: Any,
    eval_data: dict[str, Any],
    *,
    name: str = "Frozen LambdaMART (artifacts)",
) -> ModelScoreRow:
    """Score a persisted ranker pipeline without retraining."""
    scores = ranker.predict(eval_data["x_rank"])
    return _score_row(name, np.asarray(scores, dtype=np.float64), eval_data)


def evaluate_frozen_adoption(
    adoption_model: Any,
    eval_data: dict[str, Any],
    *,
    name: str = "Frozen adoption classifier (artifacts)",
) -> ModelScoreRow:
    """Score persisted adoption model; tile scores across strategies for ranking metrics."""
    n_s = int(eval_data["n_strategies"])
    proba = adoption_model.predict_proba(eval_data["x_adopt"])
    prob_cols = np.column_stack([p[:, 1] for p in proba])
    flat = np.repeat(prob_cols, n_s, axis=0).reshape(-1)
    return _score_row(name, flat, eval_data, prob_cols)


__all__ = [
    "AblationConfig",
    "evaluate_frozen_adoption",
    "evaluate_frozen_ranker",
    "run_ablation_study",
]
