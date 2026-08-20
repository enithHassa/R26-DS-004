"""Parametrized golden examples for the Adaptive Tax rule engine (file KG)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
from backend.shared.config.settings import PROJECT_ROOT

_EXAMPLES_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "examples"


def _example_files() -> list[Path]:
    return sorted(_EXAMPLES_DIR.glob("ex*.json"))


def _expand_cases(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a fixture (single case or ``variants[]``) into runnable cases."""
    if "variants" in doc:
        parent_id = str(doc.get("id") or "")
        cases: list[dict[str, Any]] = []
        for variant in doc["variants"]:
            case = {
                **variant,
                "parent_id": parent_id,
                "scenario": doc.get("scenario"),
                "assert_variants_differ": bool(doc.get("assert_variants_differ")),
            }
            cases.append(case)
        return cases
    return [doc]


def _all_cases() -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in _example_files():
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in _expand_cases(doc):
            case_id = str(case.get("id") or path.stem)
            out.append((case_id, case))
    return out


_CASES = _all_cases()


def test_examples_directory_has_named_mvp_and_phase5_files() -> None:
    files = _example_files()
    ids = [
        str(json.loads(path.read_text(encoding="utf-8"))["id"]) for path in files
    ]
    assert set(ids) >= {
        f"ex0{i}" for i in range(1, 10)
    } | {
        "ex12",
        "ex10",
        "ex11",
        "ex13",
        "ex14",
        "ex15",
        "ex16",
        "ex17",
        "ex18",
        "ex19",
        "ex20",
        "ex21",
        "ex22",
        "ex23",
        "ex24",
        "ex25",
        "ex26",
        "ex27",
        "ex30",
    }
    assert len(files) >= 30


