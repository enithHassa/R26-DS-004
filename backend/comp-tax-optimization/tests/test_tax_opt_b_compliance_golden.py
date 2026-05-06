"""Golden / regression tests for compliance (HTTP + real MVP rules file).

Violation **ordering** matches the engine: (1) tax year mismatch, (2) unknown
relief codes in sorted claim-key order, (3) rules list order for cap checks.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules


def test_mvp_rules_file_loads_as_expected_pack() -> None:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    assert pack.thresholds.personal_relief_annual == Decimal("1200000")
    assert len(pack.thresholds.apit_slabs) == 5
    assert pack.thresholds.deductions["life_insurance_premium_cap_annual"] == Decimal("100000")
    types = {r.rule_type for r in pack.rules}
    assert "deduction_cap" in types
    assert "charitable_donation_cap" in types
    assert "retirement_contribution_cap" in types


def _base_profile(**kwargs: object) -> dict:
    base = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_gross_income": "2400000",
        "estimated_annual_taxable_income": "1800000",
    }
    base.update(kwargs)
    return base


def test_golden_pass_multiple_claims_under_caps(client: TestClient) -> None:
    body = {
        "profile": _base_profile(),
        "strategy": {
            "claims": [
                {"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"},
                {"relief_code": "health_insurance_premium", "claimed_amount_annual": "50000"},
            ],
            "notes": None,
        },
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["violations"] == []
    assert "life_insurance_premium" in data["applied_relief"]
    assert "health_insurance_premium" in data["applied_relief"]


def test_golden_fail_life_insurance_message_and_rule_id(client: TestClient) -> None:
    body = {
        "profile": _base_profile(),
        "strategy": {
            "claims": [{"relief_code": "life_insurance_premium", "claimed_amount_annual": "150000"}],
        },
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert data["applied_relief"] == {}
    assert len(data["violations"]) == 1
    v0 = data["violations"][0]
    assert v0["rule_id"] == "it22064486_optb_cap_life_ins_001"
    assert v0["severity"] == "error"
    assert "exceeds" in v0["message"].lower()
    assert "life insurance" in v0["message"].lower()


def test_golden_fail_tax_year_first_in_order(client: TestClient) -> None:
    body = {
        "profile": _base_profile(tax_year="2025_26"),
        "strategy": {
            "claims": [
                {"relief_code": "magic_deduction", "claimed_amount_annual": "1"},
            ],
        },
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    ids = [v["rule_id"] for v in data["violations"]]
    assert ids[0] == "it22064486_optb_year_001"
    assert "it22064486_optb_unknown_relief_001" in ids


def test_golden_unknown_relief_code_message(client: TestClient) -> None:
    body = {
        "profile": _base_profile(),
        "strategy": {"claims": [{"relief_code": "magic_deduction", "claimed_amount_annual": "1"}]},
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert len(data["violations"]) == 1
    v0 = data["violations"][0]
    assert v0["rule_id"] == "it22064486_optb_unknown_relief_001"
    assert "magic_deduction" in v0["message"]


def test_golden_retirement_cap_rule_id(client: TestClient) -> None:
    # 15% of 2.4M = 360k < 600k cap
    body = {
        "profile": _base_profile(annual_gross_income="2400000"),
        "strategy": {"claims": [{"relief_code": "retirement_contribution", "claimed_amount_annual": "400000"}]},
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert any(v["rule_id"] == "it22064486_optb_cap_retirement_001" for v in data["violations"])


def test_golden_charitable_donation_cap_rule_id(client: TestClient) -> None:
    # 33% of 1.8M = 594000
    body = {
        "profile": _base_profile(estimated_annual_taxable_income="1800000"),
        "strategy": {"claims": [{"relief_code": "charitable_donations", "claimed_amount_annual": "600000"}]},
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert any(v["rule_id"] == "it22064486_optb_cap_donations_001" for v in data["violations"])


def test_golden_pass_all_allowed_relief_codes_under_caps(client: TestClient) -> None:
    body = {
        "profile": _base_profile(),
        "strategy": {
            "claims": [
                {"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"},
                {"relief_code": "health_insurance_premium", "claimed_amount_annual": "50000"},
                {"relief_code": "home_loan_interest", "claimed_amount_annual": "100000"},
                {"relief_code": "rent_relief", "claimed_amount_annual": "100000"},
                {"relief_code": "charitable_donations", "claimed_amount_annual": "500000"},
                {"relief_code": "retirement_contribution", "claimed_amount_annual": "300000"},
            ],
            "notes": "Golden — all MVP caps satisfied",
        },
    }
    resp = client.post("/api/v1/compliance/check", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["violations"] == []
    for code in (
        "life_insurance_premium",
        "health_insurance_premium",
        "home_loan_interest",
        "rent_relief",
        "charitable_donations",
        "retirement_contribution",
    ):
        assert code in data["applied_relief"]
