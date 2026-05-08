"""Tests for Function 2 strategy search (enumerated grid, passing-only)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compare_strategies import compare_strategies
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.services.tax_opt_b_search_strategies import (
    enumerate_candidate_specs,
    search_space_id,
    search_strategies_from_financial_inputs,
)
from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import profile_from_financial_inputs
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import TaxOptBSearchStrategiesFromFinancialInputsRequestV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1


def _pack():
    return load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)


def _profile():
    return TaxOptBProfileV1(
        tax_year="2024_25",
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
    )


def _financial_body(**overrides):
    base = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2400000",
        "annual_business_income": "0",
        "annual_other_income": "0",
        "deductions": [],
        "investments": [],
        "top_k": 64,
        "rank_by": "total_tax",
        "max_candidates": 500,
        "include_result_detail": True,
        "include_explanations": False,
    }
    base.update(overrides)
    return base


def test_enumerate_candidate_specs_count_mvp_yaml() -> None:
    pack = _pack()
    profile = _profile()
    specs = enumerate_candidate_specs(profile, pack, max_candidates=500)
    assert len(specs) == 64
    assert specs[0].candidate_id == "cap_subset_0"
    assert specs[0].included_relief_codes == ()
    assert specs[-1].candidate_id == "cap_subset_63"


def test_enumerate_raises_when_grid_exceeds_max_candidates() -> None:
    pack = _pack()
    profile = _profile()
    with pytest.raises(ValueError, match="exceeds max_candidates"):
        enumerate_candidate_specs(profile, pack, max_candidates=32)


def test_search_space_id_stable() -> None:
    pack = _pack()
    profile = _profile()
    amounts = __import__(
        "tax_opt_b_app.services.tax_opt_b_financial_strategy_presets",
        fromlist=["relief_max_claim_amounts_by_code"],
    ).relief_max_claim_amounts_by_code(profile, pack)
    ordered = tuple(sorted(amounts.keys()))
    a = search_space_id(profile, ordered)
    b = search_space_id(profile, ordered)
    assert a == b
    assert len(a) == 16


def test_search_only_passing_rows_with_detail() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(_financial_body(top_k=64))
    out = search_strategies_from_financial_inputs(
        body,
        pack,
        rules_version_label="test",
    )
    assert out.candidates_evaluated == 64
    assert out.passing_count == len(out.rows)
    assert all(r.result is not None for r in out.rows)
    assert all(r.result.compliance.passed for r in out.rows)  # type: ignore[union-attr]
    assert out.baseline_candidate_id == "cap_subset_0"
    assert out.best_candidate_id == out.rows[0].candidate_id
    assert all(r.display_name for r in out.rows)
    baseline_row = next(r for r in out.rows if r.candidate_id == "cap_subset_0")
    assert "Baseline" in baseline_row.display_name
    assert baseline_row.metrics is not None
    assert baseline_row.metrics.tax_savings_vs_baseline_lkr == "0"
    assert out.traceability is not None
    assert out.traceability.search_space_id == out.search_space_id
    assert out.comparison_summary
    assert out.optimization_meta is not None
    om = out.optimization_meta
    assert om.strategies_evaluated == 64
    assert om.legal_strategies_count == out.passing_count
    assert om.rejected_strategies_count + om.legal_strategies_count == om.strategies_evaluated
    assert om.reproducibility_id == out.search_space_id
    assert om.optimization_objective == "minimize_total_tax"
    assert out.top_rank_explanation is not None
    assert out.top_rank_explanation.headline
    assert len(out.top_rank_explanation.bullets) >= 4
    for r in out.rows:
        assert r.metrics is not None
        assert r.breakdown is not None
        assert r.breakdown.employment_income_lkr == "2400000"
        assert r.breakdown.gross_income_lkr == r.metrics.gross_income
        assert r.breakdown.assessable_income_lkr == r.metrics.income_basis_before_personal_relief
        assert r.optimization_summary
        assert r.rule_summary
        assert isinstance(r.rule_trace, list)
        assert len(r.rule_trace) >= 1
        assert r.rule_trace[-1].rule_id == "search:compliance_bundle"
        assert r.rule_trace[-1].outcome == "passed"
        assert r.rule_trace[-1].short_label
        for t in r.rule_trace:
            assert t.outcome == "passed"
            assert t.short_label
        if r.included_relief_codes:
            assert len(r.rule_trace) >= 2


def test_search_optimization_meta_effective_rate_objective() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(
        _financial_body(top_k=5, rank_by="effective_rate"),
    )
    out = search_strategies_from_financial_inputs(body, pack, rules_version_label="test")
    assert out.optimization_meta is not None
    assert out.optimization_meta.optimization_objective == "minimize_effective_tax_rate"


def test_search_top_k_truncates() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(_financial_body(top_k=3))
    out = search_strategies_from_financial_inputs(body, pack, rules_version_label="test")
    assert out.passing_count >= 3
    assert len(out.rows) == 3
    assert out.rows[0].rank == 1
    assert out.rows[2].rank == 3


def test_search_include_result_detail_false() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(
        _financial_body(top_k=2, include_result_detail=False),
    )
    out = search_strategies_from_financial_inputs(body, pack, rules_version_label="test")
    assert all(r.result is None for r in out.rows)
    assert all(r.metrics is None for r in out.rows)
    assert all(r.breakdown is None for r in out.rows)
    assert all(r.display_name for r in out.rows)


def test_search_baseline_delta_zero_for_baseline_row() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(_financial_body(top_k=64))
    out = search_strategies_from_financial_inputs(body, pack, rules_version_label="test")
    baseline_row = next(r for r in out.rows if r.candidate_id == "cap_subset_0")
    assert baseline_row.delta_total_tax_vs_baseline == "0"


def test_search_invalid_baseline_candidate_id() -> None:
    pack = _pack()
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(
        _financial_body(baseline_candidate_id="not_in_grid"),
    )
    with pytest.raises(ValueError, match="not in the search grid"):
        search_strategies_from_financial_inputs(body, pack)


def test_search_aligned_with_compare_top_ranked() -> None:
    """Full passing set sorted by total_tax should match compare_strategies order."""
    pack = _pack()
    fin = TaxOptBFinancialInputsV1.model_validate(_financial_body())
    profile = profile_from_financial_inputs(fin)
    amounts = __import__(
        "tax_opt_b_app.services.tax_opt_b_financial_strategy_presets",
        fromlist=["relief_max_claim_amounts_by_code"],
    ).relief_max_claim_amounts_by_code(profile, pack)
    specs = enumerate_candidate_specs(profile, pack, max_candidates=500)
    variants: list[tuple[str, str | None, TaxOptBStrategyProposalV1]] = []
    for spec in specs:
        variants.append((spec.candidate_id, spec.label, spec.to_strategy_proposal(amounts)))
    compared = compare_strategies(
        profile,
        variants,
        pack,
        rules_version_label="test",
        include_result_detail=False,
    )
    passing_compare = [r for r in compared.rows if r.passed and r.rank is not None]
    body = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(_financial_body(top_k=64))
    searched = search_strategies_from_financial_inputs(body, pack, rules_version_label="test")
    assert len(passing_compare) == searched.passing_count
    for a, b in zip(passing_compare, searched.rows, strict=True):
        assert a.variant_id == b.candidate_id
        assert a.total_tax == b.total_tax


def test_search_strategies_api(client: TestClient) -> None:
    r = client.post(
        "/api/v1/compliance/search-strategies-from-financial-inputs",
        json=_financial_body(top_k=5),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["candidates_evaluated"] == 64
    assert data["passing_count"] >= 5
    assert len(data["rows"]) == 5
    assert data["baseline_candidate_id"] == "cap_subset_0"
    assert data["rows"][0]["rank"] == 1


def test_search_strategies_api_max_candidates_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/compliance/search-strategies-from-financial-inputs",
        json=_financial_body(max_candidates=32),
    )
    assert r.status_code == 422
    assert "max_candidates" in r.json()["detail"].lower() or "exceeds" in r.json()["detail"].lower()


def test_search_strategies_api_explanations_when_requested(client: TestClient) -> None:
    r = client.post(
        "/api/v1/compliance/search-strategies-from-financial-inputs",
        json=_financial_body(top_k=2, include_explanations=True, explanation_detail="summary"),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("explanations") is not None
    assert "summary" in data["explanations"]
