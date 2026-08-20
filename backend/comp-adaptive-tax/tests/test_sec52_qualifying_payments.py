"""Phase 5.4 / 6.3 — Section 52 QP deduct + Sec 52(4) category CF (Path B: no aggregate cap)."""



from __future__ import annotations



from decimal import Decimal



from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1

from adaptive_tax_app.services.param_store import clear_param_store_cache, load_tax_param_pack

from adaptive_tax_app.services.provenance import clear_provenance_cache

from adaptive_tax_app.services.rule_engine import calculate, default_file_kg





def test_personal_relief_packs_versioned_by_ya() -> None:

    clear_param_store_cache()

    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")

    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")

    pr24 = ya24.relief_for_concept("personal_relief")

    pr25 = ya25.relief_for_concept("personal_relief")

    assert pr24 is not None and pr24.cap_amount == Decimal("1200000")

    assert pr25 is not None and pr25.cap_amount == Decimal("1800000")

    assert ya24.relief_for_concept("qualifying_payment_cap") is None

    assert ya25.relief_for_concept("qualifying_payment_cap") is None





def test_dual_ya_same_qp_inputs_different_tax_from_personal_relief() -> None:

    """Same employment+QP; different YA personal relief → different tax."""

    clear_provenance_cache()

    shared = {

        "resident_status": "resident",

        "employment_income": "3000000",

        "qualifying_payments": "1500000",

        "param_set": "current",

    }

    kg = default_file_kg()

    t24 = calculate(

        CalculateTaxRequestV1.model_validate({**shared, "assessment_year": "2024_25"}),

        kg=kg,

    )

    t25 = calculate(

        CalculateTaxRequestV1.model_validate({**shared, "assessment_year": "2025_26"}),

        kg=kg,

    )

    assert t24.final_tax_lkr == "18000"

    assert t25.final_tax_lkr == "0"

    step_ids = {s.step_id for s in t24.calculation_trace}

    assert "cap_qualifying_payment_cap" not in step_ids

    ded = next(s for s in t24.calculation_trace if s.step_id == "deduct_qualifying_payment")

    assert ded.inputs.get("allowed") == "1500000"





def test_ex10_sec52_4_cf_from_eligible_undeducted_only() -> None:

    clear_provenance_cache()

    result = calculate(

        CalculateTaxRequestV1(

            assessment_year="2025_26",

            resident_status="resident",

            employment_income="1500000",

            filing_lines=[

                FilingLineV1(component_id="qp_government_sri_lanka", amount="2000000"),

            ],

        ),

        kg=default_file_kg(),

    )

    assert result.final_tax_lkr == "0"

    assert result.qualifying_payment_carry_forward_out == "500000"

    assert result.qualifying_payment_summary is not None

    assert result.qualifying_payment_summary.carry_forward_out == "500000"

    assert result.qualifying_payment_summary.section_52_cap is None

    assert result.qualifying_payment_summary.unused_after_sec52 is None

    gov = next(

        c

        for c in result.qualifying_payment_categories

        if c.component_id == "qp_government_sri_lanka"

    )

    assert gov.deducted_this_year == "1500000"

    assert gov.undeducted_amount == "500000"

    assert gov.sec52_4_eligible is True

    assert gov.carry_forward_amount == "500000"

    out = next(

        s for s in result.calculation_trace if s.step_id == "carry_forward_qualifying_payment_out"

    )

    assert "bootstrap:sec52_carry_forward_2025_26" in out.rule_source_ids

    assert out.inputs.get("assessment_year") == "2025_26"





def test_sec52_4_cf_excludes_samurdhi_undeducted() -> None:

    """Gov undeducted CF when income room exhausted; Samurdhi undeducted is not Sec 52(4) eligible."""

    clear_provenance_cache()

    result = calculate(

        CalculateTaxRequestV1(

            assessment_year="2025_26",

            resident_status="resident",

            employment_income="5000000",

            filing_lines=[

                FilingLineV1(component_id="qp_government_sri_lanka", amount="2000000"),

                FilingLineV1(component_id="qp_samurdhi_shop", amount="500000"),

            ],

        ),

        kg=default_file_kg(),

    )

    by_id = {c.component_id: c for c in result.qualifying_payment_categories}

    assert by_id["qp_government_sri_lanka"].sec52_4_eligible is True

    assert by_id["qp_samurdhi_shop"].sec52_4_eligible is False

    assert by_id["qp_samurdhi_shop"].carry_forward_amount == "0"

    cf = Decimal(result.qualifying_payment_carry_forward_out or "0")

    assert cf == Decimal("0")

    ded = next(s for s in result.calculation_trace if s.step_id == "deduct_qualifying_payment")

    assert ded.inputs.get("allowed") == "2500000"





def test_brought_forward_ignored_without_provenance_on_2024_25() -> None:

    """Carry-forward bootstrap is YA 2025/26 only — prior YA ignores brought_forward."""

    clear_provenance_cache()

    result = calculate(

        CalculateTaxRequestV1.model_validate(

            {

                "assessment_year": "2024_25",

                "resident_status": "resident",

                "employment_income": "3000000",

                "qualifying_payments": "500000",

                "qualifying_payment_brought_forward": "800000",

            }

        ),

        kg=default_file_kg(),

    )

    step_ids = [s.step_id for s in result.calculation_trace]

    assert "apply_qualifying_payment_brought_forward" not in step_ids

    ded = next(s for s in result.calculation_trace if s.step_id == "deduct_qualifying_payment")

    assert ded.inputs["allowed"] == "500000"

    assert result.qualifying_payment_carry_forward_out is None

