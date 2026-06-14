"""Predictive impact simulation service (Phase 5 — FR7, FR8)."""

from __future__ import annotations

import re
import sys
import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM
from app.schemas.impact import (
    ImpactSimulationRequest,
    ImpactSimulationResponse,
    ImpactSummary,
    ProjectionBand,
    Scenario,
    StrategyComparisonRequest,
    YearlyProjection,
)
from app.services.profile_service import ProfileNotFoundError, compute_derived_features, get_profile

# Stable UUID namespace for catalog strategy ids in API responses.
_STRATEGY_UUID_NS = uuid.UUID("a3f2c8e1-5b4d-4e9a-8c7d-2f1e0b9a6d3c")


class ImpactSimulationError(RuntimeError):
    """Raised when simulation cannot be completed."""


class StrategyNotFoundError(LookupError):
    """Raised when a strategy code/id does not resolve in the catalog."""


def _import_impact_engine() -> Any:
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from impact.monte_carlo import median_projection, projection_bands, run_monte_carlo  # noqa: E402
    from impact.strategy_effects import build_strategy_snapshot  # noqa: E402
    from impact.types import DeductionProfile, ScenarioParams, SimulationSnapshot  # noqa: E402
    from rules.engine import apply_deductions, compute_annual_tax, load_tax_rules  # noqa: E402
    from strategy_gen.catalog import load_strategy_catalog  # noqa: E402

    return (
        run_monte_carlo,
        median_projection,
        projection_bands,
        build_strategy_snapshot,
        DeductionProfile,
        ScenarioParams,
        SimulationSnapshot,
        load_tax_rules,
        apply_deductions,
        compute_annual_tax,
        load_strategy_catalog,
    )


def _catalog_path() -> Any:
    return component_settings.COMP_RECOMMENDATION_RULES_PATH.parent / "strategy_catalog.yaml"


def _strategy_uuid(catalog_id: str) -> UUID:
    return uuid.uuid5(_STRATEGY_UUID_NS, catalog_id)


def _normalize_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper()


def _resolve_catalog_strategy(
    *,
    strategy_code: str | None,
    strategy_id: UUID | None,
) -> Any:
    (
        _run,
        _med,
        _bands,
        _build_snap,
        _DeductionProfile,
        _ScenarioParams,
        _SimulationSnapshot,
        _load_rules,
        _apply,
        _compute,
        load_strategy_catalog,
    ) = _import_impact_engine()

    catalog = load_strategy_catalog(_catalog_path())

    if strategy_code:
        needle = _normalize_code(strategy_code)
        for s in catalog.strategies:
            if _normalize_code(s.strategy_id) == needle or needle in _normalize_code(s.strategy_id):
                return s
        raise StrategyNotFoundError(f"Unknown strategy_code: {strategy_code}")

    if strategy_id is not None:
        for s in catalog.strategies:
            if _strategy_uuid(s.strategy_id) == strategy_id:
                return s
        raise StrategyNotFoundError(f"Unknown strategy_id: {strategy_id}")

    return None


def _build_context(profile: FinancialProfileORM) -> dict[str, Any]:
    derived = compute_derived_features(profile)
    return {
        "annual_income": float(derived.gross_annual_taxable_income),
        "annual_tax_before_strategy": float(derived.baseline_tax_liability_annual),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "health_insurance_premium_annual_lkr": 15_000.0 if profile.health_insurance else 0.0,
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "rent_paid_annual_lkr": 0.0,
        "retirement_contribution_annual_lkr": 0.0,
    }


def _snapshot_from_profile(profile: FinancialProfileORM, ctx: dict[str, Any]) -> Any:
    (
        _run,
        _med,
        _bands,
        _build_snap,
        DeductionProfile,
        _ScenarioParams,
        SimulationSnapshot,
        _load_rules,
        _apply,
        _compute,
        _load_catalog,
    ) = _import_impact_engine()

    baseline = DeductionProfile(
        rent_paid_annual=float(ctx.get("rent_paid_annual_lkr", 0.0)),
        life_insurance_premium_annual=float(ctx.get("life_insurance_premium_annual_lkr", 0.0)),
        health_insurance_premium_annual=float(ctx.get("health_insurance_premium_annual_lkr", 0.0)),
        home_loan_interest_annual=float(ctx.get("home_loan_interest_annual_lkr", 0.0)),
        donations_annual=float(ctx.get("donations_annual_lkr", 0.0)),
        retirement_contribution_annual=float(ctx.get("retirement_contribution_annual_lkr", 0.0)),
    )
    derived = compute_derived_features(profile)
    return SimulationSnapshot(
        annual_income=float(derived.gross_annual_taxable_income),
        monthly_expenses=float(profile.monthly_expenses),
        monthly_debt_service=float(profile.monthly_debt_service),
        liquid_savings=float(profile.liquid_savings),
        existing_investments=float(profile.existing_investments),
        baseline_deductions=baseline,
        strategy_deductions=None,
    )


def _scenario_params(scenario: Scenario) -> Any:
    (
        _run,
        _med,
        _bands,
        _build_snap,
        _DeductionProfile,
        ScenarioParams,
        _SimulationSnapshot,
        _load_rules,
        _apply,
        _compute,
        _load_catalog,
    ) = _import_impact_engine()
    return ScenarioParams(
        name=scenario.name,
        salary_growth_mean=scenario.salary_growth_mean,
        salary_growth_std=scenario.salary_growth_std,
        inflation_mean=scenario.inflation_mean,
        investment_return_mean=scenario.investment_return_mean,
        adoption_success_prob=scenario.adoption_success_prob,
    )


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def _yearly_projections(rows: list[dict[str, float]]) -> list[YearlyProjection]:
    return [
        YearlyProjection(
            year=int(r["year"]),
            projected_salary=_to_decimal(r["projected_salary"]),
            projected_tax_liability=_to_decimal(r["projected_tax_liability"]),
            projected_savings=_to_decimal(r["projected_savings"]),
            net_worth=_to_decimal(r["net_worth"]),
        )
        for r in rows
    ]


