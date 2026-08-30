"""Orchestrate Phase 6 offline evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from evaluation.ablation import (
    AblationConfig,
    evaluate_frozen_adoption,
    evaluate_frozen_ranker,
    run_ablation_study,
)
from evaluation.dataset import build_eval_dataset
from evaluation.report import EvaluationReport
from strategy_gen.catalog import load_strategy_catalog


def _load_user_meta(path: Path) -> tuple[list[str], list[str]]:
    meta = json.loads(path.read_text(encoding="utf-8"))
    return [str(x) for x in meta["num_features"]], [str(x) for x in meta["cat_features"]]


def _split_frame(df: pd.DataFrame, split: str, limit: int) -> pd.DataFrame:
    mask = df["split"].astype(str).str.lower() == split.lower()
    return df[mask].head(limit).reset_index(drop=True)


def run_offline_evaluation(
    *,
    csv_path: Path,
    catalog_path: Path,
    user_meta_path: Path,
    artifacts_dir: Path | None = None,
    train_limit: int = 8000,
    eval_limit: int = 1500,
    eval_split: str = "val",
    include_ablation: bool = True,
) -> EvaluationReport:
    """Run frozen-artifact eval plus optional ablation retraining."""
    user_num, user_cat = _load_user_meta(user_meta_path)
    catalog = load_strategy_catalog(catalog_path)
    df = pd.read_csv(csv_path)
    train_df = _split_frame(df, "train", train_limit)
    eval_df = _split_frame(df, eval_split, eval_limit)
    eval_data = build_eval_dataset(eval_df, catalog, user_num, user_cat)

    report = EvaluationReport(
        eval_split=eval_split,
        n_profiles=len(eval_df),
        n_strategies=int(eval_data["n_strategies"]),
    )

    if artifacts_dir is not None and (artifacts_dir / "phase4_manifest.json").exists():
        manifest = json.loads((artifacts_dir / "phase4_manifest.json").read_text(encoding="utf-8"))
        ranker = joblib.load(artifacts_dir / str(manifest["ranker_model"]))
        adoption = joblib.load(artifacts_dir / str(manifest["adoption_model"]))
        report.models.append(evaluate_frozen_ranker(ranker, eval_data))
        report.models.append(evaluate_frozen_adoption(adoption, eval_data))
        report.notes.append(f"Loaded frozen artifacts from {artifacts_dir}")
    else:
        report.notes.append("No phase4_manifest.json; skipped frozen artifact eval")

    if include_ablation:
        ablation = run_ablation_study(
            train_df=train_df,
            eval_df=eval_df,
            catalog=catalog,
            user_num=user_num,
            user_cat=user_cat,
            config=AblationConfig(
                train_limit=train_limit,
                eval_limit=eval_limit,
                eval_split=eval_split,
            ),
        )
        existing = {m.name for m in report.models}
        for row in ablation.models:
            if row.name not in existing:
                report.models.append(row)

    return report


__all__ = ["run_offline_evaluation"]
