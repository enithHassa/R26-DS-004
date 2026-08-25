"""Phase 6.6 — field-level explain API + housing allowance DoD."""

from __future__ import annotations

from fastapi.testclient import TestClient

from adaptive_tax_app.main import create_app
from adaptive_tax_app.services.evidence import gather_field_evidence
from adaptive_tax_app.services.filing_catalog import clear_filing_catalog_cache, explain_component


def setup_function() -> None:
    clear_filing_catalog_cache()


def test_explain_emp_housing_allowance_dod() -> None:
    """DoD: Included + Sec 5(2)(b) + High confidence + Act quote."""
    payload = explain_component("emp_housing_allowance", assessment_year="2024_25")
    assert payload.display_name == "Housing Allowance"
    assert payload.treatment == "include"
    assert payload.section == "5"
    assert payload.paragraph == "2(b)"
    assert payload.legal_confidence == "high"
    assert payload.confidence_basis == "direct_section"
    assert payload.confidence_reason
    assert payload.source_quote
    assert "rent" in payload.source_quote.lower()
    assert payload.section_uid == "ird-ira-2017-base::sec::section_5"
    assert payload.concept_id == "emp_housing_allowance"
    assert payload.rule_source_id == "bootstrap:emp_housing_allowance"
    assert payload.act_version_label
    kg_types = {node["node_type"] for node in payload.kg_nodes}
    assert "Concept" in kg_types
    assert "Section" in kg_types


def test_explain_api_returns_evidence_envelope() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/filing-catalog/inv_dividends/explain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["section"] == "7"
    assert body["confidence_basis"] == "direct_section"
    assert "evidence_chunks" in body
    assert "evidence_warnings" in body
    assert isinstance(body["kg_nodes"], list)


def test_gather_field_evidence_degrades_without_chroma() -> None:
    bundle = gather_field_evidence(
        section_uid="ird-ira-2017-base::sec::section_5",
        rule_source_id="bootstrap:emp_housing_allowance",
        chroma_index=None,
        db=None,
    )
    assert isinstance(bundle.chunks, list)
    assert isinstance(bundle.warnings, list)
