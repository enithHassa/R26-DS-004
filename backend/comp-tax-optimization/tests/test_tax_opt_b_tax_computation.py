"""Golden and unit tests for deterministic tax computation (Phase B)."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_rules_loader import (
    TaxOptBRulePack,
    load_tax_opt_b_rules,
    parse_tax_opt_b_rules_dict,
)
from tax_opt_b_app.services.tax_opt_b_tax_computation import (
    allocate_progressive_slabs,
    compute_apit_liability,
    income_basis_before_personal_relief,
    run_compliance_and_compute_tax,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1


def _minimal_pack_for_slabs() -> TaxOptBRulePack:
    """Two-band pack: first 1_000_000 @ 10%, remainder @ 20% (no compliance rules)."""
    return parse_tax_opt_b_rules_dict(
        {
            "schema_version": "t",
            "assessment_year": "2024_25",
            "currency": "LKR",
            "thresholds": {
                "personal_relief_annual": 0,
                "apit_slabs": [
                    {"upper": 1_000_000, "rate": 0.10},
                    {"upper": None, "rate": 0.20},
                ],
                "deductions": {"life_insurance_premium_cap_annual": 100_000},
            },
            "allowed_relief_codes": ["life_insurance_premium"],
            "rules": [
                {
                    "rule_id": "y",
                    "type": "tax_year_match",
                    "description": "",
                    "reference": "",
                },
                {
                    "rule_id": "u",
                    "type": "unknown_relief_code",
                    "description": "",
                    "reference": "",
                },
            ],
        },
    )


def test_allocate_progressive_slabs_two_step_remainder() -> None:
    pack = _minimal_pack_for_slabs()
    tax, slices = allocate_progressive_slabs(Decimal("2500000"), pack.thresholds.apit_slabs)
    assert tax == Decimal("400000")
    assert len(slices) == 2
    assert slices[0].taxable_in_slice == "1000000"
    assert slices[0].tax_in_slice == "100000"
    assert slices[1].taxable_in_slice == "1500000"
    assert slices[1].tax_in_slice == "300000"
    assert slices[1].slice_width_cap is None


def test_allocate_zero_taxable_empty_slices() -> None:
    pack = _minimal_pack_for_slabs()
    tax, slices = allocate_progressive_slabs(Decimal("0"), pack.thresholds.apit_slabs)
    assert tax == Decimal("0")
    assert slices == []


def test_income_basis_prefers_estimated_taxable() -> None:
    p = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("9999999"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )
    assert income_basis_before_personal_relief(p) == Decimal("1800000")


def test_compute_apit_golden_no_deductions_48k() -> None:
    """1.8M basis, 1.2M personal relief → 600k taxable; first two MVP slabs → 48k."""
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )
    strategy = TaxOptBStrategyProposalV1(claims=[])
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert out.compliance.passed is True
    assert out.tax_computation is not None
    assert out.tax_computation.total_tax == "48000"
    assert out.tax_computation.taxable_after_personal_relief == "600000"
    assert out.tax_computation.total_allowed_deductions == "0"
    assert len(out.tax_computation.slab_slices) >= 2


def test_compute_apit_golden_life_insurance_39k() -> None:
    """600k after PR minus 50k allowed life → 550k taxable → 39k tax."""
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000"))],
    )
    out = run_compliance_and_compute_tax(profile, strategy, pack, rules_version_label="test")
    assert out.compliance.passed is True
    assert out.tax_computation is not None
    assert out.tax_computation.total_tax == "39000"
    assert out.tax_computation.total_allowed_deductions == "50000"
    assert out.tax_computation.taxable_after_deductions == "550000"


def test_compute_tax_when_compliance_fails_no_tax_block(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "strategy": {
            "claims": [{"relief_code": "life_insurance_premium", "claimed_amount_annual": "150000"}],
        },
    }
    resp = client.post("/api/v1/compliance/compute-tax", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliance"]["passed"] is False
    assert data["tax_computation"] is None
    assert "research" in data["research_disclaimer"].lower() or "MVP" in data["research_disclaimer"]


def test_http_compute_tax_from_financial_inputs_golden(client: TestClient) -> None:
    """Gross 2.4M, life 50k: basis 2.4M → after PR 1.2M → after ded 1.15M → tax 156k."""
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2000000",
        "annual_business_income": "400000",
        "annual_other_income": "0",
        "deductions": [{"relief_code": "life_insurance_premium", "amount_annual": "50000"}],
        "investments": [],
        "strategy_notes": None,
    }
    resp = client.post("/api/v1/compliance/compute-tax-from-financial-inputs", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliance"]["passed"] is True
    assert data["tax_computation"]["total_tax"] == "156000"
    assert data["compliance"]["mapped_profile"]["annual_gross_income"] == "2400000"
    assert data["compliance"]["mapped_profile"].get("estimated_annual_taxable_income") is None


def test_http_compute_tax_golden_48k(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "strategy": {"claims": []},
    }
    resp = client.post("/api/v1/compliance/compute-tax", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tax_computation"]["total_tax"] == "48000"


def test_compute_apit_liability_directly_uses_applied() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    profile = TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )
    applied = {
        "life_insurance_premium": {
            "relief_code": "life_insurance_premium",
            "claimed": "50000",
            "cap": "100000",
            "allowed": "50000",
        }
    }
    tax = compute_apit_liability(profile=profile, applied_relief=applied, pack=pack)
    assert tax.total_tax == "39000"
