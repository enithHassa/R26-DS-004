"""Classifier must not 500 when DistilBERT / TF-IDF artifacts are absent."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.semantic_classifier import (
    UnavailableSemanticClassifier,
    get_semantic_classifier,
    reset_semantic_classifier_for_tests,
)
from app.services.transaction_analyzer import (
    TransactionAnalyzeInput,
    analyze_transactions_batch,
)
from backend.shared.db.enums import TxnDirection


def test_get_classifier_never_raises_without_artifacts() -> None:
    reset_semantic_classifier_for_tests()
    classifier = get_semantic_classifier()
    # With or without local artifacts, classify callers always get a usable object.
    assert hasattr(classifier, "predict_many")
    preds = classifier.predict_many(["random merchant purchase"])
    assert len(preds) == 1
    assert preds[0].label


def test_analyze_batch_succeeds_without_ml_artifacts() -> None:
    reset_semantic_classifier_for_tests()
    tx_date = date(2025, 12, 15)
    results = analyze_transactions_batch(
        [
            TransactionAnalyzeInput(
                raw_desc="200280055988:WTax.Pd:01-12-2025to 31-12-2025",
                amount_lkr=Decimal("115.00"),
                tx_date=tx_date,
                direction=TxnDirection.DR,
            ),
            TransactionAnalyzeInput(
                raw_desc="Int.Pd: savings interest",
                amount_lkr=Decimal("2310.00"),
                tx_date=tx_date,
                direction=TxnDirection.CR,
            ),
            TransactionAnalyzeInput(
                raw_desc="POS PURCHASE KEELLS SUPERMARKET",
                amount_lkr=Decimal("4500.00"),
                tx_date=tx_date,
                direction=TxnDirection.DR,
            ),
        ],
        bank_code="COMBANK",
    )
    assert len(results) == 3
    assert results[0].semantic_category == "withholding_tax"
    assert results[1].semantic_category == "interest_income"
    # Ambiguous rows may be model or unavailable→unknown; must not crash.
    assert results[2].semantic_category in {"personal_spend", "unknown", "bank_charge"}


def test_unavailable_classifier_predicts_unknown() -> None:
    clf = UnavailableSemanticClassifier(reason="test")
    pred = clf.predict("anything")
    assert pred.label == "unknown"
    assert pred.model_key == "unavailable"
