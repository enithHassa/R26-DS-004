"""Load Function 3 ML artifacts (joblib estimator + manifest) — inference only."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class TaxOptBMlBundleSummaryV1(BaseModel):
    """Shape of ``best_model_summary.json`` (versioned research manifest)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: int = Field(default=1, ge=1)
    model_id: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    training_timestamp: str = Field(min_length=1, description="ISO-8601 timestamp string.")
    model_joblib: str = Field(min_length=1, description="Filename within the artifacts directory.")
    feature_pipeline_joblib: str | None = Field(
        default=None,
        description="Optional joblib bundle with sklearn ColumnTransformer + metadata (feature_version v1).",
    )
    artifact_sha256: str | None = Field(
        default=None,
        description="Optional hex digest; when set, must match the joblib file on disk.",
    )
    synthetic_training_data_disclaimer: str = Field(min_length=1)
    target_name: str = Field(default="savings_vs_baseline_lkr")
    inference_matrix_layout: Literal["v1_12_full", "v1_11_no_savings"] = Field(
        default="v1_12_full",
        description=(
            "v1_12_full: same columns as ML_FEATURE_COLUMN_NAMES_V1 (includes savings). "
            "v1_11_no_savings: research-trained regressors excluding savings_vs_baseline_lkr from X."
        ),
    )
    metrics_v1_path: str | None = Field(
        default=None,
        description="Filename within artifacts dir for metrics_v1.json from eval_tax_opt_models_v1.py.",
    )
    metrics_v1_sha256: str | None = Field(default=None)
    evaluation_timestamp: str | None = Field(
        default=None,
        description="ISO-8601 when eval_tax_opt_models_v1.py last updated metrics.",
    )
    dataset_sha256_training_table: str | None = Field(
        default=None,
        description="SHA-256 of training table parquet/csv used for research.",
    )
    training_row_count: int | None = Field(default=None, ge=0)
    evaluation_random_seeds: list[int] | None = Field(default=None)
    metric_table_test: dict[str, Any] | None = Field(
        default=None,
        description="Subset of metrics_v1.json for the promoted best model (test split).",
    )


class MlArtifactError(Exception):
    """Base class for missing or invalid ML bundle (→ HTTP 503)."""


class MlArtifactNotFoundError(MlArtifactError):
    """Manifest or estimator file missing."""


class MlArtifactChecksumError(MlArtifactError):
    """Estimator checksum mismatch."""


class MlFeatureVersionMismatchError(Exception):
    """Requested feature_version does not match manifest (→ HTTP 424)."""


def file_sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ml_bundle_summary(artifacts_dir: Path) -> TaxOptBMlBundleSummaryV1:
    path = artifacts_dir / "best_model_summary.json"
    if not path.is_file():
        msg = f"ML manifest not found: {path}"
        raise MlArtifactNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    return TaxOptBMlBundleSummaryV1.model_validate(data)


def load_ml_estimator(artifacts_dir: Path, summary: TaxOptBMlBundleSummaryV1) -> Any:
    est_path = (artifacts_dir / summary.model_joblib).resolve()
    if not est_path.is_file():
        msg = f"ML estimator not found: {est_path}"
        raise MlArtifactNotFoundError(msg)
    digest = file_sha256_hex(est_path)
    if summary.artifact_sha256 and digest.lower() != summary.artifact_sha256.lower():
        msg = "ML estimator SHA-256 does not match best_model_summary.json"
        raise MlArtifactChecksumError(msg)
    return joblib.load(est_path)


def measure_predict_latency_ms(estimator: Any, X: np.ndarray) -> tuple[np.ndarray, float]:
    t0 = time.perf_counter()
    y = np.asarray(estimator.predict(X), dtype=np.float64)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if y.ndim != 1:
        msg = "Estimator must return a 1-D prediction vector."
        raise ValueError(msg)
    return y, elapsed_ms
