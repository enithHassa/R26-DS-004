"""Phase 6.8 — legal coverage dashboard, unsupported queue, reasoning graph."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from adaptive_tax_app.main import create_app
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1
from adaptive_tax_app.services.calc_store import save as save_calculation
from adaptive_tax_app.services.filing_catalog import clear_filing_catalog_cache
from adaptive_tax_app.services.legal_coverage import build_legal_coverage
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.reasoning_graph import build_reasoning_graph
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def setup_function() -> None:
    clear_filing_catalog_cache()
    clear_provenance_cache()


def test_legal_coverage_api_returns_section_grain() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/knowledge/legal-coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["catalog_version"] == "v1"
    assert body["area_summary"]["n_planned"] >= 8
    section_keys = {s["section_key"] for s in body["sections"]}
    assert {
        "5",
        "6",
        "7",
        "8",
        "52",
        "89",
        "first_schedule",
        "third_schedule",
    } <= section_keys
    sec5 = next(s for s in body["sections"] if s["section_key"] == "5")
    assert sec5["n_planned"] > 0
    assert sec5["n_covered"] <= sec5["n_planned"]
    assert 0 <= sec5["coverage"] <= 1


def test_build_legal_coverage_component_flags() -> None:
    cov = build_legal_coverage()
    sec52 = next(s for s in cov.sections if s.section_key == "52")
    assert sec52.n_planned > 0
    pending = [c for c in sec52.components if not c.covered]
    for row in pending:
        assert not (
            row.approved and row.engine_wired and row.provenance_complete
        ) or row.covered


def test_unsupported_queue_typed_response() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/filing-catalog/unsupported")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    item = next(i for i in body["items"] if i["component_id"] == "qp_bank_merger")
    assert item["status"] == "pending_unsupported"
    assert item["engine_support"] == "unsupported"
    assert item["action_required"] == "Requires new Rule Engine handler"
    assert "Approve only after" in item["approve_blocked_reason"]


def test_reasoning_graph_from_persisted_calc() -> None:
    req = CalculateTaxRequestV1(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income=Decimal("0"),
        business_income=Decimal("0"),
        investment_income=Decimal("0"),
        qualifying_payments=Decimal("100000"),
        donations=Decimal("0"),
        param_set="current",
        filing_lines=[
            FilingLineV1(component_id="emp_salary", amount=Decimal("1800000")),
            FilingLineV1(component_id="emp_housing_allowance", amount=Decimal("200000")),
            FilingLineV1(component_id="qp_government_sri_lanka", amount=Decimal("100000")),
        ],
    )
    result = calculate(req, kg=default_file_kg())
    calc_id = save_calculation(req, result)

    client = TestClient(create_app())
    graph_resp = client.get(f"/api/v1/calculations/{calc_id}/reasoning-graph")
    assert graph_resp.status_code == 200
    graph = graph_resp.json()
    assert graph["calc_id"] == calc_id
    node_ids = {n["node_id"] for n in graph["nodes"]}
    assert "salary" in node_ids
    assert "employment" in node_ids
    assert "assessable" in node_ids
    assert "payable" in node_ids
    salary = next(n for n in graph["nodes"] if n["node_id"] == "salary")
    assert salary["component_ids"]
    assert graph["display_order"][0] == "salary"


def test_reasoning_graph_service_deterministic() -> None:
    req = CalculateTaxRequestV1(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income=Decimal("1800000"),
        business_income=Decimal("0"),
        investment_income=Decimal("0"),
        qualifying_payments=Decimal("0"),
        donations=Decimal("0"),
        param_set="current",
    )
    result = calculate(req, kg=default_file_kg())
    from datetime import datetime, timezone

    from adaptive_tax_app.schemas.calculate import StoredCalculationV1

    record = StoredCalculationV1(
        calc_id="test-calc",
        created_at=datetime.now(timezone.utc),
        request=req,
        response=result,
        param_set_effective="current",
    )
    g1 = build_reasoning_graph(record)
    g2 = build_reasoning_graph(record)
    assert g1.model_dump() == g2.model_dump()
