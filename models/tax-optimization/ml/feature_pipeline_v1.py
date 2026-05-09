"""Build and persist the frozen sklearn ``ColumnTransformer`` for feature_version v1.

Reads ``features_v1.json``, verifies ``feature_version`` matches ``best_model_summary.json``,
fits a single-block Pipeline (median ``SimpleImputer`` + ``StandardScaler``) on synthetic data
by default, and saves a joblib bundle next to the regressor artifact.

The transformer uses **integer column indices** ``0 .. n-1`` so ``fit`` / ``transform`` work on
``numpy`` arrays with columns in ``feature_order_in_matrix`` order (same as inference).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_FEATURES_JSON = Path(__file__).resolve().parent / "features_v1.json"
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DEFAULT_OUT_NAME = "tax_opt_feature_pipeline_v1.joblib"
BUNDLE_SCHEMA = "tax_opt_feature_pipeline_bundle_v1"


class FeaturePipelineBundleV1(TypedDict):
    """Joblib bundle written next to ``tax_opt_best_model_v1.joblib``."""

    schema: str
    column_transformer: ColumnTransformer
    metadata: dict[str, Any]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_features_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_feature_version_matches_manifest(
    spec: dict[str, Any],
    summary_path: Path,
) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    fv_spec = spec.get("feature_version")
    fv_sum = summary.get("feature_version")
    if fv_spec != fv_sum:
        msg = (
            f"feature_version mismatch: features spec has {fv_spec!r}, "
            f"best_model_summary.json has {fv_sum!r}"
        )
        raise ValueError(msg)


def build_column_transformer_v1(spec: dict[str, Any]) -> ColumnTransformer:
    cols: list[str] = spec["feature_order_in_matrix"]
    n = len(cols)
    pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[("all_v1", pipe, list(range(n)))],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _synthetic_fit_matrix(
    *,
    n_features: int,
    n_rows: int,
    random_state: int,
) -> np.ndarray:
    rng = np.random.default_rng(random_state)
    return np.ascontiguousarray(rng.normal(size=(n_rows, n_features)), dtype=np.float64)


def build_bundle(
    spec: dict[str, Any],
    *,
    fit_array: np.ndarray | None,
    features_json_path: Path,
    synthetic_rows: int,
    random_state: int,
) -> FeaturePipelineBundleV1:
    cols: list[str] = spec["feature_order_in_matrix"]
    ct = build_column_transformer_v1(spec)
    if fit_array is not None:
        if fit_array.shape[1] != len(cols):
            msg = f"fit matrix has {fit_array.shape[1]} columns, expected {len(cols)}"
            raise ValueError(msg)
        X = np.ascontiguousarray(fit_array, dtype=np.float64)
    else:
        X = _synthetic_fit_matrix(
            n_features=len(cols), n_rows=synthetic_rows, random_state=random_state
        )
    ct.fit(X)
    meta = {
        "feature_version": spec["feature_version"],
        "feature_order_in_matrix": cols,
        "features_json_path": str(features_json_path.as_posix()),
        "features_json_sha256": _sha256_file(features_json_path),
        "column_transformer_indices": list(range(len(cols))),
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fit_rows": int(X.shape[0]),
        "random_state": random_state,
        "bundle_schema": BUNDLE_SCHEMA,
    }
    return {
        "schema": BUNDLE_SCHEMA,
        "column_transformer": ct,
        "metadata": meta,
    }


def save_bundle(bundle: FeaturePipelineBundleV1, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--features-json",
        type=Path,
        default=DEFAULT_FEATURES_JSON,
        help="Path to features_v1.json",
    )
    p.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Directory containing best_model_summary.json and model joblib",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output joblib path (default: <artifacts-dir>/{DEFAULT_OUT_NAME})",
    )
    p.add_argument(
        "--fit-npy",
        type=Path,
        default=None,
        help="Optional path to a .npy file with shape (n_samples, n_features) for fitting",
    )
    p.add_argument(
        "--synthetic-rows",
        type=int,
        default=512,
        help="Rows of synthetic normal data used when --fit-npy is not set",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=0,
    )
    p.add_argument(
        "--skip-version-check",
        action="store_true",
        help="Do not compare feature_version to best_model_summary.json (not recommended)",
    )
    args = p.parse_args(argv)

    spec = load_features_spec(args.features_json)
    summary_path = args.artifacts_dir / "best_model_summary.json"
    if not args.skip_version_check:
        if not summary_path.is_file():
            print(f"error: manifest not found: {summary_path}", file=sys.stderr)
            return 1
        assert_feature_version_matches_manifest(spec, summary_path)

    fit_array: np.ndarray | None = None
    if args.fit_npy is not None:
        fit_array = np.load(args.fit_npy)
        if fit_array.ndim != 2:
            print("error: --fit-npy must be a 2-D array", file=sys.stderr)
            return 1

    out_path = args.out if args.out is not None else (args.artifacts_dir / DEFAULT_OUT_NAME)
    bundle = build_bundle(
        spec,
        fit_array=fit_array,
        features_json_path=args.features_json.resolve(),
        synthetic_rows=args.synthetic_rows,
        random_state=args.random_state,
    )
    save_bundle(bundle, out_path)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
