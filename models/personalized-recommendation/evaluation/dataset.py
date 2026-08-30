"""Build evaluation tensors from synthetic profile CSVs (Phase 6)."""

from __future__ import annotations

import ast
import json
from typing import Any

import numpy as np
import pandas as pd

from features.pair_features import build_pair_row, pair_column_names
from ranking.relevance import relevance_from_evaluation
from strategy_gen.catalog import StrategyCatalog
from strategy_gen.evaluator import evaluate_strategy


def boolish(x: object) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    return str(x).strip().lower() in {"1", "true", "t", "yes", "y"}


def income_sources_list(raw: object) -> list[dict[str, Any]]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            val = ast.literal_eval(s)
            return val if isinstance(val, list) else []
        except (SyntaxError, ValueError):
            return []


def row_to_eval_context(r: pd.Series) -> dict[str, Any]:
    hi = boolish(r["health_insurance"])
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


def row_to_user_dict(r: pd.Series, user_num: list[str], user_cat: list[str]) -> dict[str, Any]:
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
    for it in income_sources_list(r.get("income_sources_json")):
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
    out: dict[str, Any] = {}
    for k in user_num:
        out[k] = float(row.get(k, 0.0) or 0.0)
    for k in user_cat:
        v = row.get(k, "unknown")
        out[k] = "unknown" if v is None else str(v)
    return out


def build_eval_dataset(
    df: pd.DataFrame,
    catalog: StrategyCatalog,
    user_num: list[str],
    user_cat: list[str],
) -> dict[str, Any]:
    """Materialize ranking/adoption tensors and per-profile segment labels."""
    pair_num, pair_cat = pair_column_names(user_num, user_cat)
    rank_rows: list[dict[str, Any]] = []
    rank_y: list[int] = []
    groups: list[int] = []
    adopt_x: list[dict[str, Any]] = []
    adopt_y: list[list[int]] = []
    rule_scores: list[float] = []
    feas_scores: list[float] = []
    occupations: list[str] = []
    incomes: list[float] = []
    n_s = len(catalog.strategies)

    for _, r in df.iterrows():
        ctx = row_to_eval_context(r)
        udict = row_to_user_dict(r, user_num, user_cat)
        occupations.append(str(r["occupation"]))
        incomes.append(float(r["gross_annual_taxable_income_lkr"]))
        y_row: list[int] = []
        for s in catalog.strategies:
            ev = evaluate_strategy(s, ctx)
            rel = relevance_from_evaluation(ev, priority_hint=s.priority_hint)
            rank_rows.append(
                build_pair_row(udict, s, user_num_keys=user_num, user_cat_keys=user_cat)
            )
            rank_y.append(rel)
            y_row.append(1 if ev.is_eligible else 0)
            rule_scores.append(-float(s.priority_hint))
            feas_scores.append(float(ev.feasibility_score) if ev.is_eligible else 0.0)
        groups.append(n_s)
        adopt_x.append(udict)
        adopt_y.append(y_row)

    return {
        "x_rank": pd.DataFrame(rank_rows, columns=[*pair_num, *pair_cat]),
        "y_rank": np.asarray(rank_y, dtype=np.int32),
        "group": np.asarray(groups, dtype=np.int32),
        "x_adopt": pd.DataFrame(adopt_x, columns=[*user_num, *user_cat]),
        "y_adopt": np.asarray(adopt_y, dtype=np.int32),
        "rule_scores": np.asarray(rule_scores, dtype=np.float64),
        "feas_scores": np.asarray(feas_scores, dtype=np.float64),
        "pair_num": pair_num,
        "pair_cat": pair_cat,
        "occupations": occupations,
        "incomes": incomes,
        "n_strategies": n_s,
    }


__all__ = [
    "build_eval_dataset",
    "boolish",
    "income_sources_list",
    "row_to_eval_context",
    "row_to_user_dict",
]
