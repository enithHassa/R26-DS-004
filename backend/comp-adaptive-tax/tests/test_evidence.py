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
from adaptive_tax_app.schemas.evidence import EvidenceBundle
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
    # Query uses the human label
    assert index.search.call_args.args[0] == "Section 52"


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
