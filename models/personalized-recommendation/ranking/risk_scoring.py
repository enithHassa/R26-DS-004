"""Audit-risk scoring for strategy ranking fusion (Component 3).

Penalties are on a 0–1 scale and multiplied by ``w_risk_penalty`` (default 10%)
in the fusion formula. Bands follow common tax-advisory practice:

- **LOW (0.05)** — established statutory reliefs with clear IRD guidance
- **MEDIUM (0.12)** — substantiation required; moderate audit scrutiny
- **HIGH (0.20)** — complex or timing-sensitive planning; higher dispute risk

``risk_alignment_score`` (0–1) rewards strategies whose audit-risk band matches
the active taxpayer risk view. Together with tolerance sensitivity multipliers,
auditor overrides produce visible rank and penalty changes.
"""

from __future__ import annotations

AUDIT_RISK_LEVELS: frozenset[str] = frozenset({"low", "medium", "high"})

AUDIT_RISK_SCORES: dict[str, float] = {
    "low": 0.05,
    "medium": 0.12,
    "high": 0.20,
}

TOLERANCE_ORDINAL: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

# Amplify/dampen all penalties for the active risk view (auditor override uses this).
TOLERANCE_SENSITIVITY: dict[str, float] = {
    "low": 1.75,
    "medium": 1.0,
    "high": 0.55,
}

MISMATCH_STEP = 0.04
MAX_MISMATCH_ADDON = 0.08

# Alignment drops 0.35 per ordinal step away from taxpayer comfort.
ALIGNMENT_STEP = 0.35
MIN_ALIGNMENT = 0.15


def normalize_risk_level(raw: str | None, *, default: str = "medium") -> str:
    level = str(raw or default).strip().lower()
    if level not in AUDIT_RISK_LEVELS:
        return default
    return level


def risk_alignment_score(*, strategy_audit_risk: str, user_risk_tolerance: str) -> float:
    """1.0 when strategy audit band matches taxpayer comfort; lower when mismatched."""
    strat_level = normalize_risk_level(strategy_audit_risk)
    user_level = normalize_risk_level(user_risk_tolerance)
    gap = abs(TOLERANCE_ORDINAL[strat_level] - TOLERANCE_ORDINAL[user_level])
    return round(max(MIN_ALIGNMENT, 1.0 - gap * ALIGNMENT_STEP), 6)


def compute_risk_penalty(
    *,
    strategy_audit_risk: str,
    user_risk_tolerance: str,
) -> float:
    """Combined fusion penalty for one profile×strategy pair."""
    strat_level = normalize_risk_level(strategy_audit_risk)
    user_level = normalize_risk_level(user_risk_tolerance)

    base = AUDIT_RISK_SCORES[strat_level]
    gap = max(0, TOLERANCE_ORDINAL[strat_level] - TOLERANCE_ORDINAL[user_level])
    mismatch = min(MAX_MISMATCH_ADDON, gap * MISMATCH_STEP)
    raw = min(1.0, base + mismatch)
    sensitivity = TOLERANCE_SENSITIVITY[user_level]
    return round(min(1.0, raw * sensitivity), 6)


__all__ = [
    "AUDIT_RISK_LEVELS",
    "AUDIT_RISK_SCORES",
    "TOLERANCE_SENSITIVITY",
    "compute_risk_penalty",
    "normalize_risk_level",
    "risk_alignment_score",
]
