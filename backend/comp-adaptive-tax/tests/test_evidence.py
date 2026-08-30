"""Unit tests for Phase 4 evidence gatherer (section map + RAG/PG/Neo4j)."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from adaptive_tax_app.db_loader import RuleSourceStatus, RuleType
from adaptive_tax_app.schemas.calculate import (
    CalculateTaxResponseV1,
    CalculationTraceStep,
    RuleSourceRef,
)
from adaptive_tax_app.schemas.evidence import EvidenceBundle, EvidenceChunk
from adaptive_tax_app.services.chroma_index import RagHit
from adaptive_tax_app.services.evidence import (
    collect_section_uids,
    gather_evidence,
    has_insufficient_evidence,
    section_ref_matches,
    section_uid_to_label,
)


def test_section_uid_to_label_known_slugs() -> None:
    assert (
        section_uid_to_label("ird-ira-2017-base::sec::section_52") == "Section 52"
    )
    assert section_uid_to_label("ird-ira-2017-base::sec::section_5") == "Section 5"
    assert (
        section_uid_to_label("ird-ira-2017-base::sec::first_schedule")
        == "First Schedule"
    )


def test_section_ref_matches_digit_aware() -> None:
    assert section_ref_matches("Section 52", "Section 52")
    assert section_ref_matches("Section 5 | Part II", "Section 5")
    assert not section_ref_matches("Section 52", "Section 5")
    assert section_ref_matches("First Schedule", "First Schedule")
    assert not section_ref_matches("Section 5", "First Schedule")


def test_collect_section_uids_from_response() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="sum",
                formula="sum",
                output="3000000",
                section_uids=["ird-ira-2017-base::sec::section_5"],
            ),
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="qp",
                formula="min",
                output="1200000",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            ),
        ],
        rules_applied=["sum_assessable"],
        rule_source_refs=[
            RuleSourceRef(
                id="personal_relief",
                kind="relief",
                section_uid="ird-ira-2017-base::sec::first_schedule",
            )
        ],
    )
    uids = collect_section_uids(resp)
    assert uids[0].endswith("section_5")
    assert any(u.endswith("section_52") for u in uids)
    assert any(u.endswith("first_schedule") for u in uids)


def test_gather_evidence_empty_when_no_sources() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="sum",
                formula="sum",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["sum_assessable"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = []
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        db=None,
        include_graph_modifies=False,
    )
    assert isinstance(bundle, EvidenceBundle)
    assert bundle.sections_queried == ["Section 52"]
    assert bundle.chunks == []
    assert bundle.source_quotes == []
    assert has_insufficient_evidence(bundle)
    assert bundle.insufficient_evidence is True


def test_gather_evidence_chroma_chunks_and_sections_retrieved() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="qp",
                formula="min",
                output="1800000",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["deduct_qualifying_payment"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="c-52",
            text="Qualifying payments under Section 52 …",
            score=0.91,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=40,
            metadata={},
        ),
        RagHit(
            chunk_id="c-5-noise",
            text="Employment income Section 5",
            score=0.5,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 5",
            page=10,
            metadata={},
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
    )
    assert len(bundle.chunks) == 1
    assert bundle.chunks[0].chunk_id == "c-52"
    assert bundle.sections_retrieved == ["Section 52"]
    assert not has_insufficient_evidence(bundle)
    index.search.assert_called()
    # Step-aware query includes section label + step description
    assert "Section 52" in index.search.call_args.args[0]
    assert "qp" in index.search.call_args.args[0]


def test_gather_evidence_postgres_quotes() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="cap",
                description="cap",
                formula="cap",
                output="1800000",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["cap"],
        rule_source_refs=[],
    )
    rule_id = uuid.uuid4()
    job_id = uuid.uuid4()
    row = MagicMock()
    row.id = rule_id
    row.section = "52"
    row.amends_section = "52"
    row.source_quote = "one million eight hundred thousand" + (" x" * 10)
    row.concept_id = "qualifying_payment_cap"
    row.maximum = 1_800_000.0
    row.status = RuleSourceStatus.APPROVED
    row.amendment_job_id = job_id
    row.effective_date = date(2025, 4, 1)
    row.rule_type = RuleType.LIMIT

    db = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [row]
    db.scalars.return_value = scalars

    index = MagicMock()
    index.search.return_value = []

    bundle = gather_evidence(
        resp,
        chroma_index=index,
        db=db,
        include_graph_modifies=False,
    )
    assert len(bundle.source_quotes) == 1
    assert bundle.source_quotes[0].rule_source_id == str(rule_id)
    assert bundle.source_quotes[0].section == "52"
    assert "Section 52" in bundle.sections_retrieved
    assert not has_insufficient_evidence(bundle)


def test_gather_evidence_graph_modifies_optional() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="cap",
                description="cap",
                formula="cap",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["cap"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = []

    session = MagicMock()
    session.run.return_value.data.return_value = [
        {
            "amendment_source_doc_id": "ird-amend-2025-02",
            "section_uid": "ird-ira-2017-base::sec::section_52",
            "section_label": "Section 52",
            "source_note": "cap raised",
            "effective_from": "2025-04-01",
        }
    ]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False

    with patch(
        "adaptive_tax_app.services.kg_client.open_neo4j_driver",
        return_value=driver,
    ):
        bundle = gather_evidence(resp, chroma_index=index, include_graph_modifies=True)

    assert len(bundle.graph_modifies) == 1
    assert bundle.graph_modifies[0].amendment_source_doc_id == "ird-amend-2025-02"
    # Still insufficient for GPT (no chunks/quotes)
    assert has_insufficient_evidence(bundle)


def test_gather_evidence_neo4j_down_returns_empty_modifies() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="cap",
                description="cap",
                formula="cap",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["cap"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="c1",
            text="Section 52 text",
            score=0.8,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=1,
            metadata={},
        )
    ]
    with patch(
        "adaptive_tax_app.services.kg_client.open_neo4j_driver",
        side_effect=RuntimeError("NEO4J_PASSWORD is not set"),
    ):
        bundle = gather_evidence(resp, chroma_index=index, include_graph_modifies=True)
    assert bundle.graph_modifies == []
    assert not has_insufficient_evidence(bundle)


def test_legal_precedence_ya_beats_raw_similarity() -> None:
    """Wrong-YA higher score must not beat correct-YA lower score."""
    from adaptive_tax_app.services.legal_authority import load_doc_authority_table

    load_doc_authority_table.cache_clear()

    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="qp",
                formula="min",
                output="1800000",
                section_uids=["ird-ira-2017-base::sec::section_52"],
                inputs={"assessment_year": "2024_25"},
            )
        ],
        rules_applied=["deduct_qualifying_payment"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="wrong-ya-high",
            text="Section 52 qualifying payments (amendment 2025)",
            score=0.70,
            source_doc_id="ird-amend-2025-02",
            section_ref="Section 52",
            page=1,
            metadata={"instrument_type": "amendment_act"},
        ),
        RagHit(
            chunk_id="correct-ya-lower",
            text="Section 52 qualifying payments (base Act)",
            score=0.62,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=40,
            metadata={"instrument_type": "base_act"},
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2024_25",
        min_score=0.50,
    )
    assert len(bundle.chunks) >= 1
    assert bundle.chunks[0].chunk_id == "correct-ya-lower"
    assert bundle.chunks[0].legal_precedence_tier is not None
    assert bundle.chunks[0].legal_precedence_tier < 90


def test_legal_precedence_paragraph_beats_section_only() -> None:
    from adaptive_tax_app.services.legal_authority import load_doc_authority_table

    load_doc_authority_table.cache_clear()

    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="carry_forward",
                description="Sec 52(4) carry-forward",
                formula="cf",
                output="0",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["carry_forward"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="sec52-generic",
            text="Section 52 qualifying payments aggregate.",
            score=0.85,
            source_doc_id="ird-amend-2025-02",
            section_ref="Section 52",
            page=2,
            metadata={"instrument_type": "amendment_act", "paragraph_ref": "52"},
        ),
        RagHit(
            chunk_id="sec52-4",
            text="Section 52(4) carry forward of excess qualifying payment.",
            score=0.66,
            source_doc_id="ird-amend-2025-02",
            section_ref="Section 52",
            page=3,
            metadata={"instrument_type": "amendment_act", "paragraph_ref": "52(4)"},
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2025_26",
        paragraph_ref="52(4)",
        min_score=0.50,
    )
    assert bundle.chunks[0].chunk_id == "sec52-4"


def test_rag_min_score_filters_noise() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="cap",
                description="cap",
                formula="cap",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["cap"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="weak",
            text="Section 52 weak hit",
            score=0.40,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=1,
            metadata={},
        ),
        RagHit(
            chunk_id="ok",
            text="Section 52 ok hit",
            score=0.70,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=2,
            metadata={},
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        min_score=0.55,
    )
    assert [c.chunk_id for c in bundle.chunks] == ["ok"]


def test_infer_paragraph_and_step_aware_query() -> None:
    from adaptive_tax_app.services.evidence import (
        build_step_aware_query,
        infer_paragraph_ref,
    )

    step = CalculationTraceStep(
        step_id="apply_qualifying_payment_brought_forward",
        description="Add qualifying payments brought forward under Sec 52(4)",
        formula="x+y",
        output="1",
        concept_ids=["qualifying_payment_carry_forward"],
        section_uids=["ird-ira-2017-base::sec::section_52"],
    )
    assert infer_paragraph_ref(step) == "52(4)"
    q = build_step_aware_query(label="Section 52", step=step, paragraph_ref="52(4)")
    assert "Section 52" in q
    assert "52(4)" in q
    assert "carry" in q.lower() or "brought" in q.lower()


def test_gather_infers_paragraph_ref_from_trace_description() -> None:
    """Carry-forward step description drives paragraph-prefer ranking without explicit arg."""
    from adaptive_tax_app.services.legal_authority import load_doc_authority_table

    load_doc_authority_table.cache_clear()

    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="apply_qualifying_payment_brought_forward",
                description="Add QP brought forward under Sec 52(4)",
                formula="cf",
                output="0",
                concept_ids=["qualifying_payment_carry_forward"],
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["apply_qualifying_payment_brought_forward"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="sec52-generic",
            text="Section 52 qualifying payments aggregate.",
            score=0.85,
            source_doc_id="ird-amend-2025-02",
            section_ref="Section 52",
            page=2,
            metadata={"instrument_type": "amendment_act", "paragraph_ref": "52"},
        ),
        RagHit(
            chunk_id="sec52-4",
            text="Section 52(4) carry forward of excess qualifying payment.",
            score=0.66,
            source_doc_id="ird-amend-2025-02",
            section_ref="Section 52",
            page=3,
            metadata={
                "instrument_type": "amendment_act",
                "paragraph_ref": "52(4)",
                "is_operative_provision": True,
            },
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2025_26",
        min_score=0.50,
    )
    assert bundle.chunks[0].chunk_id == "sec52-4"
    call_q = index.search.call_args[0][0]
    assert "52(4)" in call_q


def test_bootstrap_section_matched_only() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="cap",
                description="Sec 52 cap",
                formula="cap",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["cap"],
        rule_source_refs=[
            RuleSourceRef(
                id="bootstrap:sec52_cap_2025_26",
                kind="relief",
                section="52",
                section_uid="ird-ira-2017-base::sec::section_52",
                source_quote="one million eight hundred thousand rupees",
                source_doc_id="ird-ira-2017-base",
                status="approved",
            ),
            RuleSourceRef(
                id="bootstrap:section_5_only",
                kind="relief",
                section="5",
                section_uid="ird-ira-2017-base::sec::section_5",
                source_quote="employment income means",
                source_doc_id="ird-ira-2017-base",
                status="approved",
            ),
        ],
    )
    index = MagicMock()
    index.search.return_value = []
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2025_26",
    )
    assert not has_insufficient_evidence(bundle)
    ids = {q.rule_source_id for q in bundle.source_quotes}
    assert "bootstrap:sec52_cap_2025_26" in ids
    assert "bootstrap:section_5_only" not in ids
    assert all(q.status == "bootstrap" for q in bundle.source_quotes)
    assert bundle.step_evidence
    assert bundle.step_evidence[0].evidence_available is True


def test_step_evidence_gate_status_on_bundle() -> None:
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="sum_assessable",
                description="employment",
                formula="sum",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_5"],
            ),
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="qp",
                formula="min",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            ),
        ],
        rules_applied=["sum_assessable", "deduct_qualifying_payment"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="only-5",
            text="Section 5 employment",
            score=0.9,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 5",
            page=1,
            metadata={"is_operative_provision": True},
        )
    ]
    bundle = gather_evidence(
        resp, chroma_index=index, include_graph_modifies=False, min_score=0.5
    )
    by_id = {s.step_id: s for s in bundle.step_evidence}
    assert by_id["sum_assessable"].evidence_available is True
    assert by_id["deduct_qualifying_payment"].evidence_available is False


def test_citation_support_prefers_topical_operative_over_string_match() -> None:
    """Containing 'Section 52' is not enough — need operative + topical support."""
    from adaptive_tax_app.services.evidence import (
        STEP_EVIDENCE_UNAVAILABLE,
        build_step_evidence_statuses,
        local_evidence_for_step,
    )
    from adaptive_tax_app.services.gpt_explain import build_fixture_narrative
    from adaptive_tax_app.services.legal_authority import load_doc_authority_table

    load_doc_authority_table.cache_clear()

    step = CalculationTraceStep(
        step_id="apply_qualifying_payment_brought_forward",
        description="Add QP brought forward under Sec 52(4)",
        formula="cf",
        output="0",
        concept_ids=["qualifying_payment_carry_forward"],
        section_uids=["ird-ira-2017-base::sec::section_52"],
    )
    resp = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[step],
        rules_applied=["apply_qualifying_payment_brought_forward"],
        rule_source_refs=[],
    )
    index = MagicMock()
    index.search.return_value = [
        RagHit(
            chunk_id="toc-only",
            text="52. Qualifying payments and reliefs. 43 Division II",
            score=0.92,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 52",
            page=4,
            metadata={"is_toc": True, "is_operative_provision": False},
        ),
        RagHit(
            chunk_id="string-only",
            text="See also Section 52 of the Act for reliefs.",
            score=0.80,
            source_doc_id="ird-ira-2017-base",
            section_ref="Section 5",
            page=10,
            metadata={"is_operative_provision": True},
        ),
        RagHit(
            chunk_id="carry-op",
            text="Section 52(4) qualifying payment which is not possible to be deducted shall be carried forward.",
            score=0.61,
            source_doc_id="ird-amend-2026-11",
            section_ref="Section 52",
            page=7,
            metadata={
                "instrument_type": "amendment_act",
                "paragraph_ref": "52(4)",
                "is_operative_provision": True,
                "applicable_yas": "2025_26",
            },
        ),
    ]
    bundle = gather_evidence(
        resp,
        chroma_index=index,
        include_graph_modifies=False,
        assessment_year="2025_26",
        min_score=0.50,
    )
    assert bundle.chunks
    assert bundle.chunks[0].chunk_id == "carry-op"
    ids, _ = local_evidence_for_step(step, bundle)
    assert "carry-op" in ids
    assert "toc-only" not in ids
    narr = build_fixture_narrative(resp, bundle)
    assert narr.payload.steps_explained[0].evidence_unavailable is False
    assert "carry-op" in narr.payload.steps_explained[0].evidence_chunk_ids

    # Wrong-section-only bundle → step gate unavailable (does not unlock GPT for step)
    weak = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="string-only",
                text="See also Section 52 of the Act for reliefs.",
                section_ref="Section 5",
                source_doc_id="ird-ira-2017-base",
                score=0.95,
                is_operative_provision=True,
            )
        ],
        sections_retrieved=["Section 5"],
        sections_queried=["Section 52"],
    )
    weak.step_evidence = build_step_evidence_statuses([step], weak)
    narr2 = build_fixture_narrative(resp, weak)
    assert narr2.payload.steps_explained[0].narrative == STEP_EVIDENCE_UNAVAILABLE


def test_passes_rag_min_score_helper_and_eval_bands() -> None:
    """Document experimental floors 0.45–0.60; helper is noise filter only."""
    from adaptive_tax_app.services.evidence import passes_rag_min_score

    assert passes_rag_min_score(0.55, 0.55)
    assert not passes_rag_min_score(0.54, 0.55)
    assert passes_rag_min_score(None, 0.55)
    # Dissertation candidates (choose production value from gold P@K/R@K)
    for floor in (0.45, 0.50, 0.55, 0.60):
        assert passes_rag_min_score(floor, floor)
        assert not passes_rag_min_score(floor - 0.01, floor)


def test_guide_master_never_ground_explain_chunks() -> None:
    from adaptive_tax_app.services.evidence import filter_explain_chunks

    chunks = [
        EvidenceChunk(
            chunk_id="g",
            text="guide",
            section_ref="Section 52",
            source_doc_id="ird-guide-ira",
        ),
        EvidenceChunk(
            chunk_id="m",
            text="master",
            section_ref="Section 52",
            source_doc_id="ird-calc-ontology-v5",
        ),
        EvidenceChunk(
            chunk_id="ok",
            text="act",
            section_ref="Section 52",
            source_doc_id="ird-ira-2017-base",
        ),
    ]
    kept = filter_explain_chunks(chunks)
    assert [c.chunk_id for c in kept] == ["ok"]


def test_toc_chunk_does_not_unlock_step() -> None:
    from adaptive_tax_app.services.evidence import (
        build_step_evidence_statuses,
        local_evidence_for_step,
    )

    step = CalculationTraceStep(
        step_id="cap",
        description="Section 52",
        formula="cap",
        output="1",
        section_uids=["ird-ira-2017-base::sec::section_52"],
    )
    bundle = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="toc-52",
                text="52. Qualifying payments .... 43",
                section_ref="Section 52",
                source_doc_id="ird-ira-2017-base",
                page=4,
                score=0.9,
                is_toc=True,
                is_operative_provision=False,
            )
        ],
        sections_retrieved=["Section 52"],
        sections_queried=["Section 52"],
    )
    ids, rule = local_evidence_for_step(step, bundle)
    assert ids == []
    assert rule is None
    status = build_step_evidence_statuses([step], bundle)[0]
    assert status.evidence_available is False
