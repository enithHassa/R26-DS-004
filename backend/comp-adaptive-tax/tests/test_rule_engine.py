"""Unit tests for the Adaptive Tax Phase 3 rule engine (no GPT, file KG)."""

from __future__ import annotations

from decimal import Decimal

import pytest

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


def test_band_widths_match_act_verified_slices() -> None:
    pack = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    widths = [_band_width(b) for b in pack.rate_bands]
    assert len(pack.rate_bands) == 6
    assert widths[:5] == [
        Decimal("500000"),
        Decimal("500000"),
        Decimal("500000"),
        Decimal("500000"),
        Decimal("500000"),
    ]
    assert widths[5] is None
    assert pack.rate_bands[1].rate == Decimal("0.12")
    assert all(b.rule_source_id for b in pack.rate_bands)

    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert len(ya25.rate_bands) == 5
    assert ya25.rate_bands[0].upper == 1000000
    assert ya25.rate_bands[0].rate == Decimal("0.06")
    assert ya25.rate_bands[1].rate == Decimal("0.18")  # no 12% band
    assert _band_width(ya25.rate_bands[0]) == Decimal("1000000")


def test_golden_employment_1800000_tax_42000() -> None:
    """Act-verified YA 2024/25: 1.8M − 1.2M PR = 600k → 30k@6% + 12k@12% = 42_000."""
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="1800000",
    )
    assert result.final_tax_lkr == "42000"
    steps = _step_map(result)
    assert steps["sum_assessable"].output == "1800000"
    assert steps["apply_personal_relief"].inputs["personal_relief"] == "1200000"
    assert steps["apply_personal_relief"].output == "600000"
    assert steps["slab_band_1"].inputs["taxable_in_slice"] == "500000"
    assert steps["slab_band_1"].output == "30000"  # 500k * 6%
    assert steps["slab_band_2"].inputs["taxable_in_slice"] == "100000"
    assert steps["slab_band_2"].output == "12000"  # 100k * 12%
    assert "slab_band_3" not in steps
    assert result.rules_applied[0] == "sum_assessable"
    assert "apply_personal_relief" in result.rules_applied
    assert result.rules_applied[-1] == "final_tax"
    assert steps["slab_band_1"].rule_source_ids
    assert any("first_schedule" in (s or "") for s in steps["slab_band_1"].section_uids)


def test_business_income_same_path_as_employment() -> None:
    result = _calc(business_income="1800000", resident_status="resident")
    assert result.final_tax_lkr == "42000"
    assert "business_income" in _step_map(result)["sum_assessable"].concept_ids


def test_section52_qualifying_payment_full_deduct() -> None:
    # Assessable 3M, QP claimed 2.5M → full deduct (no aggregate cap).
    result = _calc(
        assessment_year="2025_26",
        employment_income="3000000",
        qualifying_payments="2500000",
        resident_status="resident",
        param_set="current",
    )
    steps = _step_map(result)
    assert "cap_qualifying_payment_cap" not in result.rules_applied
    assert steps["deduct_qualifying_payment"].inputs["allowed"] == "2500000"
    assert any("section_52" in u for u in steps["deduct_qualifying_payment"].section_uids)
    assert result.final_tax_lkr == "0"


def test_donation_folds_into_1a_on_assessable() -> None:
    # Assessable 3M → 1(a) min(2M, 75k, floor(3M/3)=1M) = 75,000.
    result = _calc(
        employment_income="3000000",
        donations="2000000",
        resident_status="resident",
    )
    steps = _step_map(result)
    assert "cap_donation_cap" not in result.rules_applied
    assert steps["deduct_qualifying_payment"].inputs["allowed"] == "75000"
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.allowable == "75000"
    # 3M - 75k = 2_925_000; − 1.2M PR = 1_725_000 taxable
    assert steps["apply_personal_relief"].output == "1725000"
    assert result.final_tax_lkr == "234000"


def test_donation_floor_rounds_down() -> None:
    assert _floor1(Decimal("0.33")) == Decimal("0")
    assert _floor1(Decimal("990000.9")) == Decimal("990000")


def test_combined_qp_donation_relief_ordering() -> None:
    result = _calc(
        employment_income="4000000",
        resident_status="resident",
        filing_lines=[
            {"component_id": "qp_government_sri_lanka", "amount": "500000"},
            {"component_id": "qp_approved_charitable", "amount": "100000"},
        ],
    )
    rules = result.rules_applied
    assert rules.index("deduct_qualifying_payment") < rules.index("apply_personal_relief")
    assert "deduct_donation" not in rules
    # 1(a) 75k + 1(b) 500k = 575k QP; then PR — 1(b) is not limited by the 75k 1(a) ceiling
    assert _step_map(result)["deduct_qualifying_payment"].inputs["allowed"] == "575000"


def test_non_resident_skips_personal_relief() -> None:
    result = _calc(
        employment_income="1800000",
        resident_status="non_resident",
    )
    steps = _step_map(result)
    assert steps["apply_personal_relief"].inputs["personal_relief"] == "0"
    assert steps["apply_personal_relief"].output == "1800000"
    # 500k*6% + 500k*12% + 500k*18% + 300k*24% = 30k+60k+90k+72k = 252_000
    assert result.final_tax_lkr == "252000"


