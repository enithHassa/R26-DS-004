"""Runtime recommendation generation using trained artifacts + rule feasibility."""

from __future__ import annotations

import sys
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM
from app.schemas.recommendation import (
    RecommendationExplanation,
    RecommendationItem,
    RecommendationResponse,
    ScoreBreakdown,
)
from app.schemas.strategy import Strategy, StrategyCategory
from app.services.inference_assets import load_inference_artifacts
from app.services.profile_service import ProfileNotFoundError, compute_derived_features, get_profile


class RecommendationGenerationError(RuntimeError):
    """Raised when recommendation generation fails."""


def _import_strategy_eval() -> Any:
    """Import strategy evaluator package from hyphenated ML path."""
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from strategy_gen.catalog import load_strategy_catalog  # type: ignore[import-not-found]
    from strategy_gen.evaluator import evaluate_strategy  # type: ignore[import-not-found]

    return load_strategy_catalog, evaluate_strategy


def _strategy_catalog_path() -> Path:
    return component_settings.COMP_RECOMMENDATION_RULES_PATH.parent / "strategy_catalog.yaml"


def _behavior_segment(ctx: dict[str, Any]) -> str:
    dti = float(ctx.get("debt_to_income", 0.0))
    sr = float(ctx.get("savings_rate", 0.0))
    rt = str(ctx.get("risk_tolerance", "medium"))
    if dti > 0.65 or sr < 0.05:
        return "cashflow_stressed"
    if sr > 0.25 and rt == "high":
        return "growth_oriented"
    if sr > 0.15:
        return "balanced_planner"
    return "conservative_or_uncertain"