@pytest.mark.parametrize("case_id,case", _CASES, ids=[c[0] for c in _CASES])
def test_named_example(case_id: str, case: dict[str, Any]) -> None:
    if case.get("skip_default_kg"):
        pytest.skip("stub File KG harness (ex28/ex29) lives in test_unresolved_claims.py")
    kg = default_file_kg()
    result = calculate(
        CalculateTaxRequestV1.model_validate(case["inputs"]),
        kg=kg,
    )

    assert result.final_tax_lkr == case["expected_final_tax_lkr"], case_id
    if "expected_tax_payable_lkr" in case:
        assert result.tax_payable_lkr == case["expected_tax_payable_lkr"], case_id
    else:
        assert result.tax_payable_lkr == result.final_tax_lkr, case_id
    if "expected_tax_credits_applied_lkr" in case:
        assert (
            result.tax_credits_applied_lkr == case["expected_tax_credits_applied_lkr"]
        ), case_id
    assert result.rules_applied == case["expected_rules_applied"], case_id

    actual_sources = {ref.id for ref in result.rule_source_refs}
    for sid in case.get("expected_rule_source_ids") or []:
        assert sid in actual_sources, f"{case_id}: missing rule_source_id {sid}"

    steps = {s.step_id: s for s in result.calculation_trace}

    for step_id, allowed in (case.get("expected_deduction_allowed") or {}).items():
        assert step_id in steps, f"{case_id}: missing step {step_id}"
        assert steps[step_id].inputs.get("allowed") == allowed

    if "expected_personal_relief" in case:
        assert steps["apply_personal_relief"].inputs["personal_relief"] == case[
            "expected_personal_relief"
        ]
    if "expected_taxable_after_relief" in case:
        assert steps["apply_personal_relief"].output == case["expected_taxable_after_relief"]
    if "expected_sum_assessable" in case:
        assert steps["sum_assessable"].output == case["expected_sum_assessable"]

    if "expected_qp_summary_final_allowable" in case:
        assert result.qualifying_payment_summary is not None
        assert (
            result.qualifying_payment_summary.final_allowable_deduction
            == case["expected_qp_summary_final_allowable"]
        )
    if "expected_qp_summary_before_sec52" in case:
        assert result.qualifying_payment_summary is not None
        assert (
            result.qualifying_payment_summary.total_allowable_before_sec52
            == case["expected_qp_summary_before_sec52"]
        )

    if "expected_qualifying_payment_carry_forward_out" in case:
        assert (
            result.qualifying_payment_carry_forward_out
            == case["expected_qualifying_payment_carry_forward_out"]
        )

    if "expected_cap_ceiling" in case:
        cap = steps.get("cap_donation_cap")
        assert cap is not None, f"{case_id}: missing cap_donation_cap step"
        assert cap.inputs.get("ceiling") == case["expected_cap_ceiling"]

    for cid, allowed in (case.get("expected_qp_category_allowable") or {}).items():
        cat = next(
            (c for c in result.qualifying_payment_categories if c.component_id == cid),
            None,
        )
        assert cat is not None, f"{case_id}: missing QP category {cid}"
        assert cat.allowable == allowed

    if "expected_investment_assessable" in case:
        excl = steps["exclude_investment_final_withholding"]
        assert excl.inputs["net_investment"] == case["expected_investment_assessable"]
    if "expected_rent_cap_inv_rents" in case:
        rent_cap = steps["cap_rent_relief"]
        assert rent_cap.inputs.get("inv_rents") == case["expected_rent_cap_inv_rents"]
    if "expected_rent_cap_ceiling" in case:
        rent_cap = steps["cap_rent_relief"]
        assert rent_cap.inputs.get("ceiling") == case["expected_rent_cap_ceiling"]
    if "expected_rent_statutory_allowed" in case:
        assert steps["cap_rent_relief"].inputs.get("allowed") == case[
            "expected_rent_statutory_allowed"
        ]
        assert steps["deduct_rent_relief"].inputs.get("allowed") != case[
            "expected_rent_statutory_allowed"
        ]
    if "expected_rent_allowed_not" in case:
        assert steps["deduct_rent_relief"].inputs.get("allowed") != case[
            "expected_rent_allowed_not"
        ]

    for concept in case.get("expected_assessable_concepts") or []:
        assert concept in steps["sum_assessable"].concept_ids

    if case_id == "ex12":
        excl = steps["exclude_employment_final_withholding"]
        assert excl.inputs["excluded"] == "200000"
        assert excl.inputs["net_employment"] == "1600000"
        assert excl.output == "1600000"
        assert steps["sum_assessable"].output == "1600000"
        assert any(
            "section_5" in u for u in excl.section_uids
        ), "ex12 exclusion must anchor Section 5"

    if case_id == "ex13":
        net = steps["compute_business_net"]
        assert net.output == "1800000"
        assert net.inputs["allowed_deductions"] == "200000"
        assert steps["sum_assessable"].output == "1800000"
        assert any("section_11" in u for u in net.section_uids)

    if case_id == "ex14":
        net = steps["compute_business_net"]
        assert net.output == "1800000"
        assert net.inputs["allowed_capital_allowances"] == "100000"
        assert any("section_16" in u for u in net.section_uids)

    if case_id == "ex24":
        agg = steps["aggregate_business_components"]
        assert agg.inputs.get("biz_gross") == "2000000"
        assert agg.inputs.get("biz_deductions") == "200000"
        net = steps["compute_business_net"]
        assert net.output == "1800000"
        assert net.inputs["allowed_deductions"] == "200000"
        assert steps["sum_assessable"].output == "1800000"
        assert any(c.component_id == "biz_gross" for c in result.component_trace)

    if case_id == "ex25":
        agg = steps["aggregate_other_income_components"]
        assert agg.inputs.get("oth_residual") == "1000000"
        assert steps["sum_assessable"].output == "1800000"
        assert any(c.component_id == "oth_custom" for c in result.component_trace)
        assert any("section_8" in u for u in steps["sum_assessable"].section_uids)

    if case_id == "ex16":
        excl = steps["exclude_investment_final_withholding"]
        assert excl.inputs["excluded"] == "200000"
        assert excl.inputs["net_investment"] == "1600000"
        assert excl.output == "1600000"
        assert steps["sum_assessable"].output == "1600000"
        assert any(
            "section_7" in u for u in excl.section_uids
        ), "ex16 exclusion must anchor Section 7"

    if case_id == "ex18":
        agg = steps["aggregate_employment_components"]
        assert agg.output == "1800000"
        assert agg.inputs.get("emp_salary") == "1600000"
        assert agg.inputs.get("emp_bonus") == "200000"
        assert steps["sum_assessable"].output == "1800000"
        assert result.knowledge_versions is not None
        assert result.knowledge_versions.catalog_version == "v1"
        assert any(c.component_id == "emp_salary" for c in result.component_trace)

    if case_id == "ex19":
        agg = steps["aggregate_employment_components"]
        assert agg.output == "1800000"
        excl = steps["exclude_employment_exempt_lines"]
        assert excl.output == "50000"
        assert excl.inputs.get("emp_medical_benefits") == "50000"
        assert steps["sum_assessable"].output == "1800000"
        medical = next(
            c for c in result.component_trace if c.component_id == "emp_medical_benefits"
        )
        assert medical.included_in_assessable is False
        assert medical.treatment_applied == "exempt"

    if case_id == "ex20":
        agg = steps["aggregate_investment_components"]
        assert agg.output == "1800000"
        assert agg.inputs.get("inv_dividends") == "1000000"
        assert agg.inputs.get("inv_interest") == "800000"
        assert steps["sum_assessable"].output == "1800000"
        assert any("section_7" in u for u in agg.section_uids)
        assert any(c.component_id == "inv_dividends" for c in result.component_trace)

    if case_id == "ex21":
        agg = steps["aggregate_investment_components"]
        assert agg.output == "1800000"
        excl = steps["exclude_investment_final_withholding"]
        assert excl.inputs["excluded"] == "200000"
        assert excl.inputs["net_investment"] == "1600000"
        assert steps["sum_assessable"].output == "1600000"
        fwh = next(
            c for c in result.component_trace if c.component_id == "inv_final_withholding"
        )
        assert fwh.included_in_assessable is False
        assert fwh.treatment_applied == "final_withholding"

    if case_id == "ex22":
        agg = steps["aggregate_qualifying_payment_components"]
        assert agg.output == "600000"
        assert agg.inputs.get("qp_government_sri_lanka") == "500000"
        assert agg.inputs.get("qp_samurdhi_shop") == "100000"
        assert any("section_52" in u for u in agg.section_uids)
        assert "evaluate_qualifying_payment_categories" in result.rules_applied
        assert result.qualifying_payment_summary is not None
        assert result.qualifying_payment_summary.final_allowable_deduction == "600000"
        assert result.qualifying_payment_carry_forward_out is None
        cat_ids = {c.component_id for c in result.qualifying_payment_categories}
        assert "qp_government_sri_lanka" in cat_ids
        assert "qp_samurdhi_shop" in cat_ids
        gov = next(
            c for c in result.qualifying_payment_categories if c.component_id == "qp_government_sri_lanka"
        )
        assert gov.sec52_4_eligible is False
        ya_steps = [
            s for s in result.calculation_trace if s.step_id.startswith("qp_category:")
        ]
        assert ya_steps
        assert all(s.inputs.get("assessment_year") == "2024_25" for s in ya_steps)

    if case_id == "ex23":
        cat = next(
            c
            for c in result.qualifying_payment_categories
            if c.component_id == "qp_approved_charitable"
        )
        assert cat.claimed == "2000000"
        assert cat.allowable == "75000"
        assert steps["deduct_qualifying_payment"].inputs.get("allowed") == "75000"

    order = case.get("expected_rule_order") or []
    if order:
        positions = [result.rules_applied.index(r) for r in order]
        assert positions == sorted(positions), f"{case_id}: rule order {order}"


def test_ex08_pre_and_current_taxes_differ() -> None:
    path = _EXAMPLES_DIR / "ex08_post_amendment_sec52.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc.get("assert_variants_differ") is True
    taxes: list[str] = []
    kg = default_file_kg()
    for variant in doc["variants"]:
        result = calculate(
            CalculateTaxRequestV1.model_validate(variant["inputs"]),
            kg=kg,
        )
        taxes.append(result.final_tax_lkr)
    assert taxes[0] != taxes[1]
    assert taxes == ["18000", "0"]