def _projection_bands(rows: list[dict[str, float]]) -> list[ProjectionBand]:
    return [
        ProjectionBand(
            year=int(r["year"]),
            p10=_to_decimal(r["p10"]),
            p50=_to_decimal(r["p50"]),
            p90=_to_decimal(r["p90"]),
        )
        for r in rows
    ]


def _response_from_result(
    *,
    profile_id: UUID,
    catalog_strategy_id: str | None,
    request: ImpactSimulationRequest,
    result: Any,
) -> ImpactSimulationResponse:
    (
        _run,
        median_projection,
        projection_bands,
        _build_snap,
        _DeductionProfile,
        _ScenarioParams,
        _SimulationSnapshot,
        _load_rules,
        _apply,
        _compute,
        _load_catalog,
    ) = _import_impact_engine()

    baseline_rows = median_projection(result.baseline_paths)
    strategy_rows = (
        median_projection(result.strategy_paths) if result.strategy_paths is not None else None
    )
    band_source = result.strategy_paths if result.strategy_paths is not None else result.baseline_paths

    summary = ImpactSummary(
        horizon_years=request.horizon_years,
        expected_total_savings=_to_decimal(result.summary["expected_total_savings"]),
        expected_net_worth=_to_decimal(result.summary["expected_net_worth"]),
        savings_std=_to_decimal(result.summary["savings_std"]),
        value_at_risk_p10=_to_decimal(result.summary["value_at_risk_p10"]),
        probability_of_net_gain=float(result.summary["probability_of_net_gain"]),
    )

    return ImpactSimulationResponse(
        run_id=uuid4(),
        profile_id=profile_id,
        strategy_id=_strategy_uuid(catalog_strategy_id) if catalog_strategy_id else None,
        horizon_years=request.horizon_years,
        n_paths=request.n_paths,
        baseline=_yearly_projections(baseline_rows),
        strategy_path=_yearly_projections(strategy_rows) if strategy_rows else None,
        net_worth_bands=_projection_bands(projection_bands(band_source, field="net_worth")),
        tax_liability_bands=_projection_bands(projection_bands(band_source, field="tax_liability")),
        summary=summary,
    )


def simulate_impact(db: Session, payload: ImpactSimulationRequest) -> ImpactSimulationResponse:
    """Run Monte Carlo impact simulation for a profile and optional strategy."""
    try:
        profile = get_profile(db, payload.profile_id)
    except ProfileNotFoundError as exc:
        raise exc

    strategy = _resolve_catalog_strategy(
        strategy_code=payload.strategy_code,
        strategy_id=payload.strategy_id,
    )

    (
        run_monte_carlo,
        _median_projection,
        _projection_bands,
        build_strategy_snapshot,
        _DeductionProfile,
        _ScenarioParams,
        _SimulationSnapshot,
        load_tax_rules,
        apply_deductions,
        compute_annual_tax,
        _load_catalog,
    ) = _import_impact_engine()

    ctx = _build_context(profile)
    snapshot = _snapshot_from_profile(profile, ctx)
    rules = load_tax_rules(component_settings.COMP_RECOMMENDATION_RULES_PATH)

    catalog_id: str | None = None
    if strategy is not None:
        catalog_id = strategy.strategy_id
        snapshot = build_strategy_snapshot(
            strategy_id=strategy.strategy_id,
            estimation_type=strategy.estimation_method.type,
            context=ctx,
            rules=rules,
            snapshot=snapshot,
        )

    try:
        result = run_monte_carlo(
            snapshot,
            horizon_years=payload.horizon_years,
            n_paths=payload.n_paths,
            scenario=_scenario_params(payload.scenario),
            rules=rules,
            apply_deductions=apply_deductions,
            compute_annual_tax=compute_annual_tax,
            random_seed=payload.random_seed,
            include_strategy_paths=strategy is not None,
        )
    except Exception as exc:
        raise ImpactSimulationError(f"Simulation failed: {exc}") from exc

    return _response_from_result(
        profile_id=payload.profile_id,
        catalog_strategy_id=catalog_id,
        request=payload,
        result=result,
    )


def compare_strategies(db: Session, payload: StrategyComparisonRequest) -> list[ImpactSimulationResponse]:
    """Compare multiple strategies for the same profile."""
    codes = payload.strategy_codes or []
    if not codes and not payload.strategy_ids:
        raise ImpactSimulationError("Provide strategy_codes or strategy_ids")

    results: list[ImpactSimulationResponse] = []
    for code in codes:
        req = ImpactSimulationRequest(
            profile_id=payload.profile_id,
            strategy_code=code,
            horizon_years=payload.horizon_years,
            n_paths=component_settings.COMP_RECOMMENDATION_DEFAULT_MC_PATHS,
        )
        results.append(simulate_impact(db, req))

    for sid in payload.strategy_ids:
        req = ImpactSimulationRequest(
            profile_id=payload.profile_id,
            strategy_id=sid,
            horizon_years=payload.horizon_years,
            n_paths=component_settings.COMP_RECOMMENDATION_DEFAULT_MC_PATHS,
        )
        results.append(simulate_impact(db, req))

    return results


__all__ = [
    "ImpactSimulationError",
    "StrategyNotFoundError",
    "compare_strategies",
    "simulate_impact",
]
