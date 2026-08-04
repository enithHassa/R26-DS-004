"""Unit tests for the Adaptive Tax Phase 3 rule engine (no GPT, file KG)."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.param_store import load_tax_param_pack
from adaptive_tax_app.services.rule_engine import (
    _band_width,
    _floor1,
    calculate,
    default_file_kg,
)


def _calc(**kwargs: object):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def _step_map(result):
    return {s.step_id: s for s in result.calculation_trace}


def test_band_widths_match_comp_b_500k_slices() -> None:
    pack = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    widths = [_band_width(b) for b in pack.rate_bands]
    assert widths[:4] == [
        Decimal("500000"),
        Decimal("500000"),
        Decimal("500000"),
        Decimal("500000"),
    ]
    assert widths[4] is None


def test_golden_employment_1800000_tax_48000() -> None:
    """Comp B informal cross-check: 1.8M − 1.2M PR = 600k → 48_000 tax."""
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
    )
    assert result.final_tax_lkr == "48000"
    steps = _step_map(result)
    assert steps["sum_assessable"].output == "1800000"
    assert steps["apply_personal_relief"].inputs["personal_relief"] == "1200000"
    assert steps["apply_personal_relief"].output == "600000"
    assert steps["slab_band_1"].inputs["taxable_in_slice"] == "500000"
    assert steps["slab_band_1"].output == "30000"  # 500k * 6%
    assert steps["slab_band_2"].inputs["taxable_in_slice"] == "100000"
    assert steps["slab_band_2"].output == "18000"  # 100k * 18%
    assert "slab_band_3" not in steps
    assert result.rules_applied[0] == "sum_assessable"
    assert "apply_personal_relief" in result.rules_applied
    assert result.rules_applied[-1] == "final_tax"


def test_business_income_same_path_as_employment() -> None:
    result = _calc(business_income="1800000", resident_status="resident")
    assert result.final_tax_lkr == "48000"
    assert "business_income" in _step_map(result)["sum_assessable"].concept_ids


def test_section52_qualifying_payment_cap() -> None:
    # Assessable 3M, QP claimed 2.5M → allowed 1.8M (current param set).
    result = _calc(
        employment_income="3000000",
        qualifying_payments="2500000",
        resident_status="resident",
        param_set="current",
    )
    steps = _step_map(result)
    assert "cap_qualifying_payment_cap" in result.rules_applied
    assert steps["deduct_qualifying_payment"].inputs["allowed"] == "1800000"
    assert any("section_52" in u for u in steps["deduct_qualifying_payment"].section_uids)
    # after QP: 3M - 1.8M = 1.2M; − PR 1.2M = 0 tax
    assert result.final_tax_lkr == "0"


def test_donation_cap_floor_33_pct_of_assessable() -> None:
    # Assessable 3M → floor(0.33*3M)=990_000; claim 2M → allowed 990_000.
    result = _calc(
        employment_income="3000000",
        donations="2000000",
        resident_status="resident",
    )
    steps = _step_map(result)
    assert "cap_donation_cap" in result.rules_applied
    assert steps["deduct_donation"].inputs["allowed"] == "990000"
    assert "floor(assessable" in steps["deduct_donation"].formula
    # 3M - 990k = 2_010_000; − 1.2M PR = 810_000 taxable
    assert steps["apply_personal_relief"].output == "810000"


def test_donation_floor_rounds_down() -> None:
    assert _floor1(Decimal("0.33")) == Decimal("0")
    assert _floor1(Decimal("990000.9")) == Decimal("990000")


def test_combined_qp_donation_relief_ordering() -> None:
    result = _calc(
        employment_income="4000000",
        qualifying_payments="500000",
        donations="100000",
        resident_status="resident",
    )
    rules = result.rules_applied
    assert rules.index("deduct_qualifying_payment") < rules.index("deduct_donation")
    assert rules.index("deduct_donation") < rules.index("apply_personal_relief")
    assert rules.index("apply_personal_relief") < rules.index("slab_band_1")


def test_non_resident_skips_personal_relief() -> None:
    result = _calc(
        employment_income="1800000",
        resident_status="non_resident",
    )
    steps = _step_map(result)
    assert steps["apply_personal_relief"].inputs["personal_relief"] == "0"
    assert steps["apply_personal_relief"].output == "1800000"
    # 500k*6% + 500k*18% + 500k*24% + 300k*30% = 30k+90k+120k+90k = 330_000
    assert result.final_tax_lkr == "330000"


def test_high_income_hits_remainder_band() -> None:
    result = _calc(employment_income="5000000", resident_status="resident")
    steps = _step_map(result)
    assert "slab_band_5" in steps
    assert steps["slab_band_5"].inputs["width"] == "null"
    # taxable = 5M - 1.2M = 3.8M
    # 500k*6 + 500k*18 + 500k*24 + 500k*30 + 1.8M*36
    # = 30k + 90k + 120k + 150k + 648k = 1_038_000
    assert result.final_tax_lkr == "1038000"


def test_pre_amend_sec52_cap_differs_from_current() -> None:
    shared = {
        "employment_income": "3000000",
        "qualifying_payments": "1500000",
        "resident_status": "resident",
    }
    pre = _calc(**shared, param_set="pre_amend_2025")
    cur = _calc(**shared, param_set="current")
    assert _step_map(pre)["deduct_qualifying_payment"].inputs["allowed"] == "1200000"
    assert _step_map(cur)["deduct_qualifying_payment"].inputs["allowed"] == "1500000"
    assert pre.final_tax_lkr != cur.final_tax_lkr


def test_falls_back_to_file_kg_when_live_graph_misses_incomes() -> None:
    """Neo4j without CONTRIBUTES_TO edges must not silently yield tax 0."""

    class EmptyKg:
        def resolve_applicable_concepts(self, *, income_types, claimed_deductions):
            from adaptive_tax_app.services.kg_client import ApplicableConcepts

            return ApplicableConcepts(
                income_concept_ids=(),
                deductions=(),
                income_section_uids={},
                resident_individual_present=True,
            )

    result = calculate(
        CalculateTaxRequestV1.model_validate(
            {
                "employment_income": "1900000",
                "resident_status": "resident",
            }
        ),
        kg=EmptyKg(),  # type: ignore[arg-type]
    )
    # 1.9M − 1.2M PR = 700k → 500k*6% + 200k*18% = 30k + 36k = 66_000
    assert result.final_tax_lkr == "66000"
    assert "slab_band_1" in result.rules_applied
