"""Model zoo training for Function 3 strategy rows (research comparison).

Loads a long-format table from ``build_training_table.py`` (Parquet or CSV), builds the
v1 feature matrix (without ``savings_vs_baseline_lkr`` in **X** when the primary target is
savings — aligns with ``inference_matrix_layout: v1_11_no_savings``), and compares:

- ``RandomForestRegressor``
- ``GradientBoostingRegressor``
- ``ExtraTreesRegressor``
- ``lightgbm.LGBMRegressor``

**XGBoost** is intentionally omitted unless you add ``xgboost`` to ``models/requirements-ml.txt``.

Splits are **grouped by ``taxpayer_id``** so rows from the same taxpayer stay in one split
(train / validation / test). Uses a fixed ``random_state`` on the shuffled unique
taxpayer ids (equivalent intent to ``GroupShuffleSplit`` in two stages).

Targets
-------

- **Primary (default):** ``savings_vs_baseline_lkr`` — regression in LKR. **X** uses 11 columns
  (all ``ML_FEATURE_COLUMN_NAMES_V1`` except savings) to avoid trivial target leakage; savings
  is still computable from ``baseline_tax_lkr`` and ``total_tax_lkr`` but the model is not given
  the clipped savings column as an input feature.
- **Secondary (optional):** ``rule_rank_among_passing`` — we treat the integer rank **1…K**
  (within taxpayer, ``rank_by=total_tax`` from the training builder) as a **real-valued**
  regression target for an exploratory baseline only. Ranks are **ordinal** and **grouped**;
  proper treatment would use learning-to-rank, ordinal regression, or per-group normalization.
  Metrics (MAE on rank, RMSE, R²) are **not** authoritative ranking quality; use them only
  to compare whether tree ensembles can approximate rule order under a simple surrogate loss.

Examples
--------

.. code-block:: bash

   python models/tax-optimization/ml/train/train_tax_opt_models_v1.py \\\\
       --train-table models/tax-optimization/datasets/ml/training_v1.parquet \\\\
       --artifacts-dir models/tax-optimization/artifacts \\\\
       --leaderboard-out models/tax-optimization/artifacts/model_zoo_leaderboard_v1.json

Promote the best (primary target only) to API artifacts:

.. code-block:: bash

   python ... --promote-best

**Memory (Windows / large parquet):** ``--n-jobs 1`` only avoids *multi-process* RAM blow-ups; fitting
RandomForest on **~1M+ training rows** still needs huge RAM for tree structures. Use
``--max-taxpayers``, ``--forest-max-depth``, lower ``--rf-n-estimators`` / ``--et-n-estimators``, or a
smaller parquet. Features are cast to **float32** before fitting to halve ``X`` size.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMRegressor
except ImportError:
    LGBMRegressor = None  # type: ignore[misc, assignment]

PRIMARY_TARGET = "savings_vs_baseline_lkr"
SECONDARY_TARGET = "rule_rank_among_passing"

# Same order as backend ML_FEATURE_COLUMN_NAMES_V1 without savings (inference v1_11_no_savings).
FEATURE_COLUMNS_V1_11: tuple[str, ...] = (
    "annual_gross_income",
    "annual_salary_income",
    "annual_business_income",
    "annual_other_income",
    "dependents",
    "employment_type_code",
    "n_ordered_relief_codes",
    "n_included_relief_codes",
    "candidate_mask",
    "total_tax_lkr",
    "baseline_tax_lkr",
)

_EMP_MAP = {
    "employee": 0.0,
    "self_employed": 1.0,
    "business_owner": 2.0,
    "other": 3.0,
}


def _parse_money(val: Any) -> float:
    if pd.isna(val):
        return float("nan")
    if isinstance(val, bool):
        return float("nan")
    if isinstance(val, (int, float, np.floating)):
        return float(val)
    s = str(val).strip().replace(",", "")
    if not s:
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _employment_code(raw: Any) -> float:
    if pd.isna(raw):
        return 3.0
    k = str(raw).strip().lower().replace("-", "_")
    return float(_EMP_MAP.get(k, 3.0))


def load_training_table(path: Path) -> pd.DataFrame:
    path = path.resolve()
    if not path.is_file():
        msg = f"Training table not found: {path}"
        raise FileNotFoundError(msg)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def subsample_taxpayers_df(df: pd.DataFrame, max_taxpayers: int | None, random_state: int) -> pd.DataFrame:
    """Keep all strategy rows only for a random subset of distinct ``taxpayer_id`` values."""
    if max_taxpayers is None or max_taxpayers < 1:
        return df
    if "taxpayer_id" not in df.columns:
        return df
    u = df["taxpayer_id"].astype(str).unique()
    if len(u) <= max_taxpayers:
        return df
    rng = np.random.default_rng(random_state)
    pick = rng.choice(u, size=max_taxpayers, replace=False)
    return df[df["taxpayer_id"].astype(str).isin(pick)].reset_index(drop=True)


def build_xy_with_frame(
    df: pd.DataFrame,
    *,
    target: Literal["savings_vs_baseline_lkr", "rule_rank_among_passing"],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """Aligned filtered frame and arrays (same row order)."""

    d = df
    need = {
        "taxpayer_id",
        "annual_salary_income",
        "annual_business_income",
        "annual_other_income",
        "dependents",
        "employment_type",
        "n_included_relief_codes",
        "candidate_mask",
        "total_tax_lkr",
        "baseline_tax_lkr",
        target,
    }
    missing = need - set(d.columns)
    if missing:
        msg = f"Training table missing columns: {sorted(missing)}"
        raise ValueError(msg)

    sal = d["annual_salary_income"].map(_parse_money)
    bus = d["annual_business_income"].map(_parse_money)
    oth = d["annual_other_income"].map(_parse_money)
    gross = sal + bus + oth
    dep = pd.to_numeric(d["dependents"], errors="coerce").fillna(0.0)
    et_code = d["employment_type"].map(_employment_code)
    if "n_ordered_relief_codes" in d.columns:
        n_ord = pd.to_numeric(d["n_ordered_relief_codes"], errors="coerce")
    else:
        n_ord = pd.Series(np.nan, index=d.index, dtype=float)
    n_inc = pd.to_numeric(d["n_included_relief_codes"], errors="coerce").fillna(0.0)
    mask = pd.to_numeric(d["candidate_mask"], errors="coerce").fillna(0.0)
    tax = d["total_tax_lkr"].map(_parse_money)
    base = d["baseline_tax_lkr"].map(_parse_money)

    if target == PRIMARY_TARGET:
        y = d["savings_vs_baseline_lkr"].map(_parse_money).to_numpy(dtype=np.float64)
    else:
        y = pd.to_numeric(d["rule_rank_among_passing"], errors="coerce").to_numpy(dtype=np.float64)

    X = np.column_stack(
        [
            gross.to_numpy(dtype=np.float64),
            sal.to_numpy(dtype=np.float64),
            bus.to_numpy(dtype=np.float64),
            oth.to_numpy(dtype=np.float64),
            dep.to_numpy(dtype=np.float64),
            et_code.to_numpy(dtype=np.float64),
            n_ord.to_numpy(dtype=np.float64),
            n_inc.to_numpy(dtype=np.float64),
            mask.to_numpy(dtype=np.float64),
            tax.to_numpy(dtype=np.float64),
            base.to_numpy(dtype=np.float64),
        ]
    )
    groups = d["taxpayer_id"].astype(str).to_numpy()
    valid = np.isfinite(y) & np.isfinite(X).all(axis=1)
    d_sub = d.loc[valid].reset_index(drop=True)
    return d_sub, X[valid], y[valid], groups[valid]


def build_xy_arrays(
    df: pd.DataFrame,
    *,
    target: Literal["savings_vs_baseline_lkr", "rule_rank_among_passing"],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``X`` (n, 11), ``y`` (n,), ``groups`` (n,) taxpayer ids as strings."""
    _d_sub, X, y, groups = build_xy_with_frame(df, target=target)
    return X, y, groups


