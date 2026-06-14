"""SHAP explanations for ranked strategies (Phase 6 / FR10)."""

from __future__ import annotations

import json
import re
import sys
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM
from app.schemas.recommendation import (
    FeatureAttribution,
    RecommendationExplanation,
)
from app.services.inference_assets import ArtifactLoadError, InferenceArtifacts, load_inference_artifacts
from app.services.impact_service import StrategyNotFoundError
from app.services.profile_service import ProfileNotFoundError, compute_derived_features, get_profile


class ExplanationError(RuntimeError):
    """Raised when an explanation cannot be produced."""


def _import_eval() -> Any:
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from evaluation.explainability import explain_pair_ranking  # noqa: E402
    from features.pair_features import build_pair_dataframe  # noqa: E402
    from strategy_gen.catalog import load_strategy_catalog  # noqa: E402

    return explain_pair_ranking, build_pair_dataframe, load_strategy_catalog


def _catalog_path() -> Any:
    return component_settings.COMP_RECOMMENDATION_RULES_PATH.parent / "strategy_catalog.yaml"


def _normalize_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper()


def _resolve_strategy(strategy_code: str) -> Any:
    _, _, load_strategy_catalog = _import_eval()
    catalog = load_strategy_catalog(_catalog_path())
    needle = _normalize_code(strategy_code)
    for s in catalog.strategies:
        if _normalize_code(s.strategy_id) == needle or needle in _normalize_code(s.strategy_id):
            return s, catalog
    raise StrategyNotFoundError(f"Unknown strategy_code: {strategy_code}")


def _build_user_row(profile: FinancialProfileORM) -> dict[str, Any]:
    """Align with Phase 4 pair-feature training row (subset of training CSV builder)."""
    derived = compute_derived_features(profile)
    gmi = float(profile.gross_monthly_income)
    exp = float(profile.monthly_expenses)
    debt_m = float(profile.monthly_debt_service)
    liq = float(profile.liquid_savings)
    annual = float(derived.gross_annual_taxable_income)
    baseline = float(derived.baseline_tax_liability_annual)
    disp = float(derived.disposable_income_monthly)
    sav = float(derived.savings_rate)
    return {
        "dependents": float(profile.dependents),
        "years_employed": float(profile.years_employed),
        "gross_monthly_income_lkr": gmi,
        "monthly_expenses_lkr": exp,
        "monthly_debt_service_lkr": debt_m,
        "liquid_savings_lkr": liq,
        "existing_investments_lkr": float(profile.existing_investments),
        "total_debt_lkr": float(profile.total_debt),
        "epf_balance_lkr": float(profile.epf_balance),
        "etf_balance_lkr": float(profile.etf_balance),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "gross_annual_taxable_income_lkr": annual,
        "baseline_tax_liability_lkr": baseline,
        "effective_tax_rate": float(derived.effective_tax_rate),
        "disposable_income_monthly_lkr": disp,
        "savings_rate": sav,
        "debt_to_income": float(derived.debt_to_income),
        "expense_ratio": exp / gmi if gmi > 0 else 0.0,
        "debt_service_ratio": debt_m / gmi if gmi > 0 else 0.0,
        "liquidity_months": liq / exp if exp > 0 else 0.0,
        "src_employment_share": 1.0,
        "src_business_share": 0.0,
        "src_dividend_share": 0.0,
        "src_interest_share": 0.0,
        "src_rental_share": 0.0,
        "src_other_share": 0.0,
        "gender": str(profile.gender),
        "marital_status": str(profile.marital_status),
        "occupation": str(profile.occupation),
        "risk_tolerance": str(profile.risk_tolerance),
        "archetype": "unknown",
        "age_band": "30-34",
        "province": str(profile.district),
    }


def _load_pair_meta(artifacts: InferenceArtifacts) -> tuple[list[str], list[str]]:
    meta_path = artifacts.artifacts_dir / "pair_feature_meta.json"
    if not meta_path.exists():
        return artifacts.num_features, artifacts.cat_features
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return [str(x) for x in meta["user_num_features"]], [str(x) for x in meta["user_cat_features"]]


def explain_strategy_for_profile(
    db: Session,
    *,
    profile_id: UUID,
    strategy_code: str,
    top_k: int = 5,
) -> RecommendationExplanation:
    """Produce SHAP attributions for one profile×strategy pair."""
    try:
        profile = get_profile(db, profile_id)
    except ProfileNotFoundError:
        raise

    artifacts = load_inference_artifacts()
    if artifacts.mode != "phase4":
        raise ExplanationError("SHAP explanations require Phase 4 LambdaMART artifacts")
    if artifacts.ranker_model is None:
        raise ExplanationError("Ranker model not loaded")

    strategy, catalog = _resolve_strategy(strategy_code)
    explain_pair_ranking, build_pair_dataframe, _ = _import_eval()
    user_num, user_cat = _load_pair_meta(artifacts)

    ordered = tuple(s for s in catalog.strategies if s.strategy_id in artifacts.strategy_ids)
    if not ordered:
        ordered = catalog.strategies

    user_row = _build_user_row(profile)
    pair_df = build_pair_dataframe(
        user_row,
        ordered,
        user_num_keys=user_num,
        user_cat_keys=user_cat,
    )

    sid_list = [s.strategy_id for s in ordered]
    try:
        row_index = sid_list.index(strategy.strategy_id)
    except ValueError:
        raise StrategyNotFoundError(f"Strategy {strategy_code} not in ranker strategy list") from None

    try:
        result = explain_pair_ranking(
            artifacts.ranker_model,
            pair_df,
            strategy_row_index=row_index,
            top_k=top_k,
        )
    except Exception as exc:
        raise ExplanationError(f"SHAP explain failed: {exc}") from exc

    return RecommendationExplanation(
        top_reasons=[
            FeatureAttribution(feature=r.feature, shap_value=r.shap_value, direction=r.direction)
            for r in result.top_reasons
        ],
        bottom_reasons=[
            FeatureAttribution(feature=r.feature, shap_value=r.shap_value, direction=r.direction)
            for r in result.bottom_reasons
        ],
        narrative=result.narrative,
    )


__all__ = [
    "ExplanationError",
    "explain_strategy_for_profile",
]
