"""Smoke tests for POST /api/v1/calculate and param/kg wiring."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.kg_client import FileOntologyKgClient
from adaptive_tax_app.services.param_store import load_tax_param_pack
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
from backend.shared.config.settings import PROJECT_ROOT

_EX01 = PROJECT_ROOT / "models" / "adaptive-tax" / "examples" / "ex01_basic_salary.json"


def test_param_store_loads_current_and_pre_amend() -> None:
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    pre = load_tax_param_pack(assessment_year="2024_25", param_set="pre_amend_2025")
    assert len(ya24.rate_bands) == 6
    assert len(ya25.rate_bands) == 5
    assert ya24.relief_for_concept("personal_relief") is not None
    assert ya24.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")
    assert ya25.relief_for_concept("personal_relief").cap_amount == Decimal("1800000")
    assert ya24.relief_for_concept("qualifying_payment_cap") is None
    assert ya25.relief_for_concept("qualifying_payment_cap") is None
    assert ya24.relief_for_concept("donation_cap").cap_amount == Decimal("75000")
    assert ya24.relief_for_concept("solar_panel_relief").cap_amount == Decimal(
        "600000"
    )
    assert pre.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")


def test_file_kg_resolves_income_and_deduction_paths() -> None:
    kg = FileOntologyKgClient()
    hit = kg.resolve_applicable_concepts(
        income_types=["employment_income", "business_income"],
        claimed_deductions=["qualifying_payment", "donation"],
    )
    assert "employment_income" in hit.income_concept_ids
    assert "business_income" in hit.income_concept_ids
    ded_ids = {d.concept_id: d for d in hit.deductions}
    assert ded_ids["qualifying_payment"].cap_concept_id is None
    assert "donation" not in ded_ids


def test_rule_engine_basic_salary_tax_42000() -> None:
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("1800000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "42000"
    assert "sum_assessable" in result.rules_applied
    assert "apply_personal_relief" in result.rules_applied
    assert "slab_band_1" in result.rules_applied
    assert "slab_band_2" in result.rules_applied
    assert result.calculation_trace


def test_calculate_api_ex01_basic_salary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API smoke: POST /api/v1/calculate using the ex01 fixture inputs.

    The live route requires Neo4j; unit tests inject the file KG client.
    """
    monkeypatch.setattr(
        "adaptive_tax_app.routers.calculate.get_kg_client",
        lambda mode="neo4j": default_file_kg(),
    )
    fixture = json.loads(_EX01.read_text(encoding="utf-8"))
    response = client.post("/api/v1/calculate", json=fixture["inputs"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["final_tax_lkr"] == fixture["expected_final_tax_lkr"]
    assert body["rules_applied"] == fixture["expected_rules_applied"]
    assert isinstance(body["calculation_trace"], list)
    assert body["calculation_trace"][0]["step_id"] == "sum_assessable"
    actual_sources = {ref["id"] for ref in body["rule_source_refs"]}
    for sid in fixture["expected_rule_source_ids"]:
        assert sid in actual_sources
    calc_id = body["calc_id"]
    assert calc_id
    # UUID round-trip via GET /calculations/{calc_id}
    stored = client.get(f"/api/v1/calculations/{calc_id}")
    assert stored.status_code == 200, stored.text
    record = stored.json()
    assert record["calc_id"] == calc_id
    assert record["response"]["final_tax_lkr"] == fixture["expected_final_tax_lkr"]
    assert record["response"]["calc_id"] == calc_id
    assert record["param_set_effective"] == fixture["inputs"].get("param_set", "current")
    assert record["request"]["employment_income"] == fixture["inputs"]["employment_income"]


def test_calculate_route_forces_neo4j_kg_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 2: HTTP POST /calculate must call get_kg_client(mode='neo4j')."""
    captured: dict[str, str] = {}

    def _capture_kg(*, mode: str = "auto"):
        captured["mode"] = mode
        return default_file_kg()

    monkeypatch.setattr(
        "adaptive_tax_app.routers.calculate.get_kg_client",
        _capture_kg,
    )
    fixture = json.loads(_EX01.read_text(encoding="utf-8"))
    response = client.post("/api/v1/calculate", json=fixture["inputs"])
    assert response.status_code == 200, response.text
    assert captured.get("mode") == "neo4j"


def test_get_calculation_not_found(client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    response = client.get(f"/api/v1/calculations/{missing}")
    assert response.status_code == 404


def test_get_calculation_invalid_id(client: TestClient) -> None:
    response = client.get("/api/v1/calculations/not-a-uuid")
    assert response.status_code == 404
