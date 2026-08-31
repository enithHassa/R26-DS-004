"""Load persisted recommendation-model artifacts (legacy matcher or Phase 4 ranker + adoption)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import _column_transformer as _ct
from sklearn.preprocessing import FunctionTransformer

from app.config import component_settings


class ArtifactLoadError(RuntimeError):
    """Raised when model artifacts cannot be loaded."""


@dataclass(frozen=True)
class InferenceArtifacts:
    """Runtime models for recommendations.

    ``mode``:
    - ``legacy`` — single multi-label matcher (user features only).
    - ``phase4`` — adoption classifier (user features) + LambdaMART ranker (user×strategy pairs).
    """

    mode: Literal["legacy", "phase4"]
    model: Any | None
    strategy_ids: list[str]
    num_features: list[str]
    cat_features: list[str]
    artifacts_dir: Path
    adoption_model: Any | None = None
    ranker_model: Any | None = None


def _candidate_artifact_dirs() -> list[Path]:
    """Priority order for artifact discovery."""
    app_dir = Path(__file__).resolve().parents[1] / "artifacts"
    configured = Path(component_settings.COMP_RECOMMENDATION_ARTIFACTS_DIR)
    return [app_dir, configured]


def _is_phase4_dir(d: Path) -> bool:
    manifest = d / "phase4_manifest.json"
    if not manifest.exists():
        return False
    try:
        man = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in ("adoption_model", "ranker_model", "strategy_ids"):
        fn = man.get(key)
        if not fn or not (d / str(fn)).exists():
            return False
    return True


def _is_legacy_dir(d: Path) -> bool:
    required = ("strategy_matcher_model.joblib", "strategy_ids.joblib", "feature_meta.json")
    return all((d / f).exists() for f in required)


def resolve_artifacts_dir() -> Path:
    for d in _candidate_artifact_dirs():
        if _is_phase4_dir(d):
            return d
    for d in _candidate_artifact_dirs():
        if _is_legacy_dir(d):
            return d
    searched = ", ".join(str(x) for x in _candidate_artifact_dirs())
    raise ArtifactLoadError(
        "Could not find Phase 4 (phase4_manifest.json + adoption + ranker) or legacy "
        f"(strategy_matcher_model.joblib, ...). Searched: {searched}"
    )


def _install_sklearn_joblib_compat() -> None:
    """Backfill private sklearn symbols used by older serialized pipelines."""
    if not hasattr(_ct, "_RemainderColsList"):
        class _RemainderColsList(list):
            pass

        _ct._RemainderColsList = _RemainderColsList  # type: ignore[attr-defined]


def _phase4_prep_needs_repair(prep: Any) -> bool:
    """Detect sklearn 1.6 pipelines whose remainder column list was lost on unpickle."""
    if not hasattr(prep, "transformers_"):
        return False
    for name, _trans, cols in prep.transformers_:
        if name == "remainder" and not cols:
            return True
    return False


def _repair_phase4_prep_step(
    pipeline: Any,
    *,
    num_features: list[str],
    cat_features: list[str],
) -> None:
    """Replace a broken ColumnTransformer prep step with an equivalent transform.

    Phase 4 artifacts were trained with sklearn 1.6.1. When loaded under sklearn
    1.8, the private ``_RemainderColsList`` remainder columns unpickle as empty,
    so only one-hot columns reach LightGBM (32 instead of 60 features).
    """
    prep = pipeline.named_steps.get("prep")
    if prep is None or not _phase4_prep_needs_repair(prep):
        return

    ohe = prep.named_transformers_["cat"]
    num_cols = list(num_features)
    cat_cols = list(cat_features)

    def _transform(X: Any) -> np.ndarray:
        frame = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=[*num_cols, *cat_cols])
        cat_part = ohe.transform(frame[cat_cols])
        num_part = frame[num_cols].to_numpy()
        return np.hstack([cat_part, num_part])

    pipeline.steps[0] = ("prep", FunctionTransformer(_transform, validate=False))


def _repair_phase4_models(
    adoption_model: Any,
    ranker_model: Any,
    *,
    num_features: list[str],
    cat_features: list[str],
) -> None:
    _repair_phase4_prep_step(
        adoption_model,
        num_features=num_features,
        cat_features=cat_features,
    )
    pair_num = [*num_features, "strategy_priority_hint"]
    pair_cat = [*cat_features, "strategy_id", "strategy_category"]
    _repair_phase4_prep_step(
        ranker_model,
        num_features=pair_num,
        cat_features=pair_cat,
    )


@lru_cache(maxsize=1)
def load_inference_artifacts() -> InferenceArtifacts:
    d = resolve_artifacts_dir()
    _install_sklearn_joblib_compat()
    try:
        if _is_phase4_dir(d):
            manifest = json.loads((d / "phase4_manifest.json").read_text(encoding="utf-8"))
            adoption = joblib.load(d / str(manifest["adoption_model"]))
            ranker = joblib.load(d / str(manifest["ranker_model"]))
            strategy_ids_raw = joblib.load(d / str(manifest["strategy_ids"]))
            user_meta = json.loads((d / str(manifest["user_feature_meta"])).read_text(encoding="utf-8"))
            num_features = [str(x) for x in user_meta.get("num_features", [])]
            cat_features = [str(x) for x in user_meta.get("cat_features", [])]
            strategy_ids = [str(x) for x in strategy_ids_raw]
            _repair_phase4_models(
                adoption,
                ranker,
                num_features=num_features,
                cat_features=cat_features,
            )
            return InferenceArtifacts(
                mode="phase4",
                model=None,
                strategy_ids=strategy_ids,
                num_features=num_features,
                cat_features=cat_features,
                artifacts_dir=d,
                adoption_model=adoption,
                ranker_model=ranker,
            )

        model = joblib.load(d / "strategy_matcher_model.joblib")
        strategy_ids_raw = joblib.load(d / "strategy_ids.joblib")
        meta = json.loads((d / "feature_meta.json").read_text(encoding="utf-8"))
        strategy_ids = [str(x) for x in strategy_ids_raw]
        num_features = [str(x) for x in meta.get("num_features", [])]
        cat_features = [str(x) for x in meta.get("cat_features", [])]
        return InferenceArtifacts(
            mode="legacy",
            model=model,
            strategy_ids=strategy_ids,
            num_features=num_features,
            cat_features=cat_features,
            artifacts_dir=d,
            adoption_model=None,
            ranker_model=None,
        )
    except Exception as exc:
        raise ArtifactLoadError(f"Failed loading artifacts from {d}: {exc}") from exc
