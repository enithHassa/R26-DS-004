"""Tests for FR6 compare-strategies (ranking, baseline delta, failures last)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compare_strategies import compare_strategies
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1
from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import (
    TaxOptBCompareFromFinancialInputsRequestV1,
    TaxOptBCompareStrategiesRequestV1,
)


def _pack():
    return load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)


def _profile_1_8m_taxable():
    return TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )


def test_compare_ranking_pass_first_fail_last() -> None:
    pack = _pack()
    profile = _profile_1_8m_taxable()
    variants = [
        (
            "high_life",
            None,
            TaxOptBStrategyProposalV1(
                claims=[
                    TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("150000")),
                ],
            ),
        ),
        (
            "none",
            "no deductions",
            TaxOptBStrategyProposalV1(claims=[]),
        ),
        (
            "life50",
            None,
            TaxOptBStrategyProposalV1(
                claims=[
                    TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000")),
                ],
            ),
        ),
    ]
    out = compare_strategies(profile, variants, pack, rules_version_label="test")
    assert len(out.rows) == 3
    # Lowest tax first: 39k, 48k; then failing
    assert out.rows[0].variant_id == "life50"
    assert out.rows[0].rank == 1
    assert out.rows[0].total_tax == "39000"
    assert out.rows[1].variant_id == "none"
    assert out.rows[1].rank == 2
    assert out.rows[1].total_tax == "48000"
    assert out.rows[2].variant_id == "high_life"
    assert out.rows[2].passed is False
    assert out.rows[2].rank is None
    assert out.rows[2].total_tax is None
    assert out.rows[2].delta_total_tax_vs_baseline is None
    assert out.rows[0].result is not None and out.rows[0].result.tax_computation is not None


def test_compare_include_result_detail_false() -> None:
    pack = _pack()
    profile = _profile_1_8m_taxable()
    variants = [
        ("a", None, TaxOptBStrategyProposalV1(claims=[])),
    ]
    out = compare_strategies(
        profile,
        variants,
        pack,
        rules_version_label="test",
        include_result_detail=False,
    )
    assert out.rows[0].result is None
    assert out.rows[0].total_tax == "48000"


def test_compare_baseline_delta() -> None:
    pack = _pack()
    profile = _profile_1_8m_taxable()
    variants = [
        ("none", None, TaxOptBStrategyProposalV1(claims=[])),
        ("life50", None, TaxOptBStrategyProposalV1(
            claims=[TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("50000"))],
        )),
    ]
    out = compare_strategies(
        profile,
        variants,
        pack,
        baseline_variant_id="none",
        rules_version_label="test",
    )
    assert out.rows[0].variant_id == "life50"
    assert out.rows[0].delta_total_tax_vs_baseline == "-9000"
    assert out.rows[1].variant_id == "none"
    assert out.rows[1].delta_total_tax_vs_baseline == "0"


def test_compare_baseline_failed_no_deltas() -> None:
    pack = _pack()
    profile = _profile_1_8m_taxable()
    variants = [
        (
            "bad",
            None,
            TaxOptBStrategyProposalV1(
                claims=[
                    TaxOptBReliefClaimV1(relief_code="life_insurance_premium", claimed_amount_annual=Decimal("150000")),
                ],
            ),
        ),
        ("ok", None, TaxOptBStrategyProposalV1(claims=[])),
    ]
    out = compare_strategies(
        profile,
        variants,
        pack,
        baseline_variant_id="bad",
        rules_version_label="test",
    )
    assert out.rows[0].variant_id == "ok"
    assert out.rows[0].delta_total_tax_vs_baseline is None


def test_request_duplicate_variant_id_validation() -> None:
    with pytest.raises(ValidationError, match="unique variant_id"):
        TaxOptBCompareStrategiesRequestV1(
            profile=_profile_1_8m_taxable(),
            variants=[
                {"variant_id": "a", "strategy": {"claims": []}},
                {"variant_id": "a", "strategy": {"claims": []}},
            ],
        )


def test_request_baseline_not_in_variants_validation() -> None:
    with pytest.raises(ValidationError, match="baseline_variant_id"):
        TaxOptBCompareStrategiesRequestV1(
            profile=_profile_1_8m_taxable(),
            variants=[
                {"variant_id": "a", "strategy": {"claims": []}},
            ],
            baseline_variant_id="missing",
        )


def test_http_compare_strategies(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "variants": [
            {"variant_id": "v_none", "label": "A", "strategy": {"claims": []}},
            {
                "variant_id": "v_life",
                "strategy": {
                    "claims": [
                        {"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"},
                    ],
                },
            },
        ],
        "baseline_variant_id": "v_none",
    }
    resp = client.post("/api/v1/compliance/compare-strategies", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rows"][0]["variant_id"] == "v_life"
    assert data["rows"][0]["delta_total_tax_vs_baseline"] == "-9000"
    assert data["rows"][1]["delta_total_tax_vs_baseline"] == "0"


def test_http_compare_strategies_no_detail(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "variants": [{"variant_id": "x", "strategy": {"claims": []}}],
        "include_result_detail": False,
    }
    resp = client.post("/api/v1/compliance/compare-strategies", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["rows"][0]["result"] is None


def test_financial_compare_validation_requires_one_variant() -> None:
    with pytest.raises(ValidationError, match="at least one strategy_variant"):
        TaxOptBCompareFromFinancialInputsRequestV1(
            tax_year="2024_25",
            strategy_variants=[],
            include_mapped_strategy=False,
        )


def test_financial_compare_reserved_from_intake_id() -> None:
    with pytest.raises(ValidationError, match="from_intake"):
        TaxOptBCompareFromFinancialInputsRequestV1(
            tax_year="2024_25",
            strategy_variants=[{"variant_id": "from_intake", "strategy": {"claims": []}}],
            include_mapped_strategy=True,
            deductions=[],
            investments=[],
        )


def test_http_compare_from_financial_inputs_mapped_and_alt(client: TestClient) -> None:
    """Gross-only intake + mapped from_intake row vs explicit no-claims variant (156k vs path)."""
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2000000",
        "annual_business_income": "400000",
        "annual_other_income": "0",
        "deductions": [{"relief_code": "life_insurance_premium", "amount_annual": "50000"}],
        "investments": [],
        "include_mapped_strategy": True,
        "strategy_variants": [
            {
                "variant_id": "zero_ded",
                "label": "No deductions",
                "strategy": {"claims": []},
            },
        ],
        "baseline_variant_id": "from_intake",
    }
    resp = client.post("/api/v1/compliance/compare-strategies-from-financial-inputs", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert {r["variant_id"] for r in data["rows"]} == {"from_intake", "zero_ded"}
    # Lower tax first: zero deductions (176k?) vs 50k life on 2.4M gross → check ordering by total_tax
    by_id = {r["variant_id"]: r for r in data["rows"]}
    assert by_id["from_intake"]["passed"] is True
    assert by_id["from_intake"]["total_tax"] == "156000"
    assert by_id["zero_ded"]["total_tax"] == "168000"


def test_http_compare_unknown_relief_422(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "variants": [
            {
                "variant_id": "bad",
                "strategy": {"claims": [{"relief_code": "not_a_real_relief", "claimed_amount_annual": "1"}]},
            },
        ],
    }
    resp = client.post("/api/v1/compliance/compare-strategies", json=body)
    assert resp.status_code == 422
    assert "strategy claims" in resp.json()["detail"].lower()


def test_http_compare_strategies_empty_variants_422(client: TestClient) -> None:
    body = {
        "profile": {
            "tax_year": "2024_25",
            "employment_type": "employee",
            "dependents": 0,
            "annual_gross_income": "2400000",
            "estimated_annual_taxable_income": "1800000",
        },
        "variants": [],
    }
    resp = client.post("/api/v1/compliance/compare-strategies", json=body)
    assert resp.status_code == 422


def test_http_compare_from_financial_inputs_empty_variants_no_mapped_422(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "0",
        "annual_business_income": "0",
        "annual_other_income": "0",
        "deductions": [],
        "investments": [],
        "include_mapped_strategy": False,
        "strategy_variants": [],
    }
    resp = client.post("/api/v1/compliance/compare-strategies-from-financial-inputs", json=body)
    assert resp.status_code == 422


def test_http_compare_from_financial_inputs_unknown_relief_in_deductions_422(client: TestClient) -> None:
    """Same rejection pattern as check-from-financial-inputs / compute-tax-from-financial-inputs."""
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000",
        "deductions": [{"relief_code": "not_a_real_code", "amount_annual": "1"}],
        "investments": [],
        "include_mapped_strategy": True,
        "strategy_variants": [{"variant_id": "x", "strategy": {"claims": []}}],
    }
    resp = client.post("/api/v1/compliance/compare-strategies-from-financial-inputs", json=body)
    assert resp.status_code == 422
    detail = resp.json().get("detail", "")
    assert "deductions or investments" in detail.lower()


def test_http_compare_from_financial_inputs_unknown_relief_in_variant_422(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000000",
        "deductions": [],
        "investments": [],
        "include_mapped_strategy": False,
        "strategy_variants": [
            {
                "variant_id": "bad",
                "strategy": {"claims": [{"relief_code": "bogus_relief_xyz", "claimed_amount_annual": "1"}]},
            },
        ],
    }
    resp = client.post("/api/v1/compliance/compare-strategies-from-financial-inputs", json=body)
    assert resp.status_code == 422
    assert "strategy claims" in resp.json()["detail"].lower()


def test_http_compare_presets_from_financial_inputs(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2000000",
        "annual_business_income": "400000",
        "annual_other_income": "0",
        "deductions": [{"relief_code": "life_insurance_premium", "amount_annual": "50000"}],
        "investments": [],
    }
    resp = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["baseline_variant_id"] == "no_claims"
    ids = {r["variant_id"] for r in data["rows"]}
    assert ids == {"user_proposed", "no_claims", "max_caps_mvp"}
    by_id = {r["variant_id"]: r for r in data["rows"]}
    assert by_id["no_claims"]["delta_total_tax_vs_baseline"] == "0"
    assert all(r["passed"] for r in data["rows"])


def test_http_compare_presets_invalid_baseline_422(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000000",
        "deductions": [],
        "investments": [],
        "presets": ["max_caps_mvp"],
        "baseline_variant_id": "no_claims",
    }
    resp = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    assert resp.status_code == 422
    err = resp.json()
    detail_raw = err.get("detail", "")
    detail_text = detail_raw if isinstance(detail_raw, str) else str(detail_raw).lower()
    assert "baseline" in detail_text.lower()


def test_http_compare_presets_explanations_include_preset_section(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000000",
        "deductions": [],
        "investments": [],
        "presets": ["user_proposed", "no_claims"],
        "include_explanations": True,
    }
    resp = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    assert resp.status_code == 200, resp.text
    exp = resp.json().get("explanations")
    assert exp is not None
    titles = [s["title"] for s in exp.get("sections", [])]
    assert "Strategy presets (MVP)" in titles


def test_http_compare_presets_empty_presets_422(client: TestClient) -> None:
    body = {
        "tax_year": "2024_25",
        "annual_salary_income": "1000000",
        "deductions": [],
        "investments": [],
        "presets": [],
    }
    resp = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    assert resp.status_code == 422


def test_http_compare_presets_row_order_is_deterministic(client: TestClient) -> None:
    """Same payload yields identical ``rows[].variant_id`` ordering (FR6 rank sort is stable)."""
    body = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2000000",
        "annual_business_income": "400000",
        "annual_other_income": "0",
        "deductions": [{"relief_code": "life_insurance_premium", "amount_annual": "50000"}],
        "investments": [],
    }
    r1 = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    r2 = client.post("/api/v1/compliance/compare-presets-from-financial-inputs", json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    ids1 = [row["variant_id"] for row in r1.json()["rows"]]
    ids2 = [row["variant_id"] for row in r2.json()["rows"]]
    assert ids1 == ids2
    assert set(ids1) == {"user_proposed", "no_claims", "max_caps_mvp"}
