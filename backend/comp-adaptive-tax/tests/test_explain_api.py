"""API tests for POST /api/v1/explain (Phase 4)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.main import create_app
from adaptive_tax_app.schemas.evidence import EvidenceBundle, EvidenceChunk
from adaptive_tax_app.schemas.explain import DISCLAIMER, ExplainTaxResponseV1
from backend.shared.config.database import get_db


def _inline_calculation() -> dict:
    return {
        "final_tax_lkr": "0",
        "calc_id": "",
        "calculation_trace": [
            {
                "step_id": "sum_assessable",
                "description": "Sum assessable",
                "formula": "sum(...)",
                "inputs": {"employment_income": "3000000"},
                "output": "3000000",
                "concept_ids": [],
                "section_uids": ["ird-ira-2017-base::sec::section_5"],
                "rule_source_ids": [],
            },
            {
                "step_id": "deduct_qualifying_payment",
                "description": "Apply QP",
                "formula": "min(claimed, cap)",
                "inputs": {},
                "output": "1200000",
                "concept_ids": [],
                "section_uids": ["ird-ira-2017-base::sec::section_52"],
                "rule_source_ids": [],
            },
            {
                "step_id": "final_tax",
                "description": "Total",
                "formula": "sum(slabs)",
                "inputs": {},
                "output": "0",
                "concept_ids": [],
                "section_uids": ["ird-ira-2017-base::sec::first_schedule"],
                "rule_source_ids": [],
            },
        ],
        "rules_applied": [
            "sum_assessable",
            "deduct_qualifying_payment",
            "final_tax",
        ],
        "rule_source_refs": [],
    }


@pytest.fixture()
def explain_client() -> Iterator[TestClient]:
    """TestClient with DB dependency stubbed (no Postgres required)."""
    app = create_app()

    def _override_db():
        yield None

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_explain_openapi_path(client: TestClient) -> None:
    paths = client.app.openapi()["paths"]
    assert "/api/v1/explain" in paths


def test_explain_api_inline_with_mocked_chroma(explain_client: TestClient) -> None:
    evidence = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="c-52",
                text="Section 52",
                section_ref="Section 52",
                source_doc_id="ird-ira-2017-base",
                page=1,
                score=0.9,
            )
        ],
        source_quotes=[],
        sections_retrieved=["Section 52"],
        sections_queried=["Section 5", "Section 52", "First Schedule"],
    )
    with patch(
        "adaptive_tax_app.services.explain.gather_evidence",
        return_value=evidence,
    ):
        response = explain_client.post(
            "/api/v1/explain",
            json={"calculation": _inline_calculation()},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert body["final_tax_lkr"] == "0"
    assert body["disclaimer"] == DISCLAIMER
    assert "Section 52" in body["sections_retrieved"]
    assert set(body["sections_cited"]) <= set(body["sections_retrieved"])
    assert body["steps_explained"]


def test_explain_api_insufficient_evidence(explain_client: TestClient) -> None:
    with patch(
        "adaptive_tax_app.services.explain.gather_evidence",
        return_value=EvidenceBundle(
            chunks=[],
            source_quotes=[],
            sections_retrieved=[],
            sections_queried=["Section 52"],
        ),
    ):
        response = explain_client.post(
            "/api/v1/explain",
            json={"calculation": _inline_calculation()},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_evidence"] is True
    assert body["summary"] == ""
    assert body["steps_explained"] == []
    assert body["sections_cited"] == []


def test_explain_api_calc_id_round_trip(
    client: TestClient,
    explain_client: TestClient,
) -> None:
    """POST /calculate then POST /explain with calc_id (mocked evidence)."""
    calc = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2024_25",
            "resident_status": "resident",
            "employment_income": "1800000",
            "param_set": "current",
        },
    )
    assert calc.status_code == 200, calc.text
    calc_id = calc.json()["calc_id"]
    assert calc_id

    with patch(
        "adaptive_tax_app.services.explain.gather_evidence",
        return_value=EvidenceBundle(
            chunks=[
                EvidenceChunk(
                    chunk_id="c-fs",
                    text="First Schedule rates",
                    section_ref="First Schedule",
                    source_doc_id="ird-ira-2017-base",
                    page=200,
                    score=0.8,
                )
            ],
            sections_retrieved=["First Schedule"],
            sections_queried=["First Schedule"],
        ),
    ):
        response = explain_client.post("/api/v1/explain", json={"calc_id": calc_id})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["calc_id"] == calc_id
    assert body["insufficient_evidence"] is False
    assert body["final_tax_lkr"] == "42000"
    ExplainTaxResponseV1.model_validate(body)


def test_explain_api_missing_calc_id_404(explain_client: TestClient) -> None:
    response = explain_client.post(
        "/api/v1/explain",
        json={"calc_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert response.status_code == 404


def test_explain_api_rejects_empty_body(explain_client: TestClient) -> None:
    response = explain_client.post("/api/v1/explain", json={})
    assert response.status_code == 422