def test_high_income_hits_remainder_band() -> None:
    result = _calc(employment_income="5000000", resident_status="resident")
    steps = _step_map(result)
    assert "slab_band_6" in steps
    assert steps["slab_band_6"].inputs["width"] == "null"
    # taxable = 5M - 1.2M = 3.8M under Act-verified 6-band YA 2024/25 schedule
    assert result.final_tax_lkr == "918000"


def test_dual_ya_personal_relief_drives_tax_delta() -> None:
    shared = {
        "employment_income": "3000000",
        "qualifying_payments": "1500000",
        "resident_status": "resident",
        "param_set": "current",
    }
    ya24 = _calc(**shared, assessment_year="2024_25")
    ya25 = _calc(**shared, assessment_year="2025_26")
    assert _step_map(ya24)["deduct_qualifying_payment"].inputs["allowed"] == "1500000"
    assert _step_map(ya25)["deduct_qualifying_payment"].inputs["allowed"] == "1500000"
    assert ya24.final_tax_lkr == "18000"
    assert ya25.final_tax_lkr == "0"


def test_dual_ya_param_packs_personal_relief() -> None:
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert ya24.relief_for_concept("qualifying_payment_cap") is None
    assert ya25.relief_for_concept("qualifying_payment_cap") is None
    assert ya24.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")
    assert ya25.relief_for_concept("personal_relief").cap_amount == Decimal("1800000")
    assert len(ya24.rate_bands) == 6
    assert len(ya25.rate_bands) == 5


def test_empty_live_graph_does_not_fall_back_to_file_kg() -> None:
    """Incomplete Neo4j graph must not silently switch to file ontology."""

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
    assert result.final_tax_lkr == "0"
    assert "sum_assessable" in result.rules_applied


def test_neo4j_connection_refused_propagates() -> None:
    """Bolt refused must surface — no offline file-ontology fallback."""

    class DownKg:
        def resolve_applicable_concepts(self, *, income_types, claimed_deductions):
            raise ConnectionRefusedError(
                "[WinError 10061] No connection could be made because the "
                "target machine actively refused it"
            )

    with pytest.raises(ConnectionRefusedError):
        calculate(
            CalculateTaxRequestV1.model_validate(
                {
                    "employment_income": "1800000",
                    "resident_status": "resident",
                }
            ),
            kg=DownKg(),  # type: ignore[arg-type]
        )


def test_solar_400k_resident() -> None:
    result = _calc(
        employment_income="3000000",
        solar_panel_relief="400000",
        resident_status="resident",
    )
    steps = _step_map(result)
    assert steps["cap_solar_panel_relief"].inputs["allowed"] == "400000"
    assert steps["deduct_solar_panel_relief"].inputs["allowed"] == "400000"
    assert result.unresolved_claims == []
    # 3M − 400k − 1.2M PR = 1.4M → 30k+60k+72k = 162,000
    assert result.final_tax_lkr == "162000"


def test_solar_900k_capped_at_600k() -> None:
    result = _calc(
        employment_income="3000000",
        solar_panel_relief="900000",
        resident_status="resident",
    )
    assert _step_map(result)["cap_solar_panel_relief"].inputs["allowed"] == "600000"
    # 3M − 600k − 1.2M = 1.2M → 30k+60k+36k = 126,000
    assert result.final_tax_lkr == "126000"


def test_solar_non_resident_zero() -> None:
    result = _calc(
        employment_income="3000000",
        solar_panel_relief="900000",
        resident_status="non_resident",
    )
    assert _step_map(result)["cap_solar_panel_relief"].inputs["allowed"] == "0"
    assert _step_map(result)["apply_personal_relief"].inputs["personal_relief"] == "0"
    # 3M full taxable, 6 bands → 630,000
    assert result.final_tax_lkr == "630000"


def test_rent_25_pct_of_included_rents_not_reduced_by_fwh() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="2000000",
        filing_lines=[
            {"component_id": "inv_rents", "amount": "1000000"},
            {"component_id": "inv_final_withholding", "amount": "200000"},
            {"component_id": "relief_rent", "amount": "300000"},
        ],
    )
    steps = _step_map(result)
    assert steps["sum_assessable"].output == "2800000"  # 2M emp + 800k investment
    assert steps["exclude_investment_final_withholding"].inputs["net_investment"] == "800000"
    assert steps["cap_rent_relief"].inputs["inv_rents"] == "1000000"
    assert steps["cap_rent_relief"].inputs["ceiling"] == "250000"
    assert steps["cap_rent_relief"].inputs["allowed"] == "250000"
    # 25% of post-FWH net investment (800k) would be 200k — must not be the cap.
    assert steps["cap_rent_relief"].inputs["allowed"] != "200000"
    # 2.8M − 250k − 1.2M = 1.35M → 30+60+63 = 153,000
    assert result.final_tax_lkr == "153000"


def test_deduction_order_qp_solar_rent_personal() -> None:
    result = _calc(
        employment_income="4000000",
        resident_status="resident",
        filing_lines=[
            {"component_id": "qp_approved_charitable", "amount": "75000"},
            {"component_id": "inv_rents", "amount": "400000"},
            {"component_id": "relief_solar_panel", "amount": "400000"},
            {"component_id": "relief_rent", "amount": "100000"},
        ],
    )
    rules = result.rules_applied
    assert rules.index("deduct_qualifying_payment") < rules.index(
        "deduct_solar_panel_relief"
    )
    assert rules.index("deduct_solar_panel_relief") < rules.index("deduct_rent_relief")
    assert rules.index("deduct_rent_relief") < rules.index("apply_personal_relief")
