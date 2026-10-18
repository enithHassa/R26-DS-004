from __future__ import annotations

from app.schemas.query_v1 import Citation
from app.services.answer_confidence import compute_answer_confidence


def test_confidence_empty_citations() -> None:
    score, label = compute_answer_confidence([], validation_status="passed", has_plain_answer=True)
    assert score == 0
    assert label == "No sources"


def test_confidence_rises_with_sources_and_validation() -> None:
    cites = [
        Citation(chunk_id="a", score=0.45, text="Personal relief is Rs. 1,800,000."),
        Citation(chunk_id="b", score=0.40, text="Except trustees..."),
    ]
    low, _ = compute_answer_confidence(cites, validation_status="not_run", has_plain_answer=False)
    high, label = compute_answer_confidence(
        cites, validation_status="passed", has_plain_answer=True
    )
    assert high > low
    assert high >= 60
    assert "confidence" in label.lower() or "grounding" in label.lower()
