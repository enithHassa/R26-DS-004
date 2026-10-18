"""Tests for audit-risk penalty bands and tolerance mismatch."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ranking.risk_scoring import AUDIT_RISK_SCORES, compute_risk_penalty, risk_alignment_score


def test_low_strategy_low_tolerance_uses_sensitivity() -> None:
    score = compute_risk_penalty(strategy_audit_risk="low", user_risk_tolerance="low")
    assert score == round(AUDIT_RISK_SCORES["low"] * 1.75, 6)


def test_high_strategy_low_tolerance_adds_mismatch_and_sensitivity() -> None:
    score = compute_risk_penalty(strategy_audit_risk="high", user_risk_tolerance="low")
    assert score == round((AUDIT_RISK_SCORES["high"] + 0.08) * 1.75, 6)


def test_medium_strategy_high_tolerance_no_mismatch_damped() -> None:
    score = compute_risk_penalty(strategy_audit_risk="medium", user_risk_tolerance="high")
    assert score == round(AUDIT_RISK_SCORES["medium"] * 0.55, 6)


def test_alignment_perfect_match() -> None:
    assert risk_alignment_score(strategy_audit_risk="low", user_risk_tolerance="low") == 1.0


def test_alignment_two_step_mismatch() -> None:
    assert risk_alignment_score(strategy_audit_risk="high", user_risk_tolerance="low") == 0.3