def _build_feature_context(
    profile: FinancialProfileORM,
    *,
    num_features: list[str],
    cat_features: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    derived = compute_derived_features(profile)

    ctx: dict[str, Any] = {
        # raw profile
        "annual_income": float(derived.gross_annual_taxable_income),
        "annual_tax_before_strategy": float(derived.baseline_tax_liability_annual),
        "gross_monthly_income_lkr": float(profile.gross_monthly_income),
        "monthly_expenses_lkr": float(profile.monthly_expenses),
        "monthly_debt_service_lkr": float(profile.monthly_debt_service),
        "liquid_savings_lkr": float(profile.liquid_savings),
        "existing_investments_lkr": float(profile.existing_investments),
        "total_debt_lkr": float(profile.total_debt),
        "epf_balance_lkr": float(profile.epf_balance),
        "etf_balance_lkr": float(profile.etf_balance),
        "debt_to_income": float(derived.debt_to_income),
        "savings_rate": float(derived.savings_rate),
        "occupation": str(profile.occupation),
        "risk_tolerance": str(profile.risk_tolerance),
        "has_health_insurance": bool(profile.health_insurance),
        "health_insurance": bool(profile.health_insurance),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "health_insurance_premium_annual_lkr": 15_000.0 if profile.health_insurance else 0.0,
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "rent_paid_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
        "years_employed": int(profile.years_employed),
        "dependents": int(profile.dependents),
        "gender": str(profile.gender),
        "district": str(profile.district),
        "marital_status": str(profile.marital_status),
        "age_years": int(derived.age_years),
        "effective_tax_rate": float(derived.effective_tax_rate),
        "gross_annual_taxable_income_lkr": float(derived.gross_annual_taxable_income),
        "baseline_tax_liability_lkr": float(derived.baseline_tax_liability_annual),
        "disposable_income_monthly_lkr": float(derived.disposable_income_monthly),
        # Corrected-tax aliases to match updated synthetic datasets that use
        # *_corrected columns.
        "baseline_tax_liability_lkr_corrected": float(derived.baseline_tax_liability_annual),
        "effective_tax_rate_corrected": float(derived.effective_tax_rate),
        "disposable_income_monthly_lkr_corrected": float(derived.disposable_income_monthly),
        "savings_rate_corrected": float(derived.savings_rate),
    }
    age = int(derived.age_years)
    if age <= 24:
        age_band = "18-24"
    elif age <= 29:
        age_band = "25-29"
    elif age <= 34:
        age_band = "30-34"
    elif age <= 39:
        age_band = "35-39"
    elif age <= 44:
        age_band = "40-44"
    elif age <= 49:
        age_band = "45-49"
    elif age <= 54:
        age_band = "50-54"
    elif age <= 59:
        age_band = "55-59"
    elif age <= 64:
        age_band = "60-64"
    elif age <= 70:
        age_band = "65-70"
    else:
        age_band = "70+"
    ctx["age_band"] = age_band
    # Updated synthetic dataset includes generalized location.
    ctx["province"] = "Unknown"

    # parse income_sources shares
    src = profile.income_sources or []
    src_totals = {
        "employment": 0.0,
        "business": 0.0,
        "dividend": 0.0,
        "interest": 0.0,
        "rental": 0.0,
        "other": 0.0,
    }
    total = 0.0
    for it in src:
        kind = str(it.get("kind", "other")).lower()
        amt = float(it.get("monthly_amount", 0.0) or 0.0)
        if kind not in src_totals:
            kind = "other"
        src_totals[kind] += amt
        total += amt
    for k, v in src_totals.items():
        ctx[f"src_{k}_share"] = (v / total) if total > 0 else 0.0

    # additional engineered features used during training
    income_m = float(profile.gross_monthly_income)
    exp_m = float(profile.monthly_expenses)
    debt_m = float(profile.monthly_debt_service)
    liq = float(profile.liquid_savings)
    ctx["expense_ratio"] = exp_m / income_m if income_m > 0 else 0.0
    ctx["debt_service_ratio"] = debt_m / income_m if income_m > 0 else 0.0
    ctx["liquidity_months"] = liq / exp_m if exp_m > 0 else 0.0

    # Build model row in exact training feature order.
    feature_aliases = {
        # New corrected-tax dataset fields
        "baseline_tax_liability_lkr_corrected": "baseline_tax_liability_lkr",
        "effective_tax_rate_corrected": "effective_tax_rate",
        "disposable_income_monthly_lkr_corrected": "disposable_income_monthly_lkr",
        "savings_rate_corrected": "savings_rate",
        # Common naming variants
        "gross_monthly_income": "gross_monthly_income_lkr",
        "monthly_expenses": "monthly_expenses_lkr",
        "monthly_debt_service": "monthly_debt_service_lkr",
        "liquid_savings": "liquid_savings_lkr",
        "existing_investments": "existing_investments_lkr",
        "total_debt": "total_debt_lkr",
        "epf_balance": "epf_balance_lkr",
        "etf_balance": "etf_balance_lkr",
    }

    row: dict[str, Any] = {}
    for f in num_features:
        if f in ctx:
            row[f] = float(ctx.get(f, 0.0) or 0.0)
            continue
        alias = feature_aliases.get(f)
        if alias and alias in ctx:
            row[f] = float(ctx.get(alias, 0.0) or 0.0)
            continue
        row[f] = 0.0
    for f in cat_features:
        v = ctx.get(f, "unknown")
        row[f] = "unknown" if v is None else str(v)
    X = pd.DataFrame([row], columns=[*num_features, *cat_features])
    return X, ctx


def _strategy_category_from_catalog(raw: str) -> StrategyCategory:
    mapping = {
        "deduction_optimisation": StrategyCategory.DEDUCTION,
        "long_term_tax_efficiency": StrategyCategory.RETIREMENT,
        "housing_tax_efficiency": StrategyCategory.RELIEF,
        "compliance_optimisation": StrategyCategory.OTHER,
        "feasibility_guardrail": StrategyCategory.OTHER,
    }
    return mapping.get(raw, StrategyCategory.OTHER)


def _strategy_code_for_api(raw: str) -> str:
    """Normalize catalog strategy IDs to the API schema code pattern."""
    code = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw).strip()).upper()
    if len(code) < 2:
        code = "S0"
    if len(code) > 40:
        code = code[:40]
    return code


