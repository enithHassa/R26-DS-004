"""Additive catalog-engine tests for interview dual-result (do not change calculate())."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from adaptive_tax_app.services.catalog_rate_engine import (
    CatalogCalculateInput,
    CatalogClaim,
    CatalogEngineError,
    calculate_from_catalog,
)


def test_catalog_engine_2025_26_succeeds_not_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/catalog-engine/calculate",
        json={
            "assessment_year": "2025_26",
            "employment_income": "5000000",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["assessment_year"] == "2025_26"
    # Personal relief 1.8M from approved/2025_26.json
    assert Decimal(data["personal_relief_lkr"]) == Decimal("1800000.00")
    assert Decimal(data["taxable_income_lkr"]) == Decimal("3200000.00")
    assert Decimal(data["final_tax_lkr"]) > 0


def test_catalog_engine_2024_25_succeeds_not_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/catalog-engine/calculate",
        json={
            "assessment_year": "2024_25",
            "employment_income": "5000000",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["assessment_year"] == "2024_25"
    assert Decimal(data["personal_relief_lkr"]) == Decimal("1200000.00")


def test_catalog_engine_claim_donation_appears_in_receipts() -> None:
    result = calculate_from_catalog(
        CatalogCalculateInput(
            assessment_year="2025_26",
            employment_income=Decimal("5000000"),
            claims=(
                CatalogClaim(
                    compare_group_id="donations_approved_charitable",
                    amount=Decimal("100000"),
                ),
            ),
        )
    )
    groups = {r["compare_group_id"] for r in result["reliefs_applied"]}
    assert "donations_approved_charitable" in groups
    donation = next(
        r
        for r in result["reliefs_applied"]
        if r["compare_group_id"] == "donations_approved_charitable"
    )
    # Approved cap Rs 75,000
    assert Decimal(donation["amount_lkr"]) == Decimal("75000.00")
    assert donation["section_ref"]
    assert donation["quote"]
    receipt_labels = {r["label"] for r in result["receipts"]}
    assert donation["display_name"] in receipt_labels


def test_catalog_engine_unknown_ya_still_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/catalog-engine/calculate",
        json={
            "assessment_year": "1999_00",
            "employment_income": "1000000",
        },
    )
    assert resp.status_code == 422
    assert "Unsupported catalog assessment_year" in str(resp.json())


def test_catalog_engine_older_year_still_works_with_claims() -> None:
    result = calculate_from_catalog(
        CatalogCalculateInput(
            assessment_year="2020_21",
            employment_income=Decimal("3000000"),
            claims=(
                CatalogClaim(
                    compare_group_id="donations_approved_charitable",
                    amount=Decimal("50000"),
                ),
            ),
        )
    )
    assert Decimal(result["final_tax_lkr"]) >= 0
    groups = {r["compare_group_id"] for r in result["reliefs_applied"]}
    assert "personal_relief" in groups


def test_catalog_engine_status_lists_engine_years(client: TestClient) -> None:
    resp = client.get("/api/v1/catalog-engine/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "2024_25" in data["supported_assessment_years"]
    assert "2025_26" in data["supported_assessment_years"]
    assert "2024_25" in data["authority_years_use_calculate"]


def test_catalog_engine_module_rejects_unknown_year_directly() -> None:
    try:
        calculate_from_catalog(
            CatalogCalculateInput(assessment_year="2010_11", employment_income=Decimal("1"))
        )
    except CatalogEngineError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("expected CatalogEngineError")
