#!/usr/bin/env python3
"""Compare ranking/adoption baselines vs LightGBM + LambdaMART on held-out profiles."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRanker
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, ndcg_score, roc_auc_score
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models" / "personalized-recommendation"))

from features.pair_features import build_pair_row, pair_column_names  # noqa: E402
from ranking.relevance import relevance_from_evaluation  # noqa: E402
from strategy_gen.catalog import load_strategy_catalog  # noqa: E402
from strategy_gen.evaluator import evaluate_strategy  # noqa: E402


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


def build_dataset(df: pd.DataFrame, catalog, user_num: list[str], user_cat: list[str]):
    pair_num, pair_cat = pair_column_names(user_num, user_cat)
    rank_rows: list[dict] = []
    rank_y: list[int] = []
    groups: list[int] = []
    adopt_x: list[dict] = []
    adopt_y: list[list[int]] = []
    rule_scores: list[float] = []
    feas_scores: list[float] = []
    n_s = len(catalog.strategies)

    for _, r in df.iterrows():
        ctx = row_to_eval_context(r)
        udict = row_to_user_dict(r, user_num, user_cat)
        y_row: list[int] = []
        for s in catalog.strategies:
            ev = evaluate_strategy(s, ctx)
            rel = relevance_from_evaluation(ev, priority_hint=s.priority_hint)
            rank_rows.append(build_pair_row(udict, s, user_num_keys=user_num, user_cat_keys=user_cat))
            rank_y.append(rel)
            y_row.append(1 if ev.is_eligible else 0)
            rule_scores.append(-float(s.priority_hint))
            feas_scores.append(float(ev.feasibility_score) if ev.is_eligible else 0.0)
        groups.append(n_s)
        adopt_x.append(udict)
        adopt_y.append(y_row)

    x_rank = pd.DataFrame(rank_rows, columns=[*pair_num, *pair_cat])
    y_rank = np.asarray(rank_y, dtype=np.int32)
    group = np.asarray(groups, dtype=np.int32)
    x_adopt = pd.DataFrame(adopt_x, columns=[*user_num, *user_cat])
    y_adopt = np.asarray(adopt_y, dtype=np.int32)
    return x_rank, y_rank, group, x_adopt, y_adopt, np.asarray(rule_scores), np.asarray(feas_scores), pair_num, pair_cat


def _pair_pipeline(estimator, pair_num: list[str], pair_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), pair_cat)],
        remainder="passthrough",
    )
    return Pipeline([("prep", pre), ("model", estimator)])


def _user_pipeline(estimator, user_num: list[str], user_cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), user_cat)],
        remainder="passthrough",
    )
    return Pipeline([("prep", pre), ("model", estimator)])


def _scores_from_user_classifier(model, x_adopt: pd.DataFrame, n_strategies: int) -> np.ndarray:
    proba = model.predict_proba(x_adopt)
    if not isinstance(proba, list):
        raise TypeError("Expected list of per-strategy probability arrays")
    cols = [p[:, 1] for p in proba]
    return np.repeat(np.column_stack(cols), n_strategies, axis=0).reshape(-1)


def _ranking_metrics(y_true_groups: list[np.ndarray], y_score_groups: list[np.ndarray]) -> dict[str, float]:
    ndcg5: list[float] = []
    ndcg10: list[float] = []
    map5: list[float] = []
    mrr: list[float] = []
    hit1: list[float] = []
    p5: list[float] = []

    for y_true, y_score in zip(y_true_groups, y_score_groups):
        y_true = np.asarray(y_true, dtype=float)
        y_score = np.asarray(y_score, dtype=float)
        if y_true.sum() <= 0:
            continue
        k5 = min(5, len(y_true))
        k10 = min(10, len(y_true))
        ndcg5.append(float(ndcg_score(y_true.reshape(1, -1), y_score.reshape(1, -1), k=k5)))
        ndcg10.append(float(ndcg_score(y_true.reshape(1, -1), y_score.reshape(1, -1), k=k10)))
        order = np.argsort(-y_score)
        rel_sorted = y_true[order]
        gains = rel_sorted[:k5]
        denom = np.sum((2.0 ** rel_sorted[:k5] - 1.0) / np.log2(np.arange(2, k5 + 2)))
        if denom > 0:
            map5.append(float(np.sum(gains > 0) / max(1, np.sum(rel_sorted > 0))))
        else:
            map5.append(0.0)
        top_rel = rel_sorted[0] if len(rel_sorted) else 0.0
        mrr.append(1.0 if top_rel > 0 else 0.0)
        hit1.append(1.0 if top_rel > 0 else 0.0)
        p5.append(float(np.mean((rel_sorted[:k5] > 0).astype(float))))

    def mean(xs: list[float]) -> float:
        return float(np.mean(xs)) if xs else 0.0

    return {
        "ndcg@5": mean(ndcg5),
        "ndcg@10": mean(ndcg10),
        "map@5": mean(map5),
        "mrr": mean(mrr),
        "hit@1": mean(hit1),
        "precision@5": mean(p5),
    }


def _group_scores(flat_scores: np.ndarray, groups: np.ndarray) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    i = 0
    for g in groups:
        out.append(flat_scores[i : i + g])
        i += g
    return out


def _group_labels(flat_labels: np.ndarray, groups: np.ndarray) -> list[np.ndarray]:
    return _group_scores(flat_labels, groups)


def _adoption_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "roc_auc_micro": float(roc_auc_score(y_true, y_prob, average="micro")),
        "map_micro": float(average_precision_score(y_true, y_prob, average="micro")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--user-meta", type=Path, required=True)
    ap.add_argument("--train-limit", type=int, default=8000)
    ap.add_argument("--eval-limit", type=int, default=1500)
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    user_meta = json.loads(args.user_meta.read_text(encoding="utf-8"))
    user_num = [str(x) for x in user_meta["num_features"]]
    user_cat = [str(x) for x in user_meta["cat_features"]]
    catalog = load_strategy_catalog(str(args.catalog))
    n_s = len(catalog.strategies)

    df = pd.read_csv(args.csv)
    train_df = df[df["split"].astype(str).str.lower() == "train"].head(args.train_limit).reset_index(drop=True)
    eval_df = df[df["split"].astype(str).str.lower() == "val"].head(args.eval_limit).reset_index(drop=True)

    x_rank_tr, y_rank_tr, group_tr, x_adopt_tr, y_adopt_tr, _, _, pair_num, pair_cat = build_dataset(
        train_df, catalog, user_num, user_cat
    )
    x_rank_ev, y_rank_ev, group_ev, x_adopt_ev, y_adopt_ev, rule_ev, feas_ev, _, _ = build_dataset(
        eval_df, catalog, user_num, user_cat
    )

    y_groups = _group_labels(y_rank_ev, group_ev)
    results: list[dict] = []

    def add_result(name: str, flat_scores: np.ndarray, adopt_probs: np.ndarray | None = None):
        score_groups = _group_scores(flat_scores, group_ev)
        row = {"model": name, **_ranking_metrics(y_groups, score_groups)}
        if adopt_probs is not None:
            row.update(_adoption_metrics(y_adopt_ev, adopt_probs))
        results.append(row)

    add_result("Catalog priority (rule baseline)", rule_ev)

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
    add_result("LightGBM + LambdaMART (selected)", ranker.predict(x_rank_ev))

    hgb = _pair_pipeline(
        HistGradientBoostingRegressor(random_state=42),
        pair_num,
        pair_cat,
    )
    hgb.fit(x_rank_tr, y_rank_tr)
    add_result("HistGradientBoosting (pair regressor)", hgb.predict(x_rank_ev))

    rf = _pair_pipeline(
        RandomForestRegressor(n_estimators=120, random_state=42, n_jobs=-1),
        pair_num,
        pair_cat,
    )
    rf.fit(x_rank_tr, y_rank_tr)
    add_result("Random Forest (pair regressor)", rf.predict(x_rank_ev))

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
    flat = np.repeat(prob_cols, n_s, axis=0).reshape(-1)
    add_result("LightGBM multi-label classifier", flat, prob_cols)

    add_result("Feasibility-only heuristic", feas_ev)

    table = pd.DataFrame(results)
    table = table.sort_values("ndcg@5", ascending=False).reset_index(drop=True)
    print(table.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(table.to_json(orient="records", indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