def generate_recommendations(
    db: Session,
    *,
    profile_id,
    top_k: int,
) -> RecommendationResponse:
    profile = get_profile(db, profile_id)
    artifacts = load_inference_artifacts()
    X, ctx = _build_feature_context(
        profile,
        num_features=artifacts.num_features,
        cat_features=artifacts.cat_features,
    )

    try:
        probs = artifacts.model.predict_proba(X)
    except Exception as exc:
        raise RecommendationGenerationError(f"Model prediction failed: {exc}") from exc
    if isinstance(probs, list):
        probs = np.column_stack([p[:, 1] for p in probs])  # type: ignore[index]
    prob_row = probs[0]
    score_by_sid = {sid: float(prob_row[i]) for i, sid in enumerate(artifacts.strategy_ids)}

    load_strategy_catalog, evaluate_strategy = _import_strategy_eval()
    catalog = load_strategy_catalog(_strategy_catalog_path())

    candidates: list[RecommendationItem] = []
    for s in catalog.strategies:
        eval_result = evaluate_strategy(s, ctx)
        if not eval_result.is_eligible:
            continue
        adoption_prob = score_by_sid.get(s.strategy_id, 0.0)
        risk_penalty = 0.2 if str(ctx.get("risk_tolerance", "medium")) == "high" else 0.1
        feasibility = float(eval_result.feasibility_score)
        savings_norm = min(1.0, max(0.0, adoption_prob))  # placeholder until impact estimator added
        final_score = (
            component_settings.COMP_RECOMMENDATION_W_SAVINGS * savings_norm
            + component_settings.COMP_RECOMMENDATION_W_ADOPTION * adoption_prob
            + component_settings.COMP_RECOMMENDATION_W_FEASIBILITY * feasibility
            - component_settings.COMP_RECOMMENDATION_W_RISK_PENALTY * risk_penalty
        )
        item = RecommendationItem(
            id=uuid4(),
            rank=999,
            strategy=Strategy(
                id=uuid4(),
                created_at=datetime.now(timezone.utc),
                updated_at=None,
                code=_strategy_code_for_api(s.strategy_id),
                name=s.name,
                category=_strategy_category_from_catalog(s.category),
                description=s.description,
                legal_reference=None,
                min_income=None,
                max_income=None,
                min_age=None,
                max_age=None,
                min_liquidity=None,
                risk_profile=ctx.get("risk_tolerance", "medium"),
                effort_score=0.3,
                is_active=True,
            ),
            estimated_annual_savings=Decimal(str(round(max(0.0, adoption_prob * 100000), 2))),
            adoption_probability=round(adoption_prob, 6),
            risk_score=round(risk_penalty, 6),
            confidence=round(feasibility, 6),
            scores=ScoreBreakdown(
                tax_savings_norm=round(savings_norm, 6),
                adoption_prob=round(adoption_prob, 6),
                feasibility=round(feasibility, 6),
                risk_penalty=round(risk_penalty, 6),
                final_score=round(final_score, 6),
            ),
            explanation=RecommendationExplanation(
                top_reasons=[],
                bottom_reasons=[],
                narrative=s.estimation_method.formula_ref[:500],
            ),
        )
        candidates.append(item)

    candidates.sort(key=lambda x: x.scores.final_score, reverse=True)
    for i, it in enumerate(candidates[:top_k], start=1):
        it.rank = i

    model_version = "local-artifacts"
    version_file = artifacts.artifacts_dir / "model_version.txt"
    if version_file.exists():
        model_version = version_file.read_text(encoding="utf-8").strip() or model_version

    return RecommendationResponse(
        id=uuid4(),
        profile_id=profile.id,
        generated_at=datetime.now(timezone.utc),
        model_version=model_version,
        items=candidates[:top_k],
    )

