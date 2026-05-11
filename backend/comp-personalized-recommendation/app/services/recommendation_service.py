"""Runtime recommendation generation using trained artifacts + rule feasibility."""

from __future__ import annotations

import re
import sys
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
from app.services.inference_assets import InferenceArtifacts, load_inference_artifacts
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


def _import_pair_features() -> Any:
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from features.pair_features import build_pair_dataframe  # type: ignore[import-not-found]

    return build_pair_dataframe


def _strategy_catalog_path() -> Path:
    return component_settings.COMP_RECOMMENDATION_RULES_PATH.parent / "strategy_catalog.yaml"


def _build_feature_context(
    profile: FinancialProfileORM,
    *,
    num_features: list[str],
    cat_features: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    derived = compute_derived_features(profile)

    ctx: dict[str, Any] = {
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
    ctx["province"] = "Unknown"

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

    income_m = float(profile.gross_monthly_income)
    exp_m = float(profile.monthly_expenses)
    debt_m = float(profile.monthly_debt_service)
    liq = float(profile.liquid_savings)
    ctx["expense_ratio"] = exp_m / income_m if income_m > 0 else 0.0
    ctx["debt_service_ratio"] = debt_m / income_m if income_m > 0 else 0.0
    ctx["liquidity_months"] = liq / exp_m if exp_m > 0 else 0.0

    feature_aliases = {
        "baseline_tax_liability_lkr_corrected": "baseline_tax_liability_lkr",
        "effective_tax_rate_corrected": "effective_tax_rate",
        "disposable_income_monthly_lkr_corrected": "disposable_income_monthly_lkr",
        "savings_rate_corrected": "savings_rate",
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


def _user_narrative(strategy_id: str, ctx: dict[str, Any]) -> str:
    """Generate a plain-English, user-facing reason for recommending this strategy."""
    sid = strategy_id.lower()
    income_lkr = int(ctx.get("annual_income", 0) or 0)
    income_fmt = f"LKR {income_lkr:,.0f}"
    tax_lkr = int(ctx.get("annual_tax_before_strategy", 0) or 0)
    tax_fmt = f"LKR {tax_lkr:,.0f}"
    dti = float(ctx.get("debt_to_income", 0) or 0)
    savings_rate = float(ctx.get("savings_rate", 0) or 0)
    liq_months = float(ctx.get("liquidity_months", 0) or 0)
    epf = int(ctx.get("epf_balance_lkr", 0) or 0)
    life_ins = int(ctx.get("life_insurance_premium_annual_lkr", 0) or 0)
    home_loan = int(ctx.get("home_loan_interest_annual_lkr", 0) or 0)
    donations = int(ctx.get("donations_annual_lkr", 0) or 0)
    occupation = str(ctx.get("occupation", "")).replace("_", " ")
    age_band = str(ctx.get("age_band", ""))
    years_emp = int(ctx.get("years_employed", 0) or 0)

    if "s001" in sid:
        parts = []
        if life_ins > 0:
            parts.append(f"your life insurance premium of LKR {life_ins:,.0f}/year")
        if ctx.get("has_health_insurance"):
            parts.append("your health insurance premium")
        items = " and ".join(parts) if parts else "your insurance premiums"
        return (
            f"You are paying {items}, which qualify for a tax deduction under IRD rules. "
            f"By making sure these are properly claimed, you can reduce the portion of your "
            f"income that is taxed and lower your current tax bill of {tax_fmt}."
        )

    if "s002" in sid:
        return (
            f"You have room to increase your retirement savings contributions. "
            f"Any additional qualifying contribution you make is deducted from your taxable income "
            f"of {income_fmt}, meaning you pay less tax now while building your retirement fund."
        )

    if "s003" in sid:
        if donations > 0:
            return (
                f"You already donate LKR {donations:,.0f}/year to approved charities. "
                f"Timing or slightly increasing these donations within the annual limit "
                f"can reduce your taxable income and lower your tax bill of {tax_fmt}, "
                f"as long as your cash flow remains healthy."
            )
        return (
            f"Making donations to IRD-approved charities allows you to deduct those amounts "
            f"from your taxable income of {income_fmt}. This reduces your tax bill of {tax_fmt} "
            f"while supporting a cause you care about."
        )

    if "s004" in sid:
        return (
            f"If you are paying rent for your residence, you may be entitled to a rental relief "
            f"deduction under IRD rules. This directly reduces your taxable income of {income_fmt} "
            f"and lowers your current tax bill of {tax_fmt}."
        )

    if "s005" in sid:
        if home_loan > 0:
            return (
                f"You are paying LKR {home_loan:,.0f}/year in home loan interest. "
                f"IRD allows you to deduct eligible home loan interest up to the statutory cap, "
                f"which reduces your taxable income of {income_fmt} and lowers your tax bill."
            )
        return (
            f"Your home loan interest payments qualify for a tax deduction under IRD rules. "
            f"Claiming this fully can reduce your taxable income of {income_fmt}."
        )

    if "s006" in sid:
        parts = []
        if dti > 0.65:
            parts.append(f"your debt-to-income ratio is {dti:.0%}, which is high")
        if savings_rate < 0.05:
            parts.append(f"your savings rate is very low ({savings_rate:.0%})")
        if liq_months < 1.0:
            parts.append(f"you have less than one month of expenses in liquid savings")
        reason = "; ".join(parts) if parts else "your current cash flow is under pressure"
        return (
            f"Right now {reason}. Before taking on additional tax-saving actions that require "
            f"extra payments, it is safer to first reduce your debt burden and build a small "
            f"emergency buffer. This puts you in a stronger position to benefit from other "
            f"strategies in the future."
        )

    if "s007" in sid:
        return (
            f"As a salaried {occupation}, your employer deducts APIT (tax) from your salary each "
            f"month. Sometimes the total amount withheld across the year does not exactly match "
            f"your actual tax liability of {tax_fmt}. Checking this could mean you get a refund "
            f"for tax over-deducted, or you avoid a penalty for under-deduction."
        )

    if "s008" in sid:
        epf_fmt = f"LKR {epf:,.0f}" if epf > 0 else "an EPF account"
        return (
            f"You have {epf_fmt} in your EPF fund and have been employed for {years_emp} years. "
            f"Making additional voluntary EPF contributions beyond the mandatory amount qualifies "
            f"as a deductible payment under IRA Section 53, reducing your taxable income of "
            f"{income_fmt} while growing your retirement savings."
        )

    if "s009" in sid:
        return (
            f"As a {occupation}, you can claim your legitimate business expenses — such as "
            f"professional fees, office costs, and tools of trade — as deductions under IRA "
            f"Sections 17–18. This reduces your assessable income of {income_fmt} and lowers "
            f"your tax bill of {tax_fmt}."
        )

    if "s010" in sid:
        epf_fmt = f"LKR {epf:,.0f}" if epf > 0 else "EPF savings"
        return (
            f"You have {epf_fmt} in EPF and have worked for {years_emp} years "
            f"(age band: {age_band}). When you retire or resign, your EPF lump sum, ETF payout, "
            f"and employer gratuity are exempt from tax up to statutory limits under IRA Section 6. "
            f"Planning your exit timing carefully can maximise the tax-free portion of these benefits."
        )

    # Generic fallback
    return (
        f"This strategy can help reduce your taxable income of {income_fmt} "
        f"and lower your current tax liability of {tax_fmt} based on your financial profile."
    )


def _strategy_code_for_api(raw: str) -> str:
    code = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw).strip()).upper()
    if len(code) < 2:
        code = "S0"
    if len(code) > 40:
        code = code[:40]
    return code


def _min_max_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _model_version_string(artifacts_dir: Path) -> str:
    version_file = artifacts_dir / "model_version.txt"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip() or "local-artifacts"
    return "local-artifacts"


def _item_from_strategy(
    *,
    s: Any,
    ctx: dict[str, Any],
    eval_result: Any,
    adoption_prob: float,
    tax_savings_norm: float,
    lambdamart_score: float | None = None,
) -> RecommendationItem:
    risk_penalty = 0.2 if str(ctx.get("risk_tolerance", "medium")) == "high" else 0.1
    feasibility = float(eval_result.feasibility_score)
    savings_norm = min(1.0, max(0.0, tax_savings_norm))
    adopt = min(1.0, max(0.0, adoption_prob))

    if lambdamart_score is not None:
        # LambdaMART ranking: final_score IS the normalised LambdaMART output.
        # The model has already learned optimal NDCG-based ordering from training
        # data — no manual weights needed.
        final_score = min(1.0, max(0.0, lambdamart_score))
    else:
        # Fallback weighted formula (legacy mode).
        final_score = (
            component_settings.COMP_RECOMMENDATION_W_SAVINGS * savings_norm
            + component_settings.COMP_RECOMMENDATION_W_ADOPTION * adopt
            + component_settings.COMP_RECOMMENDATION_W_FEASIBILITY * feasibility
            - component_settings.COMP_RECOMMENDATION_W_RISK_PENALTY * risk_penalty
        )

    baseline_tax = float(ctx.get("baseline_tax_liability_lkr", 0.0) or 0.0)
    est_sav = max(0.0, min(baseline_tax * 0.45, baseline_tax * savings_norm * 0.35))

    return RecommendationItem(
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
        estimated_annual_savings=Decimal(str(round(est_sav, 2))),
        adoption_probability=round(adopt, 6),
        risk_score=round(risk_penalty, 6),
        confidence=round(feasibility, 6),
        scores=ScoreBreakdown(
            tax_savings_norm=round(savings_norm, 6),
            adoption_prob=round(adopt, 6),
            feasibility=round(feasibility, 6),
            risk_penalty=round(risk_penalty, 6),
            final_score=round(final_score, 6),
        ),
        explanation=RecommendationExplanation(
            top_reasons=[],
            bottom_reasons=[],
            narrative=_user_narrative(s.strategy_id, ctx),
        ),
    )


def _generate_legacy(
    profile: FinancialProfileORM,
    *,
    top_k: int,
    artifacts: InferenceArtifacts,
) -> RecommendationResponse:
    if artifacts.model is None:
        raise RecommendationGenerationError("Legacy matcher model missing")
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
        tax_savings_norm = min(1.0, max(0.0, adoption_prob))
        candidates.append(
            _item_from_strategy(
                s=s,
                ctx=ctx,
                eval_result=eval_result,
                adoption_prob=adoption_prob,
                tax_savings_norm=tax_savings_norm,
            )
        )

    candidates.sort(key=lambda x: x.scores.final_score, reverse=True)
    for i, it in enumerate(candidates[:top_k], start=1):
        it.rank = i

    return RecommendationResponse(
        id=uuid4(),
        profile_id=profile.id,
        generated_at=datetime.now(timezone.utc),
        model_version=_model_version_string(artifacts.artifacts_dir),
        items=candidates[:top_k],
    )


def _generate_phase4(
    profile: FinancialProfileORM,
    *,
    top_k: int,
    artifacts: InferenceArtifacts,
) -> RecommendationResponse:
    if artifacts.adoption_model is None or artifacts.ranker_model is None:
        raise RecommendationGenerationError("Phase 4 adoption or ranker model missing")

    X_user, ctx = _build_feature_context(
        profile,
        num_features=artifacts.num_features,
        cat_features=artifacts.cat_features,
    )

    # --- Adoption probability (one probability per strategy) ---
    try:
        adopt_proba = artifacts.adoption_model.predict_proba(X_user)
    except Exception as exc:
        raise RecommendationGenerationError(f"Adoption model failed: {exc}") from exc
    if isinstance(adopt_proba, list):
        adopt_cols = np.column_stack([p[:, 1] for p in adopt_proba])  # type: ignore[index]
    else:
        adopt_cols = adopt_proba
    adopt_by_sid = {sid: float(adopt_cols[0, i]) for i, sid in enumerate(artifacts.strategy_ids)}

    load_strategy_catalog, evaluate_strategy = _import_strategy_eval()
    catalog = load_strategy_catalog(_strategy_catalog_path())

    # Build strategy lookup keyed by strategy_id for ordering.
    sid_to_strategy = {s.strategy_id: s for s in catalog.strategies}

    # Build pair features in the same order as artifacts.strategy_ids so that
    # LambdaMART scores align with the strategy list by index.
    build_pair_dataframe = _import_pair_features()
    user_dict = X_user.iloc[0].to_dict()
    ordered_strategies = tuple(
        sid_to_strategy[sid] for sid in artifacts.strategy_ids if sid in sid_to_strategy
    )
    pair_df = build_pair_dataframe(
        user_dict,
        ordered_strategies,
        user_num_keys=artifacts.num_features,
        user_cat_keys=artifacts.cat_features,
    )

    # --- LambdaMART ranking scores (primary ranking criterion) ---
    try:
        rank_raw = artifacts.ranker_model.predict(pair_df)
    except Exception as exc:
        raise RecommendationGenerationError(f"LambdaMART ranker failed: {exc}") from exc

    rank_list = [float(x) for x in np.asarray(rank_raw).ravel()]
    rank_norms = _min_max_norm(rank_list)
    lambdamart_by_sid = {
        artifacts.strategy_ids[i]: rank_norms[i]
        for i in range(len(artifacts.strategy_ids))
    }

    # --- Filter eligible strategies and build recommendation items ---
    candidates: list[RecommendationItem] = []
    for s in catalog.strategies:
        eval_result = evaluate_strategy(s, ctx)
        if not eval_result.is_eligible:
            continue
        lm_score = lambdamart_by_sid.get(s.strategy_id, 0.0)
        candidates.append(
            _item_from_strategy(
                s=s,
                ctx=ctx,
                eval_result=eval_result,
                adoption_prob=adopt_by_sid.get(s.strategy_id, 0.0),
                tax_savings_norm=lm_score,
                lambdamart_score=lm_score,  # drives final_score and rank order
            )
        )

    # Sort by LambdaMART-driven final_score (highest first).
    candidates.sort(key=lambda x: x.scores.final_score, reverse=True)
    for i, it in enumerate(candidates[:top_k], start=1):
        it.rank = i

    return RecommendationResponse(
        id=uuid4(),
        profile_id=profile.id,
        generated_at=datetime.now(timezone.utc),
        model_version=_model_version_string(artifacts.artifacts_dir),
        items=candidates[:top_k],
    )


def generate_recommendations(
    db: Session,
    *,
    profile_id,
    top_k: int,
) -> RecommendationResponse:
    profile = get_profile(db, profile_id)
    artifacts = load_inference_artifacts()
    if artifacts.mode == "phase4":
        return _generate_phase4(profile, top_k=top_k, artifacts=artifacts)
    return _generate_legacy(profile, top_k=top_k, artifacts=artifacts)
