"""Resolve audit-risk penalties and alignment for recommendation fusion."""

from __future__ import annotations

import sys
from typing import Any

from app.config import component_settings


def _import_risk_scoring() -> Any:
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from ranking import risk_scoring  # noqa: E402

    return risk_scoring


def resolve_risk_tolerance(*, profile_tolerance: str, override: str | None = None) -> str:
    risk_scoring = _import_risk_scoring()
    if override:
        return risk_scoring.normalize_risk_level(override)
    return risk_scoring.normalize_risk_level(profile_tolerance)


def compute_strategy_risk_penalty(
    *,
    strategy_audit_risk: str,
    user_risk_tolerance: str,
) -> tuple[float, str]:
    """Return (fusion penalty 0–1, normalized strategy audit-risk level)."""
    risk_scoring = _import_risk_scoring()
    level = risk_scoring.normalize_risk_level(strategy_audit_risk)
    score = risk_scoring.compute_risk_penalty(
        strategy_audit_risk=level,
        user_risk_tolerance=user_risk_tolerance,
    )
    return score, level


def compute_strategy_risk_bundle(
    *,
    strategy_audit_risk: str,
    user_risk_tolerance: str,
) -> tuple[float, str, float]:
    """Return (penalty, audit level, alignment score 0–1)."""
    risk_scoring = _import_risk_scoring()
    level = risk_scoring.normalize_risk_level(strategy_audit_risk)
    penalty = risk_scoring.compute_risk_penalty(
        strategy_audit_risk=level,
        user_risk_tolerance=user_risk_tolerance,
    )
    alignment = risk_scoring.risk_alignment_score(
        strategy_audit_risk=level,
        user_risk_tolerance=user_risk_tolerance,
    )
    return penalty, level, alignment


__all__ = [
    "compute_strategy_risk_bundle",
    "compute_strategy_risk_penalty",
    "resolve_risk_tolerance",
]
