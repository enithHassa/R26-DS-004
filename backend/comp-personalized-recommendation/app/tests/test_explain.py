"""Tests for Phase 6 SHAP explanation endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("shap")
pytest.importorskip("lightgbm")


def _create_profile(client: TestClient) -> str:
    payload = {
        "full_name": "Explain Test User",
        "date_of_birth": "1988-06-01",
        "occupation": "employee",
        "gross_monthly_income": "400000",
        "monthly_expenses": "140000",
        "monthly_debt_service": "30000",
        "liquid_savings": "700000",
        "existing_investments": "200000",
        "life_insurance_premium_annual": "40000",
        "health_insurance": True,
        "income_sources": [
            {"kind": "employment", "monthly_amount": "400000", "is_taxable": True},
        ],
        "tax_year": "2026_27",
    }
    resp = client.post("/api/v1/profiles", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_explain_strategy(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/recommendations/explain",
        json={
            "profile_id": profile_id,
            "strategy_code": "S001_health_life_premium_optimisation",
            "top_k": 3,
        },
    )
    if resp.status_code == 503:
        pytest.skip(f"Explanation unavailable: {resp.json().get('detail')}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["top_reasons"]) >= 1
    assert body["narrative"]


def test_explain_unknown_strategy(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/recommendations/explain",
        json={"profile_id": profile_id, "strategy_code": "S999_missing"},
    )
    assert resp.status_code == 404


def test_legacy_get_explain_gone(client: TestClient) -> None:
    resp = client.get(f"/api/v1/recommendations/{uuid4()}/explain")
    assert resp.status_code == 410
