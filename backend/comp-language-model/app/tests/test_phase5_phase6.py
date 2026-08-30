from __future__ import annotations

import pytest

from app.config import get_lm_settings
from app.services.lex_rank import lex_specialis_boost, rerank_hits
from app.services.proof_map import build_proof_map
from app.services.query_preprocess import normalize_query
from app.services.symbolic_engine import validate_advisory_text
from app.services.think_twice import apply_think_twice


def test_normalize_query_singlish() -> None:
    assert "freelance" in normalize_query("Is my free lance income taxable?")


def test_lex_specialis_boost_tier_a() -> None:
    assert lex_specialis_boost({"tier": "A", "instrument_type": "act"}) > lex_specialis_boost(
        {"tier": "C", "instrument_type": "hub_summary"}
    )


def test_rerank_prefers_tier_a(monkeypatch: pytest.MonkeyPatch) -> None:
    join = {
        "low": {"tier": "C", "instrument_type": "guide"},
        "high": {"tier": "A", "instrument_type": "act"},
    }
    hits = rerank_hits([("low", 0.9), ("high", 0.85)], join)
    assert hits[0][0] == "high"


def test_symbolic_rejects_wrong_personal_relief() -> None:
    text = "Personal relief for 2025_26 is LKR 500,000 for all residents."
    result = validate_advisory_text(text, assessment_year_hint="2025_26")
    assert not result.passed
    assert any(i.code == "personal_relief_mismatch" for i in result.issues)


def test_symbolic_accepts_correct_personal_relief() -> None:
    text = "Personal relief for 2025_26 is LKR 1,800,000."
    result = validate_advisory_text(text, assessment_year_hint="2025_26")
    assert result.passed


def test_think_twice_corrects_bad_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    get_lm_settings.cache_clear()
    settings = get_lm_settings()
    monkeypatch.setattr(settings, "COMP_LLM_THINK_TWICE_ENABLED", True)
    bad = "Personal relief for 2025_26 is LKR 500,000."
    out = apply_think_twice(settings, bad, assessment_year_hint="2025_26")
    assert out.corrected
    assert out.validation_status == "corrected"
    assert out.answer_text is not None
    assert "symbolic validation" in out.answer_text.lower()


def test_proof_map_includes_evidence_steps() -> None:
    from app.schemas.query_v1 import Citation

    citations = [
        Citation(
            chunk_id="c1",
            score=0.8,
            text="Personal relief statute excerpt.",
            source_doc_id="ird-act",
            section_uid="ird-act::sec::1",
            section_label="Section 1",
            tier="A",
            instrument_type="act",
            content_kind="text",
        )
    ]
    proof = build_proof_map(
        question="What is personal relief?",
        normalized_question="What is personal relief?",
        retrieval_model="tfidf-baseline",
        citations=citations,
        graph_context=None,
        validation=None,
        validation_status="not_run",
        plain_answer=None,
    )
    kinds = {s.kind for s in proof.steps}
    assert "user_query" in kinds
    assert "retrieval" in kinds
    assert "evidence" in kinds
    assert len(proof.evidence_refs) == 1


def test_symbolic_accepts_valid_wht_rate() -> None:
    text = "Withholding tax of 14% applies to dividend payments."
    result = validate_advisory_text(text)
    assert result.passed
    assert not any(i.code == "wht_rate_unrecognised" for i in result.issues)


def test_symbolic_warns_invalid_wht_rate() -> None:
    text = "Withholding tax of 25% applies to this payment."
    result = validate_advisory_text(text)
    assert any(i.code == "wht_rate_unrecognised" for i in result.issues)


def test_symbolic_rate_cap_exceeded() -> None:
    text = "The marginal tax rate is 45% for the highest band."
    result = validate_advisory_text(text)
    assert not result.passed
    assert any(i.code == "rate_exceeds_cap" for i in result.issues)
