"""Unit tests for hybrid fusion ranking (adoption-aware sort order)."""

from __future__ import annotations

from app.services.hybrid_service import _fuse_rank_score


def test_fusion_prefers_high_adoption_when_tax_scores_are_close() -> None:
    weights = {
        "w_savings": 0.40,
        "w_adoption": 0.30,
        "w_feasibility": 0.20,
        "w_risk_penalty": 0.10,
        "w_risk_alignment": 0.12,
    }
    low_adopt = _fuse_rank_score(
        lambdamart_score=0.92,
        adoption_probability=0.003,
        feasibility=1.0,
        risk_penalty=0.1,
        risk_alignment=1.0,
        weights=weights,
    )
    high_adopt = _fuse_rank_score(
        lambdamart_score=0.87,
        adoption_probability=0.99,
        feasibility=1.0,
        risk_penalty=0.1,
        risk_alignment=1.0,
        weights=weights,
    )
    assert high_adopt > low_adopt


def test_fusion_weights_match_phase4_defaults() -> None:
    score = _fuse_rank_score(
        lambdamart_score=1.0,
        adoption_probability=1.0,
        feasibility=1.0,
        risk_penalty=0.0,
        risk_alignment=1.0,
    )
    assert round(score, 2) == 1.02
