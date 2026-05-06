"""Option B: orchestrated compliance after Component 1 income snapshot."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from backend.shared.schemas.income_snapshot import IncomeSnapshotV1


def _strategy_ok() -> dict:
    return {
        "claims": [
            {"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"},
        ],
        "notes": None,
    }


@patch(
    "tax_opt_b_app.routers.tax_opt_b_compliance.fetch_income_snapshot",
    new_callable=AsyncMock,
)
def test_check_from_transactions_includes_income_snapshot(mock_fetch, client) -> None:
    mock_fetch.return_value = IncomeSnapshotV1(
        user_id="u1",
        assessment_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
        source="test",
        derivation_summary="unit test snapshot",
        pipeline_version="test",
        transaction_count=3,
    )
    body = {
        "user_id": "u1",
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "strategy": _strategy_ok(),
    }
    resp = client.post("/api/v1/compliance/check-from-transactions", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["income_snapshot"] is not None
    assert data["income_snapshot"]["user_id"] == "u1"
    assert data["income_snapshot"]["annual_gross_income"] == "2400000"
    mock_fetch.assert_awaited_once()


@patch(
    "tax_opt_b_app.routers.tax_opt_b_compliance.fetch_income_snapshot",
    new_callable=AsyncMock,
)
def test_check_from_transactions_year_mismatch_422(mock_fetch, client) -> None:
    mock_fetch.return_value = IncomeSnapshotV1(
        user_id="u1",
        assessment_year="2023_24",
        annual_gross_income=Decimal("1000000"),
        estimated_annual_taxable_income=Decimal("900000"),
        source="test",
        derivation_summary="wrong year",
        pipeline_version="test",
    )
    body = {
        "user_id": "u1",
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "strategy": _strategy_ok(),
    }
    resp = client.post("/api/v1/compliance/check-from-transactions", json=body)
    assert resp.status_code == 422
    assert "assessment_year" in resp.json()["detail"].lower()


@patch(
    "tax_opt_b_app.routers.tax_opt_b_compliance.fetch_income_snapshot",
    new_callable=AsyncMock,
)
def test_check_from_transactions_upstream_error_502(mock_fetch, client) -> None:
    from tax_opt_b_app.services.tax_opt_b_income_snapshot_client import IncomeSnapshotClientError

    mock_fetch.side_effect = IncomeSnapshotClientError("upstream down")
    body = {
        "user_id": "u1",
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "strategy": _strategy_ok(),
    }
    resp = client.post("/api/v1/compliance/check-from-transactions", json=body)
    assert resp.status_code == 502
