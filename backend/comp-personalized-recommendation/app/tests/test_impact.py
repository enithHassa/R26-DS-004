"""Tests for Phase 5 predictive impact endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_profile(client: TestClient) -> str:
    payload = {
        "full_name": "Impact Test User",
        "date_of_birth": "1990-01-15",
        "occupation": "employee",
        "gross_monthly_income": "350000",
        "monthly_expenses": "120000",
        "monthly_debt_service": "25000",
        "liquid_savings": "600000",
        "existing_investments": "150000",
        "life_insurance_premium_annual": "25000",
        "health_insurance": True,
        "income_sources": [
            {"kind": "employment", "monthly_amount": "350000", "is_taxable": True},
        ],
        "tax_year": "2026_27",
    }
    resp = client.post("/api/v1/profiles", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_simulate_baseline(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "horizon_years": 5,
            "n_paths": 200,
            "random_seed": 11,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["profile_id"] == profile_id
    assert body["strategy_id"] is None
    assert len(body["baseline"]) == 5
    assert len(body["net_worth_bands"]) == 5
    assert body["strategy_path"] is None
    assert 0.0 <= body["summary"]["probability_of_net_gain"] <= 1.0


def test_simulate_with_strategy_code(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "strategy_code": "S001_health_life_premium_optimisation",
            "horizon_years": 6,
            "n_paths": 300,
            "random_seed": 42,
            "scenario": {"name": "adopt_strategy", "adoption_success_prob": 1.0},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["strategy_id"] is not None
    assert len(body["strategy_path"]) == 6
    assert float(body["summary"]["expected_total_savings"]) >= 0


def test_compare_strategies(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/impact/compare",
        json={
            "profile_id": profile_id,
            "strategy_codes": [
                "S001_health_life_premium_optimisation",
                "S002_retirement_contribution_topup",
            ],
            "horizon_years": 4,
        },
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()
    assert len(results) == 2
    codes_seen = {r["strategy_id"] for r in results}
    assert len(codes_seen) == 2


def test_simulate_combined_strategies(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "strategy_codes": [
                "S001_health_life_premium_optimisation",
                "S002_retirement_contribution_topup",
            ],
            "horizon_years": 4,
            "n_paths": 300,
            "random_seed": 7,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["strategy_id"] is None
    assert len(body["strategy_path"]) == 4
    single = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "strategy_code": "S001_health_life_premium_optimisation",
            "horizon_years": 4,
            "n_paths": 300,
            "random_seed": 7,
        },
    ).json()
    combined_tax = float(body["strategy_path"][0]["projected_tax_liability"])
    single_tax = float(single["strategy_path"][0]["projected_tax_liability"])
    assert combined_tax <= single_tax


def test_simulate_unknown_strategy(client: TestClient) -> None:
    profile_id = _create_profile(client)
    resp = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "strategy_code": "S999_does_not_exist",
        },
    )
    assert resp.status_code == 404


def test_simulate_missing_profile(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/impact/simulate",
        json={"profile_id": str(uuid4()), "horizon_years": 3, "n_paths": 100},
    )
    assert resp.status_code == 404
