"""Hybrid recommendation service: LightGBM + LambdaMART + RAG + adoption fusion.

Pipeline:
  1. Load profile from DB and compute derived features.
  2. Run LightGBM adoption model  → adoption_probability per strategy.
  3. Run LambdaMART ranker        → lambdamart_score per strategy (min-max normalised).
  4. Run TF-IDF RAG retrieval     → rag_similarity_score per strategy (cosine similarity).
  5. Filter strategies by IRD eligibility rules.
  6. retrieval_hybrid = lambda_weight × lambdamart + (1-lambda_weight) × rag
  7. fusion_score = w_savings×LM + w_adoption×adopt + w_feasibility×feas − w_risk×risk
  8. Sort by fusion_score descending → return top-K.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
import yaml
from sqlalchemy.orm import Session

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM
from app.services.catalog_rules_service import baseline_tax_for_profile, get_synced_snapshot
from app.services.inference_assets import load_inference_artifacts
from app.services.profile_service import ProfileNotFoundError, compute_derived_features, get_profile
from app.services.risk_scoring_service import compute_strategy_risk_bundle, resolve_risk_tolerance
from app.services.rag_service import (
    _IRD_REFS,
    _build_vector_store,
    _generate_detailed_explanation,
    _generate_explanation,
    _load_strategies,
    _profile_to_query,
)

LAMBDA_WEIGHT = 0.7
RAG_WEIGHT = 0.3


# ---------------------------------------------------------------------------
# Helpers re-used from recommendation_service (keep DRY via import)
# ---------------------------------------------------------------------------

def _import_strategy_eval() -> Any:
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


def _min_max_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


@lru_cache(maxsize=1)
def _default_fusion_weights() -> dict[str, float]:
    from app.services.inference_assets import resolve_artifacts_dir

    for candidate in (
        resolve_artifacts_dir(),
        Path(__file__).resolve().parents[1] / "artifacts",
        Path(component_settings.COMP_RECOMMENDATION_ARTIFACTS_DIR),
    ):
        weights_path = candidate / "scoring_weights.yaml"
        if weights_path.exists():
            raw = yaml.safe_load(weights_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {
                    "w_savings": float(raw.get("w_savings", 0.40)),
                    "w_adoption": float(raw.get("w_adoption", 0.30)),
                    "w_feasibility": float(raw.get("w_feasibility", 0.20)),
                    "w_risk_penalty": float(raw.get("w_risk_penalty", 0.10)),
                    "w_risk_alignment": float(raw.get("w_risk_alignment", 0.12)),
                }
    return {
        "w_savings": float(component_settings.COMP_RECOMMENDATION_W_SAVINGS),
        "w_adoption": float(component_settings.COMP_RECOMMENDATION_W_ADOPTION),
        "w_feasibility": float(component_settings.COMP_RECOMMENDATION_W_FEASIBILITY),
        "w_risk_penalty": float(component_settings.COMP_RECOMMENDATION_W_RISK_PENALTY),
        "w_risk_alignment": 0.12,
    }


def _fuse_rank_score(
    *,
    lambdamart_score: float,
    adoption_probability: float,
    feasibility: float,
    risk_penalty: float,
    risk_alignment: float = 1.0,
    weights: dict[str, float] | None = None,
) -> float:
    w = weights or _default_fusion_weights()
    savings = min(1.0, max(0.0, lambdamart_score))
    adopt = min(1.0, max(0.0, adoption_probability))
    feas = min(1.0, max(0.0, feasibility))
    risk = min(1.0, max(0.0, risk_penalty))
    align = min(1.0, max(0.0, risk_alignment))
    return (
        w["w_savings"] * savings
        + w["w_adoption"] * adopt
        + w["w_feasibility"] * feas
        + w.get("w_risk_alignment", 0.12) * align
        - w["w_risk_penalty"] * risk
    )


def _adoption_probabilities(artifacts: Any, X_user: pd.DataFrame) -> dict[str, float]:
    """Map strategy_id → P(adopt) from the Phase 4 multi-label adoption model."""
    adopt_proba = artifacts.adoption_model.predict_proba(X_user)
    if isinstance(adopt_proba, list):
        if len(adopt_proba) != len(artifacts.strategy_ids):
            raise RuntimeError(
                f"Adoption model returned {len(adopt_proba)} outputs "
                f"but manifest lists {len(artifacts.strategy_ids)} strategy_ids"
            )
        adopt_cols = np.column_stack([p[:, 1] for p in adopt_proba])
    else:
        adopt_cols = np.asarray(adopt_proba)
        if adopt_cols.ndim == 1:
            adopt_cols = adopt_cols.reshape(1, -1)
    if adopt_cols.shape[1] != len(artifacts.strategy_ids):
        raise RuntimeError(
            f"Adoption probability width {adopt_cols.shape[1]} "
            f"!= strategy_ids length {len(artifacts.strategy_ids)}"
        )
    return {
        sid: float(adopt_cols[0, i])
        for i, sid in enumerate(artifacts.strategy_ids)
    }


def _build_ctx(profile: FinancialProfileORM, artifacts: Any) -> tuple[pd.DataFrame, dict]:
    """Build feature DataFrame and context dict from profile."""
    derived = compute_derived_features(profile)
    ctx: dict = {
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
    }

    num_f = artifacts.num_features
    cat_f = artifacts.cat_features

    src_shares = {k: 0.0 for k in [
        "src_employment_share", "src_business_share", "src_dividend_share",
        "src_interest_share", "src_rental_share", "src_other_share",
    ]}
    if profile.income_sources:
        total = sum(float(s.get("monthly_amount", 0) or 0) for s in profile.income_sources)
        for src in profile.income_sources:
            kind = str(src.get("kind", "other")).lower()
            amt = float(src.get("monthly_amount", 0) or 0)
            key = f"src_{kind}_share"
            if key in src_shares and total > 0:
                src_shares[key] += amt / total
    ctx.update(src_shares)

    gmi = float(profile.gross_monthly_income)
    exp = float(profile.monthly_expenses)
    debt_m = float(profile.monthly_debt_service)
    liq = float(profile.liquid_savings)
    ctx["expense_ratio"] = exp / gmi if gmi > 0 else 0.0
    ctx["debt_service_ratio"] = debt_m / gmi if gmi > 0 else 0.0
    ctx["liquidity_months"] = liq / exp if exp > 0 else 0.0

    archetype_map = {
        ("low", True): "conservative_saver",
        ("medium", True): "balanced_planner",
        ("high", True): "growth_investor",
        ("low", False): "debt_stressed",
        ("medium", False): "balanced_planner",
        ("high", False): "risk_taker",
    }
    sr_ok = float(derived.savings_rate) >= 0.1
    ctx["archetype"] = archetype_map.get((str(profile.risk_tolerance), sr_ok), "balanced_planner")

    from app.schemas.profile import _age_band_midpoint  # type: ignore[import-not-found]
    age = int(derived.age_years)
    if age <= 24:
        ctx["age_band"] = "18-24"
    elif age <= 29:
        ctx["age_band"] = "25-29"
    elif age <= 34:
        ctx["age_band"] = "30-34"
    elif age <= 39:
        ctx["age_band"] = "35-39"
    elif age <= 44:
        ctx["age_band"] = "40-44"
    elif age <= 49:
        ctx["age_band"] = "45-49"
    elif age <= 54:
        ctx["age_band"] = "50-54"
    elif age <= 59:
        ctx["age_band"] = "55-59"
    elif age <= 64:
        ctx["age_band"] = "60-64"
    elif age <= 70:
        ctx["age_band"] = "65-70"
    else:
        ctx["age_band"] = "70+"

    from app.schemas.profile import _PROVINCE_TO_DISTRICT  # type: ignore[import-not-found]
    ctx["province"] = next(
        (prov for prov, dist in _PROVINCE_TO_DISTRICT.items() if dist == str(profile.district)),
        "Western",
    )

    row = {}
    for k in num_f:
        row[k] = float(ctx.get(k, 0.0) or 0.0)
    for k in cat_f:
        v = ctx.get(k, "unknown")
        row[k] = "unknown" if v is None else str(v)

    X = pd.DataFrame([row], columns=[*num_f, *cat_f])
    return X, ctx


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

class HybridResult:
    def __init__(
        self,
        rank: int,
        strategy_id: str,
        name: str,
        category: str,
        description: str,
        hybrid_score: float,
        retrieval_hybrid_score: float,
        fusion_score: float,
        lambdamart_score: float,
        rag_similarity_score: float,
        adoption_probability: float,
        estimated_annual_savings: float,
        confidence: float,
        risk_score: float,
        strategy_audit_risk: str,
        risk_tolerance_applied: str,
        risk_alignment: float,
        ird_reference: str,
        required_docs: list[str],
        why_relevant: str,
        detailed_explanation: dict[str, str],
    ) -> None:
        self.rank = rank
        self.strategy_id = strategy_id
        self.name = name
        self.category = category
        self.description = description
        self.hybrid_score = hybrid_score
        self.retrieval_hybrid_score = retrieval_hybrid_score
        self.fusion_score = fusion_score
        self.lambdamart_score = lambdamart_score
        self.rag_similarity_score = rag_similarity_score
        self.adoption_probability = adoption_probability
        self.estimated_annual_savings = estimated_annual_savings
        self.confidence = confidence
        self.risk_score = risk_score
        self.strategy_audit_risk = strategy_audit_risk
        self.risk_tolerance_applied = risk_tolerance_applied
        self.risk_alignment = risk_alignment
        self.ird_reference = ird_reference
        self.required_docs = required_docs
        self.why_relevant = why_relevant
        self.detailed_explanation = detailed_explanation


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hybrid_query(
    db: Session,
    *,
    profile_id: str,
    top_k: int = 5,
    lambda_weight: float = LAMBDA_WEIGHT,
    rules_source: str = "default",
    assessment_year: str | None = None,
    risk_tolerance_override: str | None = None,
) -> tuple[list[HybridResult], str, dict[str, Any]]:
    """Run hybrid recommendation pipeline.

    Returns (results, query_text, rules_context).

    When ``rules_source`` is ``catalog``, the caller must sync that
    ``assessment_year`` via ``POST /admin/catalog-rules/sync`` first. The
    default YAML rules path is never modified.
    """
    if rules_source not in {"default", "catalog"}:
        raise ValueError("rules_source must be 'default' or 'catalog'")
    if rules_source == "catalog":
        if not assessment_year:
            raise ValueError("assessment_year is required when rules_source is 'catalog'")
        snapshot = get_synced_snapshot(assessment_year)
        if snapshot is None:
            raise ValueError(
                f"Catalog rules for {assessment_year} are not loaded. "
                "Sync via POST /api/v1/admin/catalog-rules/sync first."
            )

    profile = get_profile(db, UUID(profile_id))
    if profile is None:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    artifacts = load_inference_artifacts()
    if artifacts.adoption_model is None or artifacts.ranker_model is None:
        raise RuntimeError("Phase 4 artifacts not loaded — ensure phase4_manifest.json exists")

    # ── Step 1: Build feature context ────────────────────────────────────────
    X_user, ctx = _build_ctx(profile, artifacts)
    user_risk_tolerance = resolve_risk_tolerance(
        profile_tolerance=str(profile.risk_tolerance),
        override=risk_tolerance_override,
    )
    ctx["risk_tolerance"] = user_risk_tolerance

    if rules_source == "catalog" and assessment_year:
        snapshot = get_synced_snapshot(assessment_year)
        assert snapshot is not None
        baseline_tax = baseline_tax_for_profile(profile, snapshot.rules)
        rules_context: dict[str, Any] = {
            "rules_source": "catalog",
            "rules_version": snapshot.rules.version,
            "assessment_year": assessment_year,
            "baseline_tax_lkr": round(baseline_tax, 2),
            "catalog_promoted_at": snapshot.promoted_at,
            "catalog_act": snapshot.personal_relief_act,
            "mapped_fields": snapshot.mapped_fields,
        }
    else:
        baseline_tax = float(ctx.get("baseline_tax_liability_lkr", 0.0) or 0.0)
        rules_context = {
            "rules_source": "default",
            "rules_version": str(component_settings.COMP_RECOMMENDATION_RULES_PATH.stem),
            "assessment_year": None,
            "baseline_tax_lkr": round(baseline_tax, 2),
            "catalog_promoted_at": None,
            "catalog_act": None,
            "mapped_fields": [],
        }

    # ── Step 2: LightGBM adoption probability ────────────────────────────────
    adopt_by_sid = _adoption_probabilities(artifacts, X_user)

    # ── Step 3: LambdaMART ranking scores ────────────────────────────────────
    build_pair_dataframe = _import_pair_features()
    load_strategy_catalog, evaluate_strategy = _import_strategy_eval()
    catalog = load_strategy_catalog(_strategy_catalog_path())
    sid_to_strategy = {s.strategy_id: s for s in catalog.strategies}

    ordered_strategies = tuple(
        sid_to_strategy[sid] for sid in artifacts.strategy_ids if sid in sid_to_strategy
    )
    user_dict = X_user.iloc[0].to_dict()
    pair_df = build_pair_dataframe(
        user_dict,
        ordered_strategies,
        user_num_keys=artifacts.num_features,
        user_cat_keys=artifacts.cat_features,
    )
    rank_raw = artifacts.ranker_model.predict(pair_df)
    rank_list = [float(x) for x in np.asarray(rank_raw).ravel()]
    rank_norms = _min_max_norm(rank_list)
    lambdamart_by_sid = {
        artifacts.strategy_ids[i]: rank_norms[i]
        for i in range(len(artifacts.strategy_ids))
    }

    # ── Step 4: RAG TF-IDF similarity scores ─────────────────────────────────
    rag_ctx = {
        "occupation": str(profile.occupation),
        "risk_tolerance": str(profile.risk_tolerance),
        "gross_monthly_income_lkr": float(profile.gross_monthly_income),
        "annual_income": float(ctx["annual_income"]),
        "epf_balance_lkr": float(profile.epf_balance),
        "years_employed": int(profile.years_employed),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "has_health_insurance": bool(profile.health_insurance),
        "debt_to_income": float(ctx["debt_to_income"]),
        "savings_rate": float(ctx["savings_rate"]),
        "age_years": int(ctx["age_years"]),
    }
    query_text = _profile_to_query(rag_ctx)

    from sklearn.metrics.pairwise import cosine_similarity as cos_sim
    vectorizer, matrix, raw_strategies = _build_vector_store()
    query_vec = vectorizer.transform([query_text])
    rag_scores_arr = cos_sim(query_vec, matrix).flatten()
    rag_by_sid = {
        raw_strategies[i].get("strategy_id", ""): float(rag_scores_arr[i])
        for i in range(len(raw_strategies))
    }

    # ── Step 5: Filter eligible + compute fusion score ─────────────────────────
    rag_weight = 1.0 - lambda_weight
    fusion_weights = _default_fusion_weights()
    candidates: list[tuple[float, HybridResult]] = []

    for s in catalog.strategies:
        eval_result = evaluate_strategy(s, ctx)
        if not eval_result.is_eligible:
            continue

        sid = s.strategy_id
        lm_score = lambdamart_by_sid.get(sid, 0.0)
        rag_score = rag_by_sid.get(sid, 0.0)
        retrieval_hybrid = round(lambda_weight * lm_score + rag_weight * rag_score, 6)

        adopt = adopt_by_sid.get(sid, 0.0)
        est_savings = max(0.0, min(baseline_tax * 0.45, baseline_tax * lm_score * 0.35))
        risk_penalty, audit_level, risk_alignment = compute_strategy_risk_bundle(
            strategy_audit_risk=s.audit_risk_level,
            user_risk_tolerance=user_risk_tolerance,
        )
        feasibility = float(eval_result.feasibility_score)
        fusion_score = round(
            _fuse_rank_score(
                lambdamart_score=lm_score,
                adoption_probability=adopt,
                feasibility=feasibility,
                risk_penalty=risk_penalty,
                risk_alignment=risk_alignment,
                weights=fusion_weights,
            ),
            6,
        )

        raw_s = next((r for r in raw_strategies if r.get("strategy_id") == sid), {})

        candidates.append((
            fusion_score,
            HybridResult(
                rank=0,
                strategy_id=sid,
                name=s.name,
                category=s.category.replace("_", " "),
                description=s.description,
                hybrid_score=fusion_score,
                retrieval_hybrid_score=retrieval_hybrid,
                fusion_score=fusion_score,
                lambdamart_score=round(lm_score, 4),
                rag_similarity_score=round(rag_score, 4),
                adoption_probability=round(adopt, 4),
                estimated_annual_savings=round(est_savings, 2),
                confidence=round(feasibility, 4),
                risk_score=round(risk_penalty, 4),
                strategy_audit_risk=audit_level,
                risk_tolerance_applied=user_risk_tolerance,
                risk_alignment=round(risk_alignment, 4),
                ird_reference=_IRD_REFS.get(sid, "IRA No. 24 of 2017"),
                required_docs=raw_s.get("constraints", {}).get("required_docs", []),
                why_relevant=_generate_explanation(raw_s, rag_ctx, rag_score),
                detailed_explanation=_generate_detailed_explanation(raw_s, rag_ctx),
            ),
        ))

    candidates.sort(key=lambda x: x[0], reverse=True)
    results = []
    for rank, (_, item) in enumerate(candidates[:top_k], start=1):
        item.rank = rank
        results.append(item)

    rules_context["risk_tolerance_applied"] = user_risk_tolerance
    rules_context["risk_tolerance_override"] = risk_tolerance_override is not None

    return results, query_text, rules_context
