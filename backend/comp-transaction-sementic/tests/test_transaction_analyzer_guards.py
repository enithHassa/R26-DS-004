"""Guardrails for risky internal-transfer predictions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
C1_ROOT = Path(__file__).resolve().parents[1]
for path in (str(REPO_ROOT), str(C1_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.semantic_classifier import SemanticPrediction
from app.services.transaction_analyzer import apply_classification_guards


def _prediction(label: str, confidence: float = 0.95) -> SemanticPrediction:
    return SemanticPrediction(
        label=label,
        confidence=confidence,
        model_key="distilbert_multilingual",
        model_version="distilbert_multilingual/v0.1.0",
        probabilities={label: confidence},
    )


@pytest.mark.parametrize(
    ("description", "confidence"),
    [
        ("CEFTS (S456878)", 0.99),
        ("FriMi ATM Withdrawal - GAMPAHA", 0.99),
        ("UBER EATS CBH LKA", 0.99),
        ("Transfer from SW to FriMi", 0.99),
    ],
)
def test_internal_transfer_without_own_account_evidence_routes_to_review(
    description: str,
    confidence: float,
) -> None:
    guarded, notes = apply_classification_guards(
        _prediction("inter_account_transfer", confidence),
        raw_desc=description,
    )
    assert guarded.label == "unknown"
    assert notes


def test_confirmed_internal_transfer_keeps_label() -> None:
    guarded, notes = apply_classification_guards(
        _prediction("inter_account_transfer", 0.70),
        raw_desc="Fund transfer from FriMi to Round up account",
    )
    assert guarded.label == "inter_account_transfer"
    assert notes == []


def test_noisy_numeric_description_routes_to_review() -> None:
    guarded, notes = apply_classification_guards(
        _prediction("inter_account_transfer", 0.99),
        raw_desc="0020122050016019840040129000500600100",
    )
    assert guarded.label == "unknown"
    assert notes
