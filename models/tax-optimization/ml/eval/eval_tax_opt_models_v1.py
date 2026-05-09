"""Full evaluation pipeline: regression + per-taxpayer ranking + stability + latency.

Writes ``metrics_v1.json`` and optionally refreshes ``best_model_summary.json`` with a metric
table and dataset hashes. Assumes rows are **post-compliance passing strategies only** (see
``constraint_compliance`` section in the JSON output).

Artifact naming (joblib, relative to ``--artifacts-dir``)::

    tax_opt_rf_v1.joblib
    tax_opt_gb_v1.joblib
    tax_opt_et_v1.joblib
    tax_opt_lgbm_v1.joblib   (if LightGBM available)
    tax_opt_best_model_v1.joblib

Feature preprocessor example in-repo: ``tax_opt_feature_pipeline_v1.joblib`` (see
``feature_pipeline_v1.py``).

**Metric accounting:** test regression and ranking metrics use estimators fit on the **train
partition only**. Saved estimator files are **refit on train+val** after metric computation so
they match the promotion workflow in ``train_tax_opt_models_v1.py`` (slightly different from
the point estimates on test).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

_ML = Path(__file__).resolve().parent.parent
_TRAIN = _ML / "train"
if str(_TRAIN) not in sys.path:
    sys.path.insert(0, str(_TRAIN))

import train_tax_opt_models_v1 as tt  # noqa: E402

ZOO_TO_FILENAME: dict[str, str] = {
    "sklearn_random_forest": "tax_opt_rf_v1.joblib",
    "sklearn_gradient_boosting": "tax_opt_gb_v1.joblib",
    "sklearn_extra_trees": "tax_opt_et_v1.joblib",
    "lightgbm_lgbm": "tax_opt_lgbm_v1.joblib",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _regression_dict(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": _rmse(y_true, y_pred),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _ranking_within_taxpayer(
    df_te: pd.DataFrame,
    y_pred: np.ndarray,
    top_k_list: tuple[int, ...],
) -> dict[str, Any]:
    """Rule order from ``rule_rank_among_passing`` (1 = best total_tax); ML order by descending pred."""
    try:
        from scipy.stats import kendalltau, spearmanr
    except ImportError:
        return {
            "error": "scipy required for spearman/kendall (install scipy or use models/requirements-ml.txt).",
        }

    if len(df_te) != len(y_pred):
        msg = "df_te and y_pred length mismatch"
        raise ValueError(msg)
    if "rule_rank_among_passing" not in df_te.columns:
        msg = "rule_rank_among_passing column required for ranking metrics"
        raise ValueError(msg)

    rule = pd.to_numeric(df_te["rule_rank_among_passing"], errors="coerce").to_numpy()
    grp = df_te["taxpayer_id"].astype(str).to_numpy()

    spearmans: list[float] = []
    kendalls: list[float] = []
    top_hits: dict[int, list[bool]] = {k: [] for k in top_k_list}

    for tid in np.unique(grp):
        m = grp == tid
        n = int(m.sum())
        if n < 2:
            spearmans.append(1.0)
            kendalls.append(1.0)
            for k in top_k_list:
                top_hits[k].append(True)
            continue
        r = rule[m].astype(np.float64)
        p = y_pred[m]
        ml_rank = np.argsort(np.argsort(-p)) + 1.0  # 1 = highest predicted savings
        sp, _ = spearmanr(r, ml_rank)
        kd, _ = kendalltau(r, ml_rank)
        spearmans.append(float(sp) if np.isfinite(sp) else 0.0)
        kendalls.append(float(kd) if np.isfinite(kd) else 0.0)

        best_idx = np.flatnonzero(r == 1)
        if best_idx.size != 1:
            for k in top_k_list:
                top_hits[k].append(False)
            continue
        bl = int(best_idx[0])
        order = np.argsort(-p)
        pos = int(np.where(order == bl)[0][0])
        for k in top_k_list:
            top_hits[k].append(pos < k)

    out: dict[str, Any] = {
        "spearman_within_taxpayer_mean": float(np.nanmean(spearmans)),
        "spearman_within_taxpayer_std": float(np.nanstd(spearmans)),
        "kendall_within_taxpayer_mean": float(np.nanmean(kendalls)),
        "kendall_within_taxpayer_std": float(np.nanstd(kendalls)),
        "top_k_hit_rate": {str(k): float(np.mean(top_hits[k])) for k in top_k_list},
        "n_taxpayers_evaluated": int(len(spearmans)),
    }
    return out


def _bootstrap_test_mae(
    y_te: np.ndarray,
    y_pred: np.ndarray,
    groups_te: np.ndarray,
    *,
    n_boot: int,
    random_state: int,
) -> dict[str, float]:
    rng = np.random.default_rng(random_state)
    ut = np.unique(groups_te)
    stats: list[float] = []
    for _ in range(n_boot):
        sample_t = rng.choice(ut, size=len(ut), replace=True)
        idx = np.concatenate([np.flatnonzero(groups_te == t) for t in sample_t])
        stats.append(float(mean_absolute_error(y_te[idx], y_pred[idx])))
    arr = np.asarray(stats, dtype=np.float64)
    return {
        "bootstrap_samples": int(n_boot),
        "test_mae_low": float(np.percentile(arr, 2.5)),
        "test_mae_mid": float(np.percentile(arr, 50.0)),
        "test_mae_high": float(np.percentile(arr, 97.5)),
    }


def _multi_seed_test_mae(
    *,
    best_key: str,
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_te: np.ndarray,
    y_te: np.ndarray,
    seeds: list[int],
    n_jobs: int,
) -> dict[str, Any]:
    maes: list[float] = []
    for s in seeds:
        zoo = tt.make_model_zoo(s, n_jobs=n_jobs)
        if best_key not in zoo:
            continue
        pipe = tt.build_preprocess_pipeline(zoo[best_key])
        pipe.fit(X_tr, y_tr)
        maes.append(float(mean_absolute_error(y_te, pipe.predict(X_te))))
    if not maes:
        return {"note": "best_key missing for repeated seeds (e.g. lightgbm unavailable)"}
    arr = np.asarray(maes, dtype=np.float64)
    return {
        "seeds": list(seeds),
        "test_mae_per_seed": maes,
        "test_mae_mean": float(np.mean(arr)),
        "test_mae_std": float(np.std(arr)),
    }


def _latency_benchmark(estimator: Any, X_batch: np.ndarray, *, repeats: int) -> dict[str, Any]:
    estimator.predict(X_batch)
    t0 = time.perf_counter()
    for _ in range(repeats):
        estimator.predict(X_batch)
    elapsed_ms = (time.perf_counter() - t0) / repeats * 1000.0
    return {
        "batch_size_rows": int(X_batch.shape[0]),
        "n_features": int(X_batch.shape[1]),
        "predict_ms_per_batch": float(elapsed_ms),
        "repeats": int(repeats),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-table", type=Path, required=True)
    ap.add_argument(
        "--artifacts-dir",
        type=Path,
        default=_ML.parent / "artifacts",
    )
    ap.add_argument("--feature-version", type=str, default="v1")
    ap.add_argument("--train-frac", type=float, default=0.70)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--random-state", type=int, default=42)
    ap.add_argument(
        "--split-method",
        choices=("group_shuffle_sklearn", "group_shuffle_manual"),
        default="group_shuffle_sklearn",
    )
    ap.add_argument("--top-k", type=str, default="1,3,5,10", help="Comma-separated k for hit rate")
    ap.add_argument("--bootstrap-samples", type=int, default=200)
    ap.add_argument(
        "--stability-seeds",
        type=str,
        default="43,44,45",
        help="Comma-separated extra seeds for best-model retrain variance; 'none' to skip",
    )
    ap.add_argument("--latency-repeats", type=int, default=25)
    ap.add_argument(
        "--write-best-summary",
        action="store_true",
        help="Overwrite/update best_model_summary.json with evaluation metadata and best model pointer.",
    )
    ap.add_argument(
        "--skip-save-joblibs",
        action="store_true",
        help="Only compute metrics JSON without writing zoo/best joblib files.",
    )
    ap.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Parallel workers for RF/ET/LGBM (default 1: lower RAM).",
    )
    ap.add_argument(
        "--max-taxpayers",
        type=int,
        default=None,
        help="Subsample distinct taxpayer_id before eval (same as train script).",
    )
    args = ap.parse_args(argv)

    if not np.isclose(args.train_frac + args.val_frac + args.test_frac, 1.0):
        print("error: train/val/test fractions must sum to 1", file=sys.stderr)
        return 1

    top_ks = tuple(int(x.strip()) for x in args.top_k.split(",") if x.strip())

    df_raw = tt.load_training_table(args.train_table)
    df_raw = tt.subsample_taxpayers_df(df_raw, args.max_taxpayers, args.random_state)
    df_sub, X, y, groups = tt.build_xy_with_frame(df_raw, target=tt.PRIMARY_TARGET)
    if "rule_rank_among_passing" not in df_sub.columns:
        print("error: training table must include rule_rank_among_passing", file=sys.stderr)
        return 1

    if args.split_method == "group_shuffle_sklearn":
        train_m, val_m, test_m = tt.group_train_val_test_masks_sklearn(
            X,
            y,
            groups,
            test_size=args.test_frac,
            val_size_of_remaining=args.val_frac / (args.train_frac + args.val_frac),
            random_state=args.random_state,
        )
    else:
        train_m, val_m, test_m = tt.group_train_val_test_masks(
            groups,
            train_frac=args.train_frac,
            val_frac=args.val_frac,
            test_frac=args.test_frac,
            random_state=args.random_state,
        )

    X_tr, y_tr = X[train_m], y[train_m]
    X_va, y_va = X[val_m], y[val_m]
    X_te, y_te = X[test_m], y[test_m]
    df_te = df_sub[test_m].reset_index(drop=True)

    if X_tr.shape[0] == 0 or X_te.shape[0] == 0:
        print("error: empty train or test after group split", file=sys.stderr)
        return 1

    out_dir = args.artifacts_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    zoo = tt.make_model_zoo(args.random_state, n_jobs=args.n_jobs)
    regression_test: dict[str, Any] = {}
    ranking_test: dict[str, Any] = {}
    fitted_pipes: dict[str, Any] = {}
    best_key: str | None = None
    best_val_mae = float("inf")

    for key, base in zoo.items():
        pipe = tt.build_preprocess_pipeline(base)
        pipe.fit(X_tr, y_tr)
        p_val = pipe.predict(X_va)
        val_mae = float(mean_absolute_error(y_va, p_val))
        if val_mae < best_val_mae:
            best_val_mae = val_mae
            best_key = key
        p_te = pipe.predict(X_te)
        regression_test[key] = _regression_dict(y_te, p_te)
        ranking_test[key] = _ranking_within_taxpayer(df_te, p_te, top_ks)
        fitted_pipes[key] = pipe

    assert best_key is not None

    best_pipe_train_only = fitted_pipes[best_key]
    pred_te_best = best_pipe_train_only.predict(X_te)
    stability_boot = _bootstrap_test_mae(
        y_te,
        pred_te_best,
        df_te["taxpayer_id"].astype(str).to_numpy(),
        n_boot=args.bootstrap_samples,
        random_state=args.random_state + 99,
    )

    raw_seeds = args.stability_seeds.strip()
    if raw_seeds.lower() in ("", "none", "-"):
        seed_extra = []
    else:
        seed_extra = [int(s.strip()) for s in raw_seeds.split(",") if s.strip()]
    stability_seeds = (
        _multi_seed_test_mae(
            best_key=best_key,
            X_tr=X_tr,
            y_tr=y_tr,
            X_te=X_te,
            y_te=y_te,
            seeds=seed_extra,
            n_jobs=args.n_jobs,
        )
        if seed_extra
        else {"skipped": True, "reason": "stability-seeds none or empty"}
    )

    passing_counts = df_sub.groupby("taxpayer_id").size()
    batch_n = int(max(2, np.median(passing_counts.to_numpy())))
    if len(X_te) >= batch_n:
        X_batch = np.ascontiguousarray(X_te[:batch_n], dtype=np.float64)
    else:
        rep = int(np.ceil(batch_n / max(1, len(X_te))))
        X_batch = np.ascontiguousarray(np.tile(X_te, (rep, 1))[:batch_n], dtype=np.float64)

    latency = _latency_benchmark(best_pipe_train_only, X_batch, repeats=args.latency_repeats)

    ts = datetime.now(timezone.utc).replace(microsecond=0)
    table_sha = _sha256_file(args.train_table)

    saved_joblibs: dict[str, str] = {}
    best_digest: str | None = None
    if not args.skip_save_joblibs:
        X_fit = np.vstack([X_tr, X_va])
        y_fit = np.concatenate([y_tr, y_va])
        for key, pipe_template in fitted_pipes.items():
            fname = ZOO_TO_FILENAME.get(key)
            if fname is None:
                continue
            fresh = tt.build_preprocess_pipeline(zoo[key])
            fresh.fit(X_fit, y_fit)
            dest = out_dir / fname
            joblib.dump(fresh, dest)
            saved_joblibs[key] = fname

        best_fresh = tt.build_preprocess_pipeline(zoo[best_key])
        best_fresh.fit(X_fit, y_fit)
        best_path = out_dir / "tax_opt_best_model_v1.joblib"
        joblib.dump(best_fresh, best_path)
        saved_joblibs["best"] = best_path.name
        best_digest = _sha256_file(best_path)

    metrics_path = out_dir / "metrics_v1.json"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": ts.isoformat().replace("+00:00", "Z"),
        "feature_version": args.feature_version,
        "artifact_naming": {
            "models": dict(ZOO_TO_FILENAME),
            "best": "tax_opt_best_model_v1.joblib",
            "feature_pipeline_example": "tax_opt_feature_pipeline_v1.joblib",
        },
        "dataset": {
            "train_table_path": str(args.train_table.resolve().as_posix()),
            "train_table_sha256": table_sha,
            "training_row_count_after_filters": int(len(df_sub)),
            "unique_taxpayers": int(df_sub["taxpayer_id"].nunique()),
        },
        "protocol": {
            "group_split": "taxpayer_id",
            "split_method": args.split_method,
            "train_frac": args.train_frac,
            "val_frac": args.val_frac,
            "test_frac": args.test_frac,
            "primary_random_seed": args.random_state,
            "max_taxpayers_cap": args.max_taxpayers,
            "sklearn_ensemble_n_jobs": args.n_jobs,
            "rows_train": int(train_m.sum()),
            "rows_val": int(val_m.sum()),
            "rows_test": int(test_m.sum()),
        },
        "evaluation_scope": {
            "regression_and_ranking_metrics": (
                "Estimators fit on train partition only; metrics computed on held-out test rows."
            ),
            "saved_joblib_files": (
                "Each zoo model and tax_opt_best_model_v1 refit on train+val before save "
                "(same as train_tax_opt_models_v1.py --promote-best)."
            ),
        },
        "regression_test": regression_test,
        "ranking_test": ranking_test,
        "stability": {
            "bootstrap_test_mae_best_model": stability_boot,
            "multi_seed_variance_best_model": stability_seeds,
        },
        "inference_latency": {
            **latency,
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        },
        "constraint_compliance": {
            "violation_rate": 0.0,
            "note": (
                "Training and evaluation rows are produced by evaluate_search_passing_rows / "
                "build_training_table: only strategies that passed deterministic compliance and "
                "received a tax computation are included. The ML rank API enumerates the same legal "
                "set before scoring—failed candidates never enter the evaluated subset."
            ),
        },
        "selection": {
            "best_zoo_key_by_val_mae": best_key,
            "best_val_mae": best_val_mae,
        },
        "saved_joblibs": saved_joblibs or None,
    }

    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {metrics_path}")

    metrics_digest = _sha256_file(metrics_path)

    if args.write_best_summary:
        summary_path = out_dir / "best_model_summary.json"
        best_fname = saved_joblibs.get("best", "tax_opt_best_model_v1.joblib")
        metric_table = {
            "regression_test": regression_test.get(best_key, {}),
            "ranking_test": ranking_test.get(best_key, {}),
            "bootstrap_mae": stability_boot,
        }
        summary = {
            "schema_version": 1,
            "model_id": f"research_{best_key}_v1",
            "feature_version": args.feature_version,
            "training_timestamp": ts.isoformat().replace("+00:00", "Z"),
            "model_joblib": best_fname,
            "feature_pipeline_joblib": "tax_opt_feature_pipeline_v1.joblib",
            "artifact_sha256": best_digest,
            "synthetic_training_data_disclaimer": (
                "Evaluation-selected model; rules engine remains authoritative."
            ),
            "target_name": tt.PRIMARY_TARGET,
            "inference_matrix_layout": "v1_11_no_savings",
            "metrics_v1_path": metrics_path.name,
            "metrics_v1_sha256": metrics_digest,
            "evaluation_timestamp": ts.isoformat().replace("+00:00", "Z"),
            "dataset_sha256_training_table": table_sha,
            "training_row_count": int(len(df_sub)),
            "evaluation_random_seeds": [args.random_state] + seed_extra,
            "metric_table_test": metric_table,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"wrote {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
