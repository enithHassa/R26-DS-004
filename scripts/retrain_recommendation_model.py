"""Retrain the strategy-matcher MultiOutputClassifier with 10 strategies (S001-S010).

Generates rule-based adoption labels from the corrected synthetic CSV,
trains a LightGBM MultiOutputClassifier pipeline, and saves artifacts to
backend/comp-personalized-recommendation/app/artifacts/.

Usage:
    python scripts/retrain_recommendation_model.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = ROOT / "models" / "personalized-recommendation"
ARTIFACTS_DIR = ROOT / "backend" / "comp-personalized-recommendation" / "app" / "artifacts"
CSV_PATH = ROOT / "data" / "synthetic" / "profiles_corrected_tax (1).csv"
CATALOG_PATH = ML_ROOT / "rules" / "strategy_catalog.yaml"

sys.path.insert(0, str(ML_ROOT))
from strategy_gen.catalog import load_strategy_catalog  # type: ignore[import-not-found]
from strategy_gen.evaluator import evaluate_strategy  # type: ignore[import-not-found]


NUM_FEATURES = [
    "dependents", "years_employed",
    "gross_monthly_income_lkr", "monthly_expenses_lkr",
    "monthly_debt_service_lkr", "liquid_savings_lkr",
    "existing_investments_lkr", "total_debt_lkr",
    "epf_balance_lkr", "etf_balance_lkr",
    "life_insurance_premium_annual_lkr", "home_loan_interest_annual_lkr",
    "donations_annual_lkr",
    "gross_annual_taxable_income_lkr", "baseline_tax_liability_lkr",
    "effective_tax_rate", "disposable_income_monthly_lkr",
    "savings_rate", "debt_to_income",
    "expense_ratio", "debt_service_ratio", "liquidity_months",
    "src_employment_share", "src_business_share", "src_dividend_share",
    "src_interest_share", "src_rental_share", "src_other_share",
]
CAT_FEATURES = ["gender", "marital_status", "occupation", "risk_tolerance", "archetype", "age_band", "province"]


def _col(df: pd.DataFrame, src: str, alias: str | None = None) -> pd.Series:
    if src in df.columns:
        return df[src]
    if alias and alias in df.columns:
        return df[alias]
    return pd.Series(0.0, index=df.index)


def build_feature_df(df: pd.DataFrame) -> pd.DataFrame:
    income_m = _col(df, "gross_monthly_income_lkr")
    exp_m = _col(df, "monthly_expenses_lkr")
    debt_m = _col(df, "monthly_debt_service_lkr")
    liq = _col(df, "liquid_savings_lkr")

    X = pd.DataFrame(index=df.index)
    for f in NUM_FEATURES:
        aliases = {
            "gross_annual_taxable_income_lkr": "gross_annual_taxable_income_lkr",
            "baseline_tax_liability_lkr": "baseline_tax_liability_lkr_corrected",
            "effective_tax_rate": "effective_tax_rate_corrected",
            "disposable_income_monthly_lkr": "disposable_income_monthly_lkr_corrected",
            "savings_rate": "savings_rate_corrected",
        }
        X[f] = _col(df, f, aliases.get(f)).fillna(0.0).astype(float)

    X["expense_ratio"] = np.where(income_m > 0, exp_m / income_m, 0.0)
    X["debt_service_ratio"] = np.where(income_m > 0, debt_m / income_m, 0.0)
    X["liquidity_months"] = np.where(exp_m > 0, liq / exp_m, 0.0)
    for sh in ["src_employment_share", "src_business_share", "src_dividend_share",
               "src_interest_share", "src_rental_share", "src_other_share"]:
        X[sh] = 0.0

    for f in CAT_FEATURES:
        if f in df.columns:
            X[f] = df[f].fillna("unknown").astype(str)
        else:
            X[f] = "unknown"

    return X


def build_ctx(row: pd.Series) -> dict:
    income_m = float(row.get("gross_monthly_income_lkr", 0) or 0)
    exp_m = float(row.get("monthly_expenses_lkr", 0) or 0)
    liq = float(row.get("liquid_savings_lkr", 0) or 0)
    return {
        "annual_income": float(row.get("gross_annual_taxable_income_lkr", income_m * 12) or 0),
        "annual_tax_before_strategy": float(row.get("baseline_tax_liability_lkr_corrected", 0) or 0),
        "gross_monthly_income_lkr": income_m,
        "monthly_expenses_lkr": exp_m,
        "monthly_debt_service_lkr": float(row.get("monthly_debt_service_lkr", 0) or 0),
        "liquid_savings_lkr": liq,
        "total_debt_lkr": float(row.get("total_debt_lkr", 0) or 0),
        "epf_balance_lkr": float(row.get("epf_balance_lkr", 0) or 0),
        "etf_balance_lkr": float(row.get("etf_balance_lkr", 0) or 0),
        "debt_to_income": float(row.get("debt_to_income", 0) or 0),
        "savings_rate": float(row.get("savings_rate_corrected", row.get("savings_rate", 0)) or 0),
        "occupation": str(row.get("occupation", "employee")),
        "risk_tolerance": str(row.get("risk_tolerance", "medium")),
        "has_health_insurance": bool(row.get("health_insurance", False)),
        "life_insurance_premium_annual_lkr": float(row.get("life_insurance_premium_annual_lkr", 0) or 0),
        "health_insurance_premium_annual_lkr": 15000.0 if bool(row.get("health_insurance", False)) else 0.0,
        "home_loan_interest_annual_lkr": float(row.get("home_loan_interest_annual_lkr", 0) or 0),
        "donations_annual_lkr": float(row.get("donations_annual_lkr", 0) or 0),
        "rent_paid_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
        "years_employed": int(row.get("years_employed", 0) or 0),
        "age_band": str(row.get("age_band", "30-34")),
    }


def generate_labels(df: pd.DataFrame, strategy_ids: list[str]) -> pd.DataFrame:
    catalog = load_strategy_catalog(str(CATALOG_PATH))
    sid_to_def = {s.strategy_id: s for s in catalog.strategies}
    labels = pd.DataFrame(0, index=df.index, columns=strategy_ids)
    for idx, row in df.iterrows():
        ctx = build_ctx(row)
        for sid in strategy_ids:
            if sid not in sid_to_def:
                continue
            result = evaluate_strategy(sid_to_def[sid], ctx)
            labels.at[idx, sid] = 1 if result.is_eligible else 0
    return labels


def main() -> None:
    print("Loading synthetic data...")
    df = pd.read_csv(CSV_PATH)
    print(f"  {len(df)} rows loaded.")

    catalog = load_strategy_catalog(str(CATALOG_PATH))
    strategy_ids = [s.strategy_id for s in sorted(catalog.strategies, key=lambda x: x.priority_hint)]
    print(f"  Strategies ({len(strategy_ids)}): {strategy_ids}")

    print("Building features...")
    X = build_feature_df(df)

    print("Generating labels via rules engine (this may take a minute)...")
    Y = generate_labels(df, strategy_ids)
    print("  Label distribution:")
    for sid in strategy_ids:
        pct = Y[sid].mean() * 100
        print(f"    {sid}: {pct:.1f}% eligible")

    prep = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUM_FEATURES),
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT_FEATURES),
        ]
    )
    base_clf = LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    clf = MultiOutputClassifier(base_clf, n_jobs=-1)
    pipe = Pipeline([("prep", prep), ("clf", clf)])

    print("Training MultiOutputClassifier...")
    pipe.fit(X, Y)
    print("  Training done.")

    print(f"Saving artifacts to {ARTIFACTS_DIR}...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, ARTIFACTS_DIR / "strategy_matcher_model.joblib")
    joblib.dump(strategy_ids, ARTIFACTS_DIR / "strategy_ids.joblib")
    (ARTIFACTS_DIR / "feature_meta.json").write_text(
        json.dumps({"num_features": NUM_FEATURES, "cat_features": CAT_FEATURES}, indent=2),
        encoding="utf-8",
    )
    (ARTIFACTS_DIR / "model_version.txt").write_text("local-retrained-v2", encoding="utf-8")
    print("  Done. Artifacts saved.")
    print("\nVerifying saved strategy_ids:")
    loaded = joblib.load(ARTIFACTS_DIR / "strategy_ids.joblib")
    print(f"  {loaded}")


if __name__ == "__main__":
    main()
