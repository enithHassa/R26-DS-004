"""Tests for the Financial Profile module (FR1, FR2 — Phase 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


def _payload(**overrides: object) -> dict:
    base = {
        "full_name": "Nuwan Perera",
        "date_of_birth": "1990-04-15",
        "gender": "male",
        "district": "Colombo",
        "marital_status": "married",
        "occupation": "employee",
        "dependents": 2,
        "years_employed": 8,
        "gross_monthly_income": "350000.00",
        "monthly_expenses": "180000.00",
        "monthly_debt_service": "45000.00",
        "liquid_savings": "1200000.00",
        "existing_investments": "850000.00",
        "total_debt": "2400000.00",
        "epf_balance": "950000.00",
        "etf_balance": "180000.00",
        "health_insurance": True,
        "life_insurance_premium_annual": "60000.00",
        "home_loan_interest_annual": "300000.00",
        "donations_annual": "0.00",
        "risk_tolerance": "medium",
        "investment_horizon_years": 15,
        "income_sources": [
            {"kind": "employment", "monthly_amount": "320000.00", "is_taxable": True},
            {"kind": "interest", "monthly_amount": "30000.00", "is_taxable": True},
        ],
        "tax_year": "2024_25",
    }
    base.update(overrides)
    return base


def test_create_get_profile(client: TestClient) -> None:
    resp = client.post("/api/v1/profiles", json=_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["full_name"] == "Nuwan Perera"
    assert body["district"] == "Colombo"
    assert body["health_insurance"] is True
    profile_id = body["id"]

    fetched = client.get(f"/api/v1/profiles/{profile_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == profile_id


def test_update_profile(client: TestClient) -> None:
    created = client.post("/api/v1/profiles", json=_payload()).json()
    pid = created["id"]

    resp = client.patch(
        f"/api/v1/profiles/{pid}",
        json={"district": "Gampaha", "dependents": 3, "risk_tolerance": "low"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["district"] == "Gampaha"
    assert body["dependents"] == 3
    assert body["risk_tolerance"] == "low"


def test_delete_profile(client: TestClient) -> None:
    created = client.post("/api/v1/profiles", json=_payload()).json()
    pid = created["id"]

    resp = client.delete(f"/api/v1/profiles/{pid}")
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/profiles/{pid}")
    assert resp.status_code == 404


def test_list_profiles_paginated_and_filtered(client: TestClient) -> None:
    client.post("/api/v1/profiles", json=_payload(full_name="A", district="Colombo"))
    client.post("/api/v1/profiles", json=_payload(full_name="B", district="Kandy"))
    client.post("/api/v1/profiles", json=_payload(full_name="C", district="Kandy"))

    resp = client.get("/api/v1/profiles", params={"page_size": 2})
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2

    filtered = client.get("/api/v1/profiles", params={"district": "Kandy"}).json()
    assert filtered["total"] == 2
    assert {p["district"] for p in filtered["items"]} == {"Kandy"}


def test_features_endpoint_computes_tax_and_disposable_income(client: TestClient) -> None:
    created = client.post("/api/v1/profiles", json=_payload()).json()
    pid = created["id"]

    resp = client.get(f"/api/v1/profiles/{pid}/features")
    assert resp.status_code == 200
    feats = resp.json()
    assert feats["profile_id"] == pid
    assert feats["age_years"] >= 30
    assert Decimal(feats["gross_annual_taxable_income"]) > 0
    assert Decimal(feats["baseline_tax_liability_annual"]) > 0
    assert 0 <= feats["effective_tax_rate"] < 0.5
    assert 0 <= feats["savings_rate"] <= 1
    assert "above_tax_threshold" in feats["eligibility_flags"]
    assert feats["eligibility_flags"]["has_health_insurance"] is True


def test_taxable_income_adds_side_sources_when_they_do_not_cover_salary(
    client: TestClient,
) -> None:
    """User-intake style: salary in gross_monthly_income, extras in income_sources.

    Using only the extras (rental + interest) kept annual income under the
    tax-free relief and flattened the impact tax chart to LKR 0.
    """
    payload = _payload(
        gross_monthly_income="100000.00",
        annual_bonus_lkr="30000.00",
        monthly_expenses="60000.00",
        monthly_debt_service="0",
        life_insurance_premium_annual="0",
        home_loan_interest_annual="0",
        donations_annual="0",
        health_insurance=False,
        income_sources=[
            {"kind": "rental", "monthly_amount": "40000.00", "is_taxable": True},
            {"kind": "interest", "monthly_amount": "20000.00", "is_taxable": True},
        ],
    )
    created = client.post("/api/v1/profiles", json=payload).json()
    feats = client.get(f"/api/v1/profiles/{created['id']}/features").json()
    # (100k + 40k + 20k) * 12 + 30k bonus = 1,950,000
    assert Decimal(feats["gross_annual_taxable_income"]) == Decimal("1950000.00")
    assert Decimal(feats["baseline_tax_liability_annual"]) > 0
    assert feats["eligibility_flags"]["above_tax_threshold"] is True


def test_zero_tax_for_low_income(client: TestClient) -> None:
    payload = _payload(
        gross_monthly_income="80000.00",
        monthly_expenses="55000.00",
        monthly_debt_service="0",
        income_sources=[
            {"kind": "employment", "monthly_amount": "80000.00", "is_taxable": True},
        ],
    )
    created = client.post("/api/v1/profiles", json=payload).json()
    feats = client.get(f"/api/v1/profiles/{created['id']}/features").json()
    assert Decimal(feats["baseline_tax_liability_annual"]) == Decimal("0.00")
    assert feats["eligibility_flags"]["above_tax_threshold"] is False


def test_404_on_missing_profile(client: TestClient) -> None:
    resp = client.get("/api/v1/profiles/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("gross_monthly_income", "-1"),
        ("dependents", 99),
        ("tax_year", "not-a-year"),
    ],
)
def test_validation_rejects_bad_input(client: TestClient, field: str, value: object) -> None:
    resp = client.post("/api/v1/profiles", json=_payload(**{field: value}))
    assert resp.status_code == 422


def test_patch_tax_return_detail_persists_and_syncs_scalars(client: TestClient) -> None:
    created = client.post("/api/v1/profiles", json=_payload()).json()
    pid = created["id"]

    detail = {
        "section1": {
            "fullName": "Kasun Perera",
            "dob": "1992-08-14",
            "gender": "male",
            "district": "Colombo",
            "marital": "single",
            "residency": "resident",
            "nationality": "lk",
            "dependants": "1",
            "taxYear": "2024-2025",
        },
        "section2": {
            "employers": [
                {
                    "name": "ABC Pvt Ltd",
                    "gross": "1800000",
                    "bonus": "150000",
                    "epf": "162000",
                    "apit": "108000",
                }
            ],
        },
    }

    resp = client.patch(
        f"/api/v1/profiles/{pid}",
        json={
            "tax_return_detail": detail,
            "section_completion": [1, 2],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Kasun Perera"
    assert body["dependents"] == 1
    assert body["tax_year"] == "2024_25"
    assert body["tax_return_detail"]["section1"]["fullName"] == "Kasun Perera"
    assert body["section_completion"] == [1, 2]
    assert Decimal(body["gross_monthly_income"]) == Decimal("150000.00")
