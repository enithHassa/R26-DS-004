"""Income snapshot aggregate (Option B contract on Component 1)."""

from __future__ import annotations


def test_income_snapshot_stub_returns_contract_fields(client) -> None:
    r = client.get(
        "/api/v1/users/demo-user-1/income-snapshot",
        params={"assessment_year": "2024_25"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["schema_version"] == "income_snapshot_v1"
    assert data["user_id"] == "demo-user-1"
    assert data["assessment_year"] == "2024_25"
    assert data["annual_gross_income"] == "2400000"
    assert data["estimated_annual_taxable_income"] == "1800000"
    assert data["source"] == "component1_stub"
    assert "Stub aggregate" in data["derivation_summary"]
