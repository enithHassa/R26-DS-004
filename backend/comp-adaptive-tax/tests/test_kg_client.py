"""Unit tests for Adaptive Tax kg_client (file ontology + Neo4j helpers)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from adaptive_tax_app.services import kg_client as kg_mod
from adaptive_tax_app.services.kg_client import (
    CORE_APPLICABLE_CYPHER,
    DeductionLink,
    FileOntologyKgClient,
    Neo4jKgClient,
    ApplicableConcepts,
    bolt_uri,
    get_kg_client,
    _rows_to_applicable,
)


def test_core_cypher_matches_phase3_spec() -> None:
    q = " ".join(CORE_APPLICABLE_CYPHER.split())
    assert "concept_id: 'resident_individual'" in q
    assert "CONTRIBUTES_TO*1..3" in q
    assert "concept_id: 'assessable_income'" in q
    assert "DEDUCTED_FROM" in q
    assert "concept_id: 'taxable_income'" in q
    assert "LIMITED_BY" in q
    assert "income.concept_id AS income_id" in q
    assert "ded.concept_id AS ded_id" in q
    assert "cap.concept_id AS cap_id" in q
    assert "ti.concept_id AS taxable_id" in q


def test_bolt_uri_rewrites_neo4j_scheme() -> None:
    assert bolt_uri("neo4j://127.0.0.1:7687") == "bolt://127.0.0.1:7687"
    assert bolt_uri("bolt://127.0.0.1:7687") == "bolt://127.0.0.1:7687"


def test_file_kg_income_and_deduction_caps() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["employment_income", "investment_income", "business_income"],
        claimed_deductions=["qualifying_payment", "donation"],
    )
    assert hit.income_concept_ids == (
        "employment_income",
        "investment_income",
        "business_income",
    )
    assert hit.resident_individual_present is True
    by_id = {d.concept_id: d for d in hit.deductions}
    assert by_id["qualifying_payment"].cap_concept_id == "qualifying_payment_cap"
    assert by_id["donation"].cap_concept_id == "donation_cap"
    # Section anchors via DEFINES / COVERS_RELIEF
    assert any("section_5" in u for u in hit.income_section_uids.get("employment_income", ()))
    assert any("section_52" in u for u in by_id["qualifying_payment"].section_uids)
    assert any("section_52" in u for u in by_id["donation"].section_uids)


def test_file_kg_ignores_unknown_and_non_contributing_income() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["employment_income", "not_a_real_income", "taxable_income"],
        claimed_deductions=["qualifying_payment", "nope"],
    )
    assert hit.income_concept_ids == ("employment_income",)
    assert [d.concept_id for d in hit.deductions] == ["qualifying_payment"]


def test_file_kg_deductions_without_income() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=[],
        claimed_deductions=["donation"],
    )
    assert hit.income_concept_ids == ()
    assert len(hit.deductions) == 1
    assert hit.deductions[0].concept_id == "donation"


def test_get_kg_client_file_mode() -> None:
    client = get_kg_client(mode="file")
    assert isinstance(client, FileOntologyKgClient)


def test_rows_to_applicable_collapses_cartesian_product() -> None:
    rows = [
        {
            "income_id": "employment_income",
            "ded_id": "qualifying_payment",
            "cap_id": "qualifying_payment_cap",
            "taxable_id": "taxable_income",
            "taxpayer_id": "resident_individual",
        },
        {
            "income_id": "employment_income",
            "ded_id": "donation",
            "cap_id": "donation_cap",
            "taxable_id": "taxable_income",
            "taxpayer_id": "resident_individual",
        },
        {
            "income_id": "business_income",
            "ded_id": "qualifying_payment",
            "cap_id": "qualifying_payment_cap",
            "taxable_id": "taxable_income",
            "taxpayer_id": "resident_individual",
        },
    ]
    hit = _rows_to_applicable(
        rows,
        income_types=["employment_income", "business_income"],
        section_map={
            "employment_income": ("ird-ira-2017-base::sec::section_5",),
            "qualifying_payment": ("ird-ira-2017-base::sec::section_52",),
        },
    )
    assert hit.income_concept_ids == ("employment_income", "business_income")
    assert len(hit.deductions) == 2
    assert hit.income_section_uids["employment_income"] == (
        "ird-ira-2017-base::sec::section_5",
    )
    qp = next(d for d in hit.deductions if d.concept_id == "qualifying_payment")
    assert qp.cap_concept_id == "qualifying_payment_cap"
    assert "ird-ira-2017-base::sec::section_52" in qp.section_uids


def test_neo4j_client_uses_core_cypher_and_section_queries() -> None:
    core_rows = [
        {
            "income_id": "employment_income",
            "ded_id": "donation",
            "cap_id": "donation_cap",
            "taxable_id": "taxable_income",
            "taxpayer_id": "resident_individual",
        }
    ]
    defines_rows = [
        {
            "concept_id": "employment_income",
            "section_uids": ["ird-ira-2017-base::sec::section_5"],
        }
    ]
    covers_rows = [
        {
            "concept_id": "donation_cap",
            "section_uids": ["ird-ira-2017-base::sec::section_52"],
        }
    ]

    session = MagicMock()

    def _run(query: str, **_kwargs: Any) -> MagicMock:
        result = MagicMock()
        if "CONTRIBUTES_TO" in query:
            result.data.return_value = core_rows
        elif "DEFINES" in query:
            result.data.return_value = defines_rows
        elif "COVERS_RELIEF" in query:
            result.data.return_value = covers_rows
        else:
            result.data.return_value = []
        return result

    session.run.side_effect = _run
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False

    with patch.object(kg_mod, "open_neo4j_driver", return_value=driver):
        hit = Neo4jKgClient().resolve_applicable_concepts(
            income_types=["employment_income"],
            claimed_deductions=["donation"],
        )

    assert isinstance(hit, ApplicableConcepts)
    assert hit.income_concept_ids == ("employment_income",)
    assert hit.deductions == (
        DeductionLink(
            concept_id="donation",
            cap_concept_id="donation_cap",
            section_uids=("ird-ira-2017-base::sec::section_52",),
        ),
    )
    assert hit.income_section_uids["employment_income"] == (
        "ird-ira-2017-base::sec::section_5",
    )
    driver.close.assert_called_once()
