"""Unit tests for fixture / OpenAI explain narrators (Phase 4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxResponseV1,
    CalculationTraceStep,
)
from adaptive_tax_app.schemas.evidence import (
    EvidenceBundle,
    EvidenceChunk,
    EvidenceSourceQuote,
)
from adaptive_tax_app.schemas.explain import (
    DISCLAIMER,
    ExplainNarrativePayload,
    ExplainStepV1,
    ExplainTaxRequestV1,
)
from adaptive_tax_app.services.chroma_index import RagHit
from adaptive_tax_app.services.explain import explain_tax
from adaptive_tax_app.services.gpt_explain import (
    build_fixture_narrative,
    filter_sections_cited,
    load_explain_fixture,
    sanitize_narrative_payload,
)


def _calc() -> CalculateTaxResponseV1:
    return CalculateTaxResponseV1(
        final_tax_lkr="0",
        calc_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="Sum assessable income",
                formula="sum(...)",
                output="3000000",
                section_uids=["ird-ira-2017-base::sec::section_5"],
            ),
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="Apply QP",
                formula="min(claimed, cap)",
                output="1200000",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            ),
            CalculationTraceStep(
                step_id="final_tax",
                description="Total tax",
                formula="sum(slabs)",
                output="0",
                section_uids=["ird-ira-2017-base::sec::first_schedule"],
            ),
        ],
        rules_applied=["sum_assessable", "deduct_qualifying_payment", "final_tax"],
        rule_source_refs=[],
    )


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="chunk-5",
                text="Section 5 employment income",
                section_ref="Section 5",
                source_doc_id="ird-ira-2017-base",
                page=5,
                score=0.9,
            ),
            EvidenceChunk(
                chunk_id="chunk-52",
                text="Section 52 qualifying payments",
                section_ref="Section 52",
                source_doc_id="ird-ira-2017-base",
                page=52,
                score=0.88,
            ),
        ],
        source_quotes=[
            EvidenceSourceQuote(
                rule_source_id="rs-52",
                section="52",
                amends_section="52",
                source_quote="one million eight hundred thousand" + (" word" * 5),
                concept_id="qualifying_payment_cap",
                maximum=1_800_000.0,
                status="approved",
            )
        ],
        sections_retrieved=["Section 5", "Section 52"],
        sections_queried=["Section 5", "Section 52", "First Schedule"],
    )


class _FakeChroma:
    def search(self, query: str, **kwargs):  # noqa: ANN003
        label = query
        if "52" in label:
            cid = "chunk-52"
        elif "Schedule" in label:
            cid = "chunk-fs"
        else:
            cid = "chunk-5"
        return [
            RagHit(
                chunk_id=cid,
                text=f"{label} legal text",
                score=0.9,
                source_doc_id="ird-ira-2017-base",
                section_ref=label,
                page=1,
                metadata={},
            )
        ]


def test_filter_sections_cited_drops_hallucinations() -> None:
    kept, dropped = filter_sections_cited(
        ["Section 5", "Section 99", "Section 52", "Section 5"],
        ["Section 5", "Section 52"],
    )
    assert kept == ["Section 5", "Section 52"]
    assert dropped == ["Section 99"]


def test_sanitize_drops_bad_chunk_and_rule_ids() -> None:
    payload = ExplainNarrativePayload(
        summary="ok",
        sections_cited=["Section 5", "Section 99"],
        steps_explained=[
            ExplainStepV1(
                step_id="sum_assessable",
                narrative="n",
                evidence_chunk_ids=["chunk-5", "fake-chunk"],
                rule_source_id="fake-rs",
            )
        ],
        final_tax_lkr="0",
    )
    cleaned, warnings = sanitize_narrative_payload(
        payload, evidence=_evidence(), final_tax_lkr="0"
    )
    assert cleaned.sections_cited == ["Section 5"]
    assert cleaned.steps_explained[0].evidence_chunk_ids == ["chunk-5"]
    assert cleaned.steps_explained[0].rule_source_id is None
    assert any("hallucinated" in w for w in warnings)
    assert cleaned.disclaimer == DISCLAIMER


def test_fixture_narrative_attaches_evidence_ids() -> None:
    evidence = _evidence()
    from adaptive_tax_app.services.evidence import build_step_evidence_statuses

    calc = _calc()
    evidence.step_evidence = build_step_evidence_statuses(
        calc.calculation_trace, evidence
    )
    result = build_fixture_narrative(calc, evidence)
    assert result.mode == "fixture"
    assert result.payload.final_tax_lkr == "0"
    assert result.payload.sections_cited == ["Section 5", "Section 52"]
    by_id = {s.step_id: s for s in result.payload.steps_explained}
    assert "chunk-5" in by_id["sum_assessable"].evidence_chunk_ids
    assert "chunk-52" in by_id["deduct_qualifying_payment"].evidence_chunk_ids
    assert by_id["deduct_qualifying_payment"].rule_source_id == "rs-52"
    # First Schedule was queried but not retrieved → step gate unavailable
    assert by_id["final_tax"].evidence_unavailable is True
    assert by_id["final_tax"].narrative == "Evidence unavailable for this step"


def test_step_gate_blocks_unrelated_global_chunk() -> None:
    """Sec 52 step must not narrate from a Sec 5-only global pass."""
    from adaptive_tax_app.services.evidence import (
        STEP_EVIDENCE_UNAVAILABLE,
        build_step_evidence_statuses,
    )

    calc = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="Apply QP",
                formula="min",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["deduct_qualifying_payment"],
        rule_source_refs=[],
    )
    evidence = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="chunk-5-only",
                text="Section 5 employment income",
                section_ref="Section 5",
                source_doc_id="ird-ira-2017-base",
                page=5,
                score=0.95,
                is_operative_provision=True,
            )
        ],
        source_quotes=[],
        sections_retrieved=["Section 5"],
        sections_queried=["Section 52"],
    )
    evidence.step_evidence = build_step_evidence_statuses(
        calc.calculation_trace, evidence
    )
    result = build_fixture_narrative(calc, evidence)
    step = result.payload.steps_explained[0]
    assert step.evidence_unavailable is True
    assert step.narrative == STEP_EVIDENCE_UNAVAILABLE
    assert step.evidence_chunk_ids == []


def test_explain_insufficient_evidence_short_circuits() -> None:
    body = ExplainTaxRequestV1(calculation=_calc())

    class EmptyIndex:
        def search(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return []

    out = explain_tax(
        body,
        db=None,
        chroma_index=EmptyIndex(),
        include_graph_modifies=False,
    )
    assert out.insufficient_evidence is True
    assert out.summary == ""
    assert out.steps_explained == []
    assert out.sections_cited == []
    assert out.final_tax_lkr == "0"
    assert out.disclaimer == DISCLAIMER
    assert out.calc_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def test_explain_fixture_mode_with_evidence() -> None:
    body = ExplainTaxRequestV1(calculation=_calc(), calc_id=_calc().calc_id)
    out = explain_tax(
        body,
        db=None,
        chroma_index=_FakeChroma(),
        include_graph_modifies=False,
    )
    assert out.insufficient_evidence is False
    assert out.final_tax_lkr == "0"
    assert out.sections_cited
    assert set(out.sections_cited) <= set(out.sections_retrieved)
    assert out.steps_explained
    assert out.disclaimer == DISCLAIMER


def test_request_requires_calc_id_or_calculation() -> None:
    with pytest.raises(ValidationError):
        ExplainTaxRequestV1()


def test_explain_fixture_json_loads_and_matches_contract() -> None:
    raw = load_explain_fixture()
    assert raw["disclaimer"] == DISCLAIMER
    assert "steps_explained" in raw
    assert raw["insufficient_evidence"] is False
    for key in (
        "summary",
        "sections_cited",
        "steps_explained",
        "final_tax_lkr",
        "disclaimer",
        "insufficient_evidence",
        "sections_retrieved",
        "calc_id",
    ):
        assert key in raw