def group_train_val_test_masks(
    groups: np.ndarray,
    *,
    train_frac: float,
    val_frac: float,
    test_frac: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not np.isclose(train_frac + val_frac + test_frac, 1.0):
        msg = "train_frac + val_frac + test_frac must sum to 1"
        raise ValueError(msg)
    unique = np.unique(groups)
    rng = np.random.default_rng(random_state)
    unique = unique[rng.permutation(len(unique))]
    n = len(unique)
    if n == 0:
        msg = "No groups (taxpayer_id) in data"
        raise ValueError(msg)

    if n == 1:
        tr_ids = set(unique)
        va_ids: set[Any] = set()
        te_ids: set[Any] = set()
    elif n == 2:
        tr_ids = {unique[0]}
        te_ids = {unique[1]}
        va_ids = set()
    else:
        n_train = max(1, int(round(train_frac * n)))
        n_val = max(1, int(round(val_frac * n)))
        n_test = max(1, n - n_train - n_val)
        while n_train + n_val + n_test > n:
            if n_val > 1:
                n_val -= 1
            elif n_train > 1:
                n_train -= 1
            else:
                break
        while n_train + n_val + n_test < n:
            n_train += 1
        i0, i1, i2 = 0, n_train, n_train + n_val
        tr_ids = set(unique[i0:i1])
        va_ids = set(unique[i1:i2])
        te_ids = set(unique[i2 : i2 + n_test])
        rest = set(unique[i2 + n_test :])
        tr_ids.update(rest)

    train_m = np.array([g in tr_ids for g in groups], dtype=bool)
    val_m = np.array([g in va_ids for g in groups], dtype=bool)
    test_m = np.array([g in te_ids for g in groups], dtype=bool)
    if val_m.sum() == 0 and n > 1 and test_m.sum() > 0:
        one_id = next(iter(te_ids))
        val_m = groups == one_id
        test_m &= ~val_m
    return train_m, val_m, test_m


def group_train_val_test_masks_sklearn(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    test_size: float,
    val_size_of_remaining: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Two ``GroupShuffleSplit`` stages: hold out test, then hold out val from remainder."""
    gss_te = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    idx_all = np.arange(len(y))
    idx_trv, idx_te = next(gss_te.split(X, y, groups))
    X_trv, y_trv, g_trv = X[idx_trv], y[idx_trv], groups[idx_trv]
    rel_val = val_size_of_remaining
    gss_va = GroupShuffleSplit(n_splits=1, test_size=rel_val, random_state=random_state + 41)
    idx_tr_rel, idx_va_rel = next(gss_va.split(X_trv, y_trv, g_trv))
    train_m = np.zeros(len(y), dtype=bool)
    val_m = np.zeros(len(y), dtype=bool)
    test_m = np.zeros(len(y), dtype=bool)
    train_m[idx_trv[idx_tr_rel]] = True
    val_m[idx_trv[idx_va_rel]] = True
    test_m[idx_te] = True
    return train_m, val_m, test_m


def make_model_zoo(
    random_state: int,
    *,
    n_jobs: int = 1,
    rf_n_estimators: int = 400,
    et_n_estimators: int = 500,
    forest_max_depth: int | None = None,
    gb_n_estimators: int = 250,
    lgbm_n_estimators: int = 400,
    lgbm_num_leaves: int = 48,
) -> dict[str, Any]:
    """``n_jobs`` for RF/ET/LGBM. Cap ``forest_max_depth`` / fewer estimators when RAM is tight."""
    out: dict[str, Any] = {
        "sklearn_random_forest": RandomForestRegressor(
            n_estimators=rf_n_estimators,
            max_depth=forest_max_depth,
            random_state=random_state,
            n_jobs=n_jobs,
        ),
        "sklearn_extra_trees": ExtraTreesRegressor(
            n_estimators=et_n_estimators,
            max_depth=forest_max_depth,
            random_state=random_state,
            n_jobs=n_jobs,
        ),
        "sklearn_gradient_boosting": GradientBoostingRegressor(
            random_state=random_state,
            n_estimators=gb_n_estimators,
            max_depth=5,
            learning_rate=0.08,
        ),
    }
    if LGBMRegressor is not None:
        out["lightgbm_lgbm"] = LGBMRegressor(
            n_estimators=lgbm_n_estimators,
            learning_rate=0.05,
            num_leaves=lgbm_num_leaves,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=random_state,
            n_jobs=n_jobs,
            verbose=-1,
        )
    return out


def build_preprocess_pipeline(model: Any) -> Pipeline:
    """Median imputation + scaling + estimator (trees are scale-invariant; keeps protocol uniform)."""
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", model),
        ]
    )


@dataclass
class FitScores:
    val_mae: float
    val_rmse: float
    val_r2: float
    test_mae: float
    test_rmse: float
    test_r2: float


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def fit_and_score(
    pipe: Pipeline,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> FitScores:
    pipe.fit(X_train, y_train)
    p_val = pipe.predict(X_val)
    p_te = pipe.predict(X_test)
    return FitScores(
        val_mae=float(mean_absolute_error(y_val, p_val)),
        val_rmse=_rmse(y_val, p_val),
        val_r2=float(r2_score(y_val, p_val)),
        test_mae=float(mean_absolute_error(y_test, p_te)),
        test_rmse=_rmse(y_test, p_te),
        test_r2=float(r2_score(y_test, p_te)),
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-table", type=Path, required=True)
    ap.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "artifacts",
    )
    ap.add_argument(
        "--leaderboard-out",
        type=Path,
        default=None,
        help="JSON path (default: <artifacts-dir>/model_zoo_leaderboard_v1.json)",
    )
    ap.add_argument("--feature-version", type=str, default="v1")
    ap.add_argument(
        "--target",
        choices=(PRIMARY_TARGET, SECONDARY_TARGET),
        default=PRIMARY_TARGET,
    )
    ap.add_argument("--train-frac", type=float, default=0.70)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--random-state", type=int, default=42)
    ap.add_argument(
        "--split-method",
        choices=("group_shuffle_sklearn", "group_shuffle_manual"),
        default="group_shuffle_sklearn",
        help="Use sklearn GroupShuffleSplit (recommended) or manual taxpayer sharding.",
    )
    ap.add_argument(
        "--promote-best",
        action="store_true",
        help=f"Write best model to tax_opt_best_model_v1.joblib and refresh best_model_summary.json "
        f"(allowed only for target={PRIMARY_TARGET}).",
    )
    ap.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Parallel workers for RF/ExtraTrees/LightGBM (default 1: lowest RAM; -1 uses all cores, may OOM on large data).",
    )
    ap.add_argument(
        "--max-taxpayers",
        type=int,
        default=None,
        help="Subsample this many distinct taxpayer_id values (all their strategy rows). Cuts RAM and runtime.",
    )
    ap.add_argument(
        "--rf-n-estimators",
        type=int,
        default=400,
        help="RandomForest tree count (lower on large data if MemoryError).",
    )
    ap.add_argument(
        "--et-n-estimators",
        type=int,
        default=500,
        help="ExtraTrees tree count.",
    )
    ap.add_argument(
        "--forest-max-depth",
        type=int,
        default=None,
        help="Max depth for RF and ExtraTrees (omit for unlimited; set e.g. 16–24 to cap RAM).",
    )
    ap.add_argument("--gb-n-estimators", type=int, default=250, help="GradientBoosting stages.")
    ap.add_argument("--lgbm-n-estimators", type=int, default=400, help="LightGBM boosting rounds.")
    ap.add_argument("--lgbm-num-leaves", type=int, default=48, help="LightGBM num_leaves (lower = less RAM).")
    args = ap.parse_args(argv)

    if not np.isclose(args.train_frac + args.val_frac + args.test_frac, 1.0):
        print("error: train/val/test fractions must sum to 1", file=sys.stderr)
        return 1
    if args.promote_best and args.target != PRIMARY_TARGET:
        print("error: --promote-best requires --target savings_vs_baseline_lkr", file=sys.stderr)
        return 1

    df = load_training_table(args.train_table)
    n_before = len(df)
    df = subsample_taxpayers_df(df, args.max_taxpayers, args.random_state)
    if len(df) != n_before and args.max_taxpayers is not None:
        print(
            f"subsampled taxpayers: {n_before} -> {len(df)} rows "
            f"(max_taxpayers={args.max_taxpayers})",
            file=sys.stderr,
        )
    X, y, groups = build_xy_arrays(df, target=args.target)
    X = np.ascontiguousarray(X, dtype=np.float32)
    y = np.ascontiguousarray(y, dtype=np.float32)
    if len(y) < 50:
        print(f"warning: only {len(y)} rows after filtering; metrics will be noisy", file=sys.stderr)

    if args.split_method == "group_shuffle_sklearn":
        train_m, val_m, test_m = group_train_val_test_masks_sklearn(
            X,
            y,
            groups,
            test_size=args.test_frac,
            val_size_of_remaining=args.val_frac / (args.train_frac + args.val_frac),
            random_state=args.random_state,
        )
    else:
        train_m, val_m, test_m = group_train_val_test_masks(
            groups,
            train_frac=args.train_frac,
            val_frac=args.val_frac,
            test_frac=args.test_frac,
            random_state=args.random_state,
        )

    X_tr, y_tr = X[train_m], y[train_m]
    X_va, y_va = X[val_m], y[val_m]
    X_te, y_te = X[test_m], y[test_m]
    if X_tr.shape[0] == 0 or X_va.shape[0] == 0:
        print("error: empty train or val after group split; add more taxpayers", file=sys.stderr)
        return 1

    zoo = make_model_zoo(
        args.random_state,
        n_jobs=args.n_jobs,
        rf_n_estimators=args.rf_n_estimators,
        et_n_estimators=args.et_n_estimators,
        forest_max_depth=args.forest_max_depth,
        gb_n_estimators=args.gb_n_estimators,
        lgbm_n_estimators=args.lgbm_n_estimators,
        lgbm_num_leaves=args.lgbm_num_leaves,
    )
    rows: list[dict[str, Any]] = []
    best_name: str | None = None
    best_val_mae = float("inf")
    best_pipe: Pipeline | None = None

    for name, base in zoo.items():
        pipe = build_preprocess_pipeline(base)
        scores = fit_and_score(pipe, X_tr, y_tr, X_va, y_va, X_te, y_te)
        rows.append(
            {
                "model": name,
                "val_mae": scores.val_mae,
                "val_rmse": scores.val_rmse,
                "val_r2": scores.val_r2,
                "test_mae": scores.test_mae,
                "test_rmse": scores.test_rmse,
                "test_r2": scores.test_r2,
            }
        )
        if scores.val_mae < best_val_mae:
            best_val_mae = scores.val_mae
            best_name = name
            best_pipe = pipe

    assert best_name is not None and best_pipe is not None

    out_dir = args.artifacts_dir.resolve()
    board_path = args.leaderboard_out or (out_dir / "model_zoo_leaderboard_v1.json")

    ts = datetime.now(timezone.utc).replace(microsecond=0)

    spearman_note = None
    try:
        from scipy.stats import spearmanr

        pred_tr = best_pipe.predict(X_va)
        corr, _p = spearmanr(y_va, pred_tr)
        spearman_note = float(corr) if np.isfinite(corr) else None
    except ImportError:
        spearman_note = None

    targets_doc = {
        PRIMARY_TARGET: {
            "paradigm": "regression",
            "unit": "LKR",
            "x_columns": list(FEATURE_COLUMNS_V1_11),
            "notes": "X excludes savings_vs_baseline_lkr; matches API inference_matrix_layout v1_11_no_savings.",
        },
        SECONDARY_TARGET: {
            "paradigm": "regression_surrogate_on_ordinal_ranks",
            "unit": "dimensionless_rank",
            "x_columns": list(FEATURE_COLUMNS_V1_11),
            "caveats": (
                "rule_rank_among_passing is discrete and ordinal within taxpayer; "
                "MSE/MAE/R2 treat it as real-valued. Prefer learning-to-rank or per-group models "
                "for research conclusions; this zoo entry is for coarse comparison only."
            ),
        },
    }

    board = {
        "schema_version": 1,
        "generated_at_utc": ts.isoformat().replace("+00:00", "Z"),
        "train_table": str(args.train_table.resolve().as_posix()),
        "train_table_sha256": _sha256_file(args.train_table),
        "feature_version": args.feature_version,
        "protocol": {
            "split": "group_by_taxpayer_id",
            "split_method": args.split_method,
            "train_frac": args.train_frac,
            "val_frac": args.val_frac,
            "test_frac": args.test_frac,
            "random_state": args.random_state,
            "max_taxpayers_cap": args.max_taxpayers,
            "sklearn_ensemble_n_jobs": args.n_jobs,
            "rf_n_estimators": args.rf_n_estimators,
            "et_n_estimators": args.et_n_estimators,
            "forest_max_depth": args.forest_max_depth,
            "feature_matrix_dtype": "float32",
            "rows_total": int(len(y)),
            "rows_train": int(train_m.sum()),
            "rows_val": int(val_m.sum()),
            "rows_test": int(test_m.sum()),
            "unique_taxpayers": int(np.unique(groups).size),
        },
        "target": args.target,
        "targets_documentation": targets_doc,
        "feature_columns_X": list(FEATURE_COLUMNS_V1_11),
        "models": sorted(rows, key=lambda r: r["val_mae"]),
        "best_model_by_val_mae": best_name,
        "best_validation_spearman": spearman_note,
        "models_excluded": {
            "xgboost": "not installed; add xgboost to models/requirements-ml.txt to enable XGBRegressor.",
            **(
                {"lightgbm": "lightgbm not importable; use models/requirements-ml.txt environment."}
                if LGBMRegressor is None
                else {}
            ),
        },
    }

    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    print(f"wrote leaderboard {board_path}")

    if args.promote_best:
        X_fit = np.vstack([X_tr, X_va])
        y_fit = np.concatenate([y_tr, y_va])
        best_pipe.fit(X_fit, y_fit)
        model_path = out_dir / "tax_opt_best_model_v1.joblib"
        joblib.dump(best_pipe, model_path)
        digest = _sha256_file(model_path)
        summary_path = out_dir / "best_model_summary.json"
        summary = {
            "schema_version": 1,
            "model_id": f"research_{best_name}_v1",
            "feature_version": args.feature_version,
            "training_timestamp": ts.isoformat().replace("+00:00", "Z"),
            "model_joblib": model_path.name,
            "feature_pipeline_joblib": "tax_opt_feature_pipeline_v1.joblib",
            "artifact_sha256": digest,
            "synthetic_training_data_disclaimer": (
                "Research model from train_tax_opt_models_v1.py; rules engine remains authoritative."
            ),
            "target_name": PRIMARY_TARGET,
            "inference_matrix_layout": "v1_11_no_savings",
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"wrote {model_path}")
        print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
