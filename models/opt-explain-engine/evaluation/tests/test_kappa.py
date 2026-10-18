"""Tests for OE Engine Cohen's kappa evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from kappa import compute_kappa, interpret_kappa, kappa_from_csv  # noqa: E402

FIXTURES = EVAL_DIR / "fixtures"


def test_perfect_agreement_is_one() -> None:
    result = compute_kappa(["claim", "do_not_claim"], ["claim", "do_not_claim"])
    assert result.cohen_kappa == 1.0


def test_sample_reliefs_csv_runs() -> None:
    result = kappa_from_csv(FIXTURES / "kappa_sample_reliefs.csv")
    assert result.n_pairs == 20
    assert -1.0 <= result.cohen_kappa <= 1.0
    assert "claim" in result.labels


def test_forty_taxpayer_demo_shows_meaningful_disagreement() -> None:
    result = kappa_from_csv(FIXTURES / "kappa_40_taxpayers.csv")
    assert result.n_pairs == 160  # 40 users × 4 relief decisions
    assert 0.4 <= result.cohen_kappa <= 0.95
    assert result.observed_agreement < 1.0
    assert result.observed_agreement > 0.7


def test_interpret_bands() -> None:
    assert "substantial" in interpret_kappa(0.70)
