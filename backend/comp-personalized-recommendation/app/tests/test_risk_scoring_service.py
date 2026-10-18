"""Tests for strategy audit-risk penalty resolution."""

from __future__ import annotations

from app.services.risk_scoring_service import compute_strategy_risk_penalty, resolve_risk_tolerance


def test_resolve_risk_tolerance_prefers_override() -> None:
    assert resolve_risk_tolerance(profile_tolerance="medium", override="high") == "high"


def test_low_strategy_for_conservative_taxpayer() -> None:
    score, level = compute_strategy_risk_penalty(
        strategy_audit_risk="low",
        user_risk_tolerance="low",
    )
    assert level == "low"
    assert score == 0.0875


def test_high_strategy_penalized_for_conservative_taxpayer() -> None:
    score, level = compute_strategy_risk_penalty(
        strategy_audit_risk="high",
        user_risk_tolerance="low",
    )
    assert level == "high"
    assert score > 0.4
