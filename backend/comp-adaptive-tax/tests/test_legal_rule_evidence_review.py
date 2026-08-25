"""Phase 11b/11c — LegalRuleEvidence approval stub + explain emission."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxResponseV1,
    CalculationTraceStep,
)
from adaptive_tax_app.schemas.evidence import EvidenceBundle, EvidenceChunk
from adaptive_tax_app.schemas.legal_rule_evidence import LegalRuleEvidence
from adaptive_tax_app.services.evidence import gather_evidence
from adaptive_tax_app.services.legal_rule_evidence_emit import (
    build_candidate_legal_rule_evidence,
    candidate_from_operative_chunk,
)
from adaptive_tax_app.services.legal_rule_evidence_review import (
    DISSERTATION_CLAIM,
    FUTURE_INCORPORATION_NOTE,
    LegalRuleEvidenceReviewError,
    approval_path_documentation,
    approve_candidate,
    clear_review_store,
    incorporate_into_engine_stub,
    reject_candidate,
    submit_candidate,
)
from adaptive_tax_app.services.chroma_index import RagHit


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    clear_review_store()


def test_approval_path_docs_state_current_vs_future() -> None:
    doc = approval_path_documentation()
    assert doc["is_rag_calculation"] is False
    assert doc["current"]["calculate_wiring"] is False
    assert "future" in doc
    assert "does not automatically change the tax calculation" in DISSERTATION_CLAIM.lower()
    assert "validation" in DISSERTATION_CLAIM.lower()


def test_submit_approve_reject_never_marks_executable_or_incorporated() -> None:
    ev = LegalRuleEvidence(
        section="52",
        paragraph_ref="52(4)",
        source_quote=(
            "such amount which cannot be deducted shall be carried forward "
            "to the succeeding year of assessment under section 52."
        ),
        rule_type="carry_forward",
        formula=None,
        cap_value=None,
    )
    rec = submit_candidate(ev)
    assert rec.evidence.status == "needs_review"
    assert rec.evidence.executable is False
    assert rec.incorporated_into_engine is False

    approved = approve_candidate(rec.review_id, reviewer_note="ok for future")
    assert approved.evidence.status == "approved"
    assert approved.evidence.executable is False
    assert approved.incorporated_into_engine is False
    assert FUTURE_INCORPORATION_NOTE.split()[0] in (
        approved.evidence.applicability_note or ""
    )

    # Fresh reject path
    clear_review_store()
    rec2 = submit_candidate(ev)
    rejected = reject_candidate(rec2.review_id, reason="quote incomplete")
    assert rejected.evidence.status == "rejected"
    assert rejected.evidence.executable is False
    assert rejected.incorporated_into_engine is False


def test_incorporate_into_engine_stub_blocked() -> None:
    ev = LegalRuleEvidence(
        section="5",
        source_quote="An individual's income from an employment for a year of assessment.",
        rule_type="definition",
    )
    rec = submit_candidate(ev)
    approve_candidate(rec.review_id)
    assert incorporate_into_engine_stub(rec.review_id) == "blocked_future_only"
    from adaptive_tax_app.services.legal_rule_evidence_review import get_review

    stored = get_review(rec.review_id)
    assert stored is not None
    assert stored.incorporated_into_engine is False
    assert stored.evidence.executable is False


def test_cannot_approve_missing_or_rejected() -> None:
    with pytest.raises(LegalRuleEvidenceReviewError):
        approve_candidate("missing-id")
    ev = LegalRuleEvidence(
        section="52",
        source_quote="Qualifying payments shall be deducted in arriving at taxable income.",
        rule_type="deduction",
    )
    rec = submit_candidate(ev)
    reject_candidate(rec.review_id, reason="no")
    with pytest.raises(LegalRuleEvidenceReviewError, match="rejected"):
        approve_candidate(rec.review_id)


def test_candidate_from_operative_chunk_null_caps() -> None:
    chunk = EvidenceChunk(
        chunk_id="ird-ira-2017-base::p0015::c0001",
        text=(
            "5. (1) An individual's income from an employment for a year of "
            "assessment shall be the individual's gains and profits from that employment."
        ),
        section_ref="Section 5",
        source_doc_id="ird-ira-2017-base",
        is_operative_provision=True,
        paragraph_ref="5(1)",
    )
    cand = candidate_from_operative_chunk(chunk, assessment_year="2025_26")
    assert cand is not None
    assert cand.status == "candidate"
    assert cand.executable is False
    assert cand.cap_value is None
    assert cand.formula is None
    assert cand.section == "5"
    assert cand.source_chunk_ids == [chunk.chunk_id]
    assert "not calculation" in (cand.applicability_note or "").lower()


def test_toc_chunk_does_not_emit_candidate() -> None:
    chunk = EvidenceChunk(
        chunk_id="toc",
        text="52. Qualifying payments and reliefs. 43",
        section_ref="Section 52",
        source_doc_id="ird-ira-2017-base",
        is_toc=True,
        is_operative_provision=False,
    )
    assert candidate_from_operative_chunk(chunk) is None


def test_gather_evidence_attaches_legal_rule_evidence_candidates() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="employment",
                formula="sum",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_5"],
            )
        ],
        rules_applied=["sum_assessable"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="op-5",
            text=(
                "5. (1) An individual's income from an employment for a year of "
                "assessment shall be the individual's gains and profits."
            ),
            score=0.9,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 5",
            page=15,
            metadata={"is_operative_provision": True, "paragraph_ref": "5(1)"},
        )
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2025_26",
        min_score=0.5,
    )
    assert bundle.legal_rule_evidence
    assert all(e.executable is False for e in bundle.legal_rule_evidence)
    assert all(e.status == "candidate" for e in bundle.legal_rule_evidence)
    assert all(e.cap_value is None for e in bundle.legal_rule_evidence)


def test_build_candidates_from_bundle_prefers_step_local_ids() -> None:
    bundle = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="a",
                text="Section 52 (1) qualifying payments aggregate deducted from taxable income.",
                section_ref="Section 52",
                source_doc_id="ird-ira-2017-base",
                is_operative_provision=True,
            ),
            EvidenceChunk(
                chunk_id="b",
                text="Section 5 employment income gains and profits from an employment.",
                section_ref="Section 5",
                source_doc_id="ird-ira-2017-base",
                is_operative_provision=True,
            ),
        ],
        step_evidence=[],
    )
    from adaptive_tax_app.schemas.evidence import StepEvidenceStatus

    bundle.step_evidence = [
        StepEvidenceStatus(
            step_id="s",
            evidence_available=True,
            evidence_chunk_ids=["b"],
        )
    ]
    cands = build_candidate_legal_rule_evidence(bundle, assessment_year="2024_25")
    assert cands
    assert cands[0].source_chunk_ids[0] == "b"
