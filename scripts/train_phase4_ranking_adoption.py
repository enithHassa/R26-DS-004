#!/usr/bin/env python3
"""Train Phase 4 artifacts: user-level adoption (multi-label) + pair-wise LambdaMART ranker.

Usage (from repo root):
  .venv-backend/bin/python scripts/train_phase4_ranking_adoption.py \\
    --csv data/synthetic/profiles_corrected_tax\\ \\(1\\).csv \\
    --catalog models/personalized-recommendation/rules/strategy_catalog.yaml \\
    --out-dir models/personalized-recommendation/artifacts \\
    --legacy-matcher models/personalized-recommendation/artifacts/strategy_matcher_model.joblib

``--legacy-matcher`` is optional; if provided, adoption labels are distilled from
matcher probabilities (>0.5 positive). Otherwise labels are eligibility bits.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models" / "personalized-recommendation"))

from features.pair_features import (  # noqa: E402
    build_pair_row,
    pair_column_names,
)
from ranking.relevance import relevance_from_evaluation  # noqa: E402
from strategy_gen.catalog import load_strategy_catalog  # noqa: E402
from strategy_gen.evaluator import evaluate_strategy  # noqa: E402

try:
    from lightgbm import LGBMClassifier, LGBMRanker
except ImportError as e:
    raise SystemExit("Install lightgbm: pip install lightgbm") from e


USER_META_NAME = "user_feature_meta.json"
PAIR_META_NAME = "pair_feature_meta.json"
MANIFEST_NAME = "phase4_manifest.json"
ADOPTION_NAME = "phase4_adoption_model.joblib"
RANKER_NAME = "phase4_lambdarank_model.joblib"
STRATEGY_IDS_NAME = "strategy_ids.joblib"
WEIGHTS_NAME = "scoring_weights.yaml"


def _boolish(x) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    return str(x).strip().lower() in {"1", "true", "t", "yes", "y"}


def _income_sources_list(raw):
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except (SyntaxError, ValueError):
            return []


def row_to_eval_context(r: pd.Series) -> dict:
    hi = _boolish(r["health_insurance"])
    return {
        "annual_income": float(r["gross_annual_taxable_income_lkr"]),
        "annual_tax_before_strategy": float(
            r.get("baseline_tax_liability_lkr_corrected", r["baseline_tax_liability_lkr"])
        ),
        "gross_monthly_income_lkr": float(r["gross_monthly_income_lkr"]),
        "monthly_expenses_lkr": float(r["monthly_expenses_lkr"]),
        "monthly_debt_service_lkr": float(r["monthly_debt_service_lkr"]),
        "liquid_savings_lkr": float(r["liquid_savings_lkr"]),
        "total_debt_lkr": float(r["total_debt_lkr"]),
        "debt_to_income": float(r["debt_to_income"]),
        "savings_rate": float(r.get("savings_rate_corrected", r["savings_rate"])),
        "occupation": str(r["occupation"]),
        "risk_tolerance": str(r["risk_tolerance"]),
        "has_health_insurance": hi,
        "life_insurance_premium_annual_lkr": float(r["life_insurance_premium_annual_lkr"]),
        "health_insurance_premium_annual_lkr": 15000.0 if hi else 0.0,
        "home_loan_interest_annual_lkr": float(r["home_loan_interest_annual_lkr"]),
        "donations_annual_lkr": float(r["donations_annual_lkr"]),
        "rent_paid_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
        "epf_balance_lkr": float(r["epf_balance_lkr"]),
        "years_employed": int(r["years_employed"]),
        "age_band": str(r["age_band"]),
    }


def row_to_user_dict(r: pd.Series, user_num: list[str], user_cat: list[str]) -> dict:
    gmi = float(r["gross_monthly_income_lkr"])
    exp = float(r["monthly_expenses_lkr"])
    debt_m = float(r["monthly_debt_service_lkr"])
    liq = float(r["liquid_savings_lkr"])
    taxable = float(r["gross_annual_taxable_income_lkr"])
    baseline = float(r.get("baseline_tax_liability_lkr_corrected", r["baseline_tax_liability_lkr"]))
    eff = float(r.get("effective_tax_rate_corrected", r["effective_tax_rate"]))
    disp = float(r.get("disposable_income_monthly_lkr_corrected", r["disposable_income_monthly_lkr"]))
    sav = float(r.get("savings_rate_corrected", r["savings_rate"]))
    src_totals = {k: 0.0 for k in ["employment", "business", "dividend", "interest", "rental", "other"]}
    total = 0.0
    for it in _income_sources_list(r.get("income_sources_json")):
        kind = str(it.get("kind", "other")).lower()
        amt = float(it.get("monthly_amount", 0.0) or 0.0)
        if kind not in src_totals:
            kind = "other"
        src_totals[kind] += amt
        total += amt
    shares = {f"src_{k}_share": (v / total if total > 0 else 0.0) for k, v in src_totals.items()}
    row = {
        "dependents": float(r["dependents"]),
        "years_employed": float(r["years_employed"]),
        "gross_monthly_income_lkr": gmi,
        "monthly_expenses_lkr": exp,
        "monthly_debt_service_lkr": debt_m,
        "liquid_savings_lkr": liq,
        "existing_investments_lkr": float(r["existing_investments_lkr"]),
        "total_debt_lkr": float(r["total_debt_lkr"]),
        "epf_balance_lkr": float(r["epf_balance_lkr"]),
        "etf_balance_lkr": float(r["etf_balance_lkr"]),
        "life_insurance_premium_annual_lkr": float(r["life_insurance_premium_annual_lkr"]),
        "home_loan_interest_annual_lkr": float(r["home_loan_interest_annual_lkr"]),
        "donations_annual_lkr": float(r["donations_annual_lkr"]),
        "gross_annual_taxable_income_lkr": taxable,
        "baseline_tax_liability_lkr": baseline,
        "effective_tax_rate": eff,
        "disposable_income_monthly_lkr": disp,
        "savings_rate": sav,
        "debt_to_income": float(r["debt_to_income"]),
        "expense_ratio": exp / gmi if gmi > 0 else 0.0,
        "debt_service_ratio": debt_m / gmi if gmi > 0 else 0.0,
        "liquidity_months": liq / exp if exp > 0 else 0.0,
        **shares,
        "gender": str(r["gender"]),
        "marital_status": str(r["marital_status"]),
        "occupation": str(r["occupation"]),
        "risk_tolerance": str(r["risk_tolerance"]),
        "archetype": str(r["archetype"]),
        "age_band": str(r["age_band"]),
        "province": str(r["province"]),
    }
    out = {}
    for k in user_num:
        out[k] = float(row.get(k, 0.0) or 0.0)
    for k in user_cat:
        v = row.get(k, "unknown")
        out[k] = "unknown" if v is None else str(v)
    return out


def _make_user_pipeline(user_num: list[str], user_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), user_cat),
        ],
        remainder="passthrough",
    )
    base = LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=40,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=42,
        verbose=-1,
    )
    return Pipeline(
        [
            ("prep", pre),
            ("clf", MultiOutputClassifier(base)),
        ]
    )


def _make_ranker_pipeline(pair_num: list[str], pair_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), pair_cat),
        ],
        remainder="passthrough",
    )
    ranker = LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbose=-1,
    )
    return Pipeline([("prep", pre), ("rank", ranker)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--legacy-matcher", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0, help="Max training rows (0=all)")
    ap.add_argument("--test-split", type=float, default=0.0, help="Holdout fraction (0=train on all)")
    args = ap.parse_args()

    user_meta_path = args.out_dir / USER_META_NAME
    if user_meta_path.exists():
        user_meta = json.loads(user_meta_path.read_text(encoding="utf-8"))
    else:
        # default column layout matches shipped feature_meta.json
        user_meta = {
            "num_features": [
                "dependents",
                "years_employed",
                "gross_monthly_income_lkr",
                "monthly_expenses_lkr",
                "monthly_debt_service_lkr",
                "liquid_savings_lkr",
                "existing_investments_lkr",
                "total_debt_lkr",
                "epf_balance_lkr",
                "etf_balance_lkr",
                "life_insurance_premium_annual_lkr",
                "home_loan_interest_annual_lkr",
                "donations_annual_lkr",
                "gross_annual_taxable_income_lkr",
                "baseline_tax_liability_lkr",
                "effective_tax_rate",
                "disposable_income_monthly_lkr",
                "savings_rate",
                "debt_to_income",
                "expense_ratio",
                "debt_service_ratio",
                "liquidity_months",
                "src_employment_share",
                "src_business_share",
                "src_dividend_share",
                "src_interest_share",
                "src_rental_share",
                "src_other_share",
            ],
            "cat_features": [
                "gender",
                "marital_status",
                "occupation",
                "risk_tolerance",
                "archetype",
                "age_band",
                "province",
            ],
        }

    user_num = [str(x) for x in user_meta["num_features"]]
    user_cat = [str(x) for x in user_meta["cat_features"]]
    pair_num, pair_cat = pair_column_names(user_num, user_cat)

    catalog = load_strategy_catalog(str(args.catalog))
    strat_ids = [s.strategy_id for s in catalog.strategies]
    n_s = len(strat_ids)

    df = pd.read_csv(args.csv)
    if args.limit and args.limit > 0:
        df = df.iloc[: args.limit].copy()
    if "split" in df.columns:
        df = df[df["split"].astype(str).str.lower() != "test"].reset_index(drop=True)

    legacy = None
    if args.legacy_matcher and args.legacy_matcher.exists():
        legacy = joblib.load(args.legacy_matcher)

    rank_rows: list[dict] = []
    rank_y: list[int] = []
    groups: list[int] = []

    adopt_X: list[dict] = []
    adopt_Y: list[list[int]] = []

    for _, r in df.iterrows():
        ctx = row_to_eval_context(r)
        udict = row_to_user_dict(r, user_num, user_cat)
        X_u = pd.DataFrame([udict], columns=[*user_num, *user_cat])

        matcher_probs: list[float] | None = None
        if legacy is not None:
            try:
                pr = legacy.predict_proba(X_u)
                if isinstance(pr, list):
                    matcher_probs = [float(p[0, 1]) for p in pr]
                else:
                    matcher_probs = None
            except Exception:
                matcher_probs = None

        y_row = []
        for j, s in enumerate(catalog.strategies):
            ev = evaluate_strategy(s, ctx)
            rel = relevance_from_evaluation(ev, priority_hint=s.priority_hint)
            prow = build_pair_row(udict, s, user_num_keys=user_num, user_cat_keys=user_cat)
            rank_rows.append(prow)
            rank_y.append(rel)
            if matcher_probs is not None and j < len(matcher_probs):
                y_row.append(1 if matcher_probs[j] >= 0.5 else 0)
            else:
                y_row.append(1 if ev.is_eligible else 0)
        groups.append(n_s)
        adopt_X.append(udict)
        adopt_Y.append(y_row)

    X_rank = pd.DataFrame(rank_rows, columns=[*pair_num, *pair_cat])
    y_rank = np.asarray(rank_y, dtype=np.int32)
    group = np.asarray(groups, dtype=np.int32)

    X_adopt = pd.DataFrame(adopt_X, columns=[*user_num, *user_cat])
    Y_adopt = np.asarray(adopt_Y, dtype=np.int32)

    ranker = _make_ranker_pipeline(pair_num, pair_cat)
    ranker.fit(X_rank, y_rank, rank__group=group)

    adoption = _make_user_pipeline(user_num, user_cat)
    adoption.fit(X_adopt, Y_adopt)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.joinpath(USER_META_NAME).write_text(
        json.dumps({"num_features": user_num, "cat_features": user_cat}, indent=2),
        encoding="utf-8",
    )
    args.out_dir.joinpath(PAIR_META_NAME).write_text(
        json.dumps({"user_num_features": user_num, "user_cat_features": user_cat}, indent=2),
        encoding="utf-8",
    )
    joblib.dump(adoption, args.out_dir / ADOPTION_NAME)
    joblib.dump(ranker, args.out_dir / RANKER_NAME)
    joblib.dump(strat_ids, args.out_dir / STRATEGY_IDS_NAME)

    weights_src = ROOT / "models/personalized-recommendation/ranking/scoring_weights.yaml"
    if weights_src.exists():
        (args.out_dir / WEIGHTS_NAME).write_text(weights_src.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = {
        "schema_version": "phase4_v1",
        "pair_feature_meta": PAIR_META_NAME,
        "user_feature_meta": USER_META_NAME,
        "adoption_model": ADOPTION_NAME,
        "ranker_model": RANKER_NAME,
        "strategy_ids": STRATEGY_IDS_NAME,
        "scoring_weights": WEIGHTS_NAME,
    }
    args.out_dir.joinpath(MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    args.out_dir.joinpath("model_version.txt").write_text("phase4-lambdarank-adoption-v1\n", encoding="utf-8")

    print("Wrote Phase 4 artifacts to", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
