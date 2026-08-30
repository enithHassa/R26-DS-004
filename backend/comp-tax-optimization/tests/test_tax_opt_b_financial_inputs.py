"""Structured financial inputs → mapper → compliance (HTTP)."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import (
    TaxOptBDeductionLineV1,
    TaxOptBFinancialInputsV1,
    TaxOptBInvestmentLineV1,
    TaxOptBInvestmentTaxTreatmentV1,
)
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import (
    map_financial_inputs_to_profile_and_strategy,
    validate_relief_codes_used,
)


def test_mapper_aggregates_income_and_duplicate_relief_codes() -> None:
    fin = TaxOptBFinancialInputsV1(
        tax_year="2024_25",
        annual_salary_income=Decimal("1000000"),
        annual_business_income=Decimal("500000"),
        annual_other_income=Decimal("100000"),
        deductions=[
            TaxOptBDeductionLineV1(relief_code="life_insurance_premium", amount_annual=Decimal("30000")),
            TaxOptBDeductionLineV1(relief_code="life_insurance_premium", amount_annual=Decimal("20000")),
        ],
        investments=[
            TaxOptBInvestmentLineV1(
                investment_type="epf_additional",
                amount_annual=Decimal("100000"),
                tax_treatment=TaxOptBInvestmentTaxTreatmentV1.MAP_TO_RELIEF,
                relief_code="retirement_contribution",
            ),
            TaxOptBInvestmentLineV1(
                investment_type="unit_trust",
                amount_annual=Decimal("50000"),
                tax_treatment=TaxOptBInvestmentTaxTreatmentV1.INFORMATIONAL,
            ),
        ],
        strategy_notes="mapper test",
    )
    profile, strategy = map_financial_inputs_to_profile_and_strategy(fin)
    assert profile.annual_gross_income == Decimal("1600000")
    assert profile.estimated_annual_taxable_income is None
    assert len(strategy.claims) == 2
    by = {c.relief_code: c.claimed_amount_annual for c in strategy.claims}
    assert by["life_insurance_premium"] == Decimal("50000")
    assert by["retirement_contribution"] == Decimal("100000")
    assert strategy.notes == "mapper test"


def test_mapper_includes_investment_income_in_gross() -> None:
    fin = TaxOptBFinancialInputsV1(
        tax_year="2024_25",
        annual_salary_income=Decimal("2000000"),
        annual_business_income=Decimal("400000"),
        annual_investment_income=Decimal("70000"),
        annual_other_income=Decimal("50000"),
    )
    profile, _ = map_financial_inputs_to_profile_and_strategy(fin)
    assert profile.annual_gross_income == Decimal("2520000")


def test_validate_relief_codes_used() -> None:
    fin = TaxOptBFinancialInputsV1(
        deductions=[
            TaxOptBDeductionLineV1(relief_code="life_insurance_premium", amount_annual=Decimal("1")),
            TaxOptBDeductionLineV1(relief_code="bad_code", amount_annual=Decimal("1")),
        ],
    )
    bad = validate_relief_codes_used(fin, {"life_insurance_premium"})
    assert bad == ["bad_code"]


def test_http_financial_inputs_passes_and_returns_mapped(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2000000",
        "annual_business_income": "400000",
        "annual_other_income": "0",
        "deductions": [
            {"relief_code": "life_insurance_premium", "amount_annual": "50000"},
        ],
        "investments": [],
        "strategy_notes": None,
    }
    resp = client.post("/api/v1/compliance/check-from-financial-inputs", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["mapped_profile"]["annual_gross_income"] == "2400000"
    assert data["mapped_profile"].get("estimated_annual_taxable_income") is None
    assert len(data["mapped_strategy"]["claims"]) == 1


def test_http_financial_inputs_unknown_relief_422(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000",
        "deductions": [{"relief_code": "not_a_real_code", "amount_annual": "1"}],
    }
    resp = client.post("/api/v1/compliance/check-from-financial-inputs", json=body)
    assert resp.status_code == 422
