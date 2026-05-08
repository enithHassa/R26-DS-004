"""Load persisted recommendation-model artifacts.

Step 1 integration helper:
- locate artifacts directory
- load model + strategy ids + feature metadata
- expose cached accessor for runtime services
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
from sklearn.compose import _column_transformer as _ct

from app.config import component_settings


class ArtifactLoadError(RuntimeError):
    """Raised when model artifacts cannot be loaded."""


@dataclass(frozen=True)
class InferenceArtifacts:
    model: Any
    strategy_ids: list[str]
    num_features: list[str]
    cat_features: list[str]
    artifacts_dir: Path


def _candidate_artifact_dirs() -> list[Path]:
    """Priority order for artifact discovery."""
    app_dir = Path(__file__).resolve().parents[1] / "artifacts"
    configured = Path(component_settings.COMP_RECOMMENDATION_ARTIFACTS_DIR)
    return [app_dir, configured]


def resolve_artifacts_dir() -> Path:
    required = ("strategy_matcher_model.joblib", "strategy_ids.joblib", "feature_meta.json")
    for d in _candidate_artifact_dirs():
        if all((d / f).exists() for f in required):
            return d
    searched = ", ".join(str(x) for x in _candidate_artifact_dirs())
    raise ArtifactLoadError(
        "Could not find required artifacts "
        f"{required}. Searched: {searched}"
    )


def _install_sklearn_joblib_compat() -> None:
    """Backfill private sklearn symbols used by older serialized pipelines."""
    if not hasattr(_ct, "_RemainderColsList"):
        class _RemainderColsList(list):
            pass

        _ct._RemainderColsList = _RemainderColsList  # type: ignore[attr-defined]


@lru_cache(maxsize=1)
def load_inference_artifacts() -> InferenceArtifacts:
    d = resolve_artifacts_dir()
    try:
        _install_sklearn_joblib_compat()
        model = joblib.load(d / "strategy_matcher_model.joblib")
        strategy_ids_raw = joblib.load(d / "strategy_ids.joblib")
        meta = json.loads((d / "feature_meta.json").read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArtifactLoadError(f"Failed loading artifacts from {d}: {exc}") from exc

    strategy_ids = [str(x) for x in strategy_ids_raw]
    num_features = [str(x) for x in meta.get("num_features", [])]
    cat_features = [str(x) for x in meta.get("cat_features", [])]
    return InferenceArtifacts(
        model=model,
        strategy_ids=strategy_ids,
        num_features=num_features,
        cat_features=cat_features,
        artifacts_dir=d,
    )

