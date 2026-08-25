"""Fifth Schedule paragraph 2 reliefs — solar 2(g) and rent 2(c)."""

from __future__ import annotations

from decimal import Decimal

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.filing_catalog import get_filing_catalog_for_year
from adaptive_tax_app.services.param_store import load_tax_param_pack
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def _calc(**kwargs: object):
    return calculate(
        CalculateTaxRequestV1.model_validate(kwargs),
        kg=default_file_kg(),
    )


def _step_map(result):
    return {s.step_id: s for s in result.calculation_trace}


def test_statutory_card_has_solar_and_rent_not_on_qp() -> None:
    for year in ("2024_25", "2025_26"):
        catalog = get_filing_catalog_for_year(year)  # type: ignore[arg-type]
        card_ids = {c.card_id for c in catalog.cards}
        assert "statutory_reliefs" in card_ids
        statutory = next(c for c in catalog.cards if c.card_id == "statutory_reliefs")
        ids = {f.component_id for f in statutory.fields}
        assert ids == {
            "relief_solar_panel",
            "relief_rent",
            "relief_senior_citizen_interest",
        }
        qp = next(c for c in catalog.cards if c.card_id == "qualifying_payments")
        qp_ids = {f.component_id for f in qp.fields}
        assert not any("solar" in i for i in qp_ids)
        assert not any("rent" in i and i.startswith("relief_") for i in qp_ids)
        assert "relief_fifth_sch_2f_expenditure" not in ids
        assert "relief_fifth_sch_2f_expenditure" not in qp_ids


def test_solar_cap_600k_both_years() -> None:
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert ya24.relief_for_concept("solar_panel_relief").cap_amount == Decimal("600000")
    assert ya25.relief_for_concept("solar_panel_relief").cap_amount == Decimal("600000")


def test_solar_900k_capped_both_yas() -> None:
    clear_provenance_cache()
    r24 = _calc(
        assessment_year="2024_25",
        employment_income="3000000",
        solar_panel_relief="900000",
        resident_status="resident",
    )
    assert _step_map(r24)["cap_solar_panel_relief"].inputs["allowed"] == "600000"
    # 3M − 600k − 1.2M PR = 1.2M → 30k+60k+36k = 126,000
    assert r24.final_tax_lkr == "126000"

    r25 = _calc(
        assessment_year="2025_26",
        employment_income="3000000",
        solar_panel_relief="900000",
        resident_status="resident",
    )
    assert _step_map(r25)["cap_solar_panel_relief"].inputs["allowed"] == "600000"
    # 3M − 600k − 1.8M PR = 600k @ 6% = 36,000
    assert r25.final_tax_lkr == "36000"


def test_solar_non_resident_zero() -> None:
    result = _calc(
        employment_income="3000000",
        solar_panel_relief="900000",
        resident_status="non_resident",
    )
    assert _step_map(result)["cap_solar_panel_relief"].inputs["allowed"] == "0"
    assert result.final_tax_lkr == "630000"


def test_rent_cap_is_25pct_of_included_inv_rents() -> None:
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
    assert steps["cap_rent_relief"].inputs["inv_rents"] == "1000000"
    assert steps["cap_rent_relief"].inputs["ceiling"] == "250000"
    assert steps["cap_rent_relief"].inputs["allowed"] == "250000"
    assert steps["cap_rent_relief"].inputs["allowed"] != "200000"
    assert result.final_tax_lkr == "153000"


def test_order_qp_then_solar_then_rent_then_senior_then_personal() -> None:
    result = _calc(
        employment_income="4000000",
        resident_status="resident",
        filing_lines=[
            {"component_id": "qp_approved_charitable", "amount": "75000"},
            {"component_id": "inv_rents", "amount": "400000"},
            {"component_id": "inv_interest", "amount": "800000"},
            {"component_id": "relief_solar_panel", "amount": "400000"},
            {"component_id": "relief_rent", "amount": "100000"},
            {"component_id": "relief_senior_citizen_interest", "amount": "800000"},
        ],
    )
    rules = result.rules_applied
    assert rules.index("deduct_qualifying_payment") < rules.index(
        "deduct_solar_panel_relief"
    )
    assert rules.index("deduct_solar_panel_relief") < rules.index("deduct_rent_relief")
    assert rules.index("deduct_rent_relief") < rules.index(
        "deduct_senior_citizen_interest_relief"
    )
    assert rules.index("deduct_senior_citizen_interest_relief") < rules.index(
        "apply_personal_relief"
    )


def test_senior_cap_min_claim_15m_inv_interest() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="3000000",
        filing_lines=[
            {"component_id": "inv_interest", "amount": "900000"},
            {"component_id": "relief_senior_citizen_interest", "amount": "2000000"},
        ],
    )
    steps = _step_map(result)
    assert steps["cap_senior_citizen_interest_relief"].inputs["inv_interest"] == "900000"
    assert steps["cap_senior_citizen_interest_relief"].inputs["cap"] == "1500000"
    assert steps["cap_senior_citizen_interest_relief"].inputs["allowed"] == "900000"
    # Gross 3.9M − 900k senior − 1.2M PR = 1.8M → 30k+60k+90k+72k = 252000
    assert result.final_tax_lkr == "252000"


def test_senior_non_resident_zero() -> None:
    clear_provenance_cache()
    result = _calc(
        assessment_year="2024_25",
        resident_status="non_resident",
        employment_income="3000000",
        filing_lines=[
            {"component_id": "inv_interest", "amount": "900000"},
            {"component_id": "relief_senior_citizen_interest", "amount": "900000"},
        ],
    )
    assert (
        _step_map(result)["cap_senior_citizen_interest_relief"].inputs["allowed"] == "0"
    )


def test_each_relief_floors_running_at_zero() -> None:
    result = _calc(
        assessment_year="2024_25",
        resident_status="resident",
        employment_income="400000",
        solar_panel_relief="600000",
        filing_lines=[{"component_id": "relief_rent", "amount": "100000"}],
    )
    steps = _step_map(result)
    assert steps["deduct_solar_panel_relief"].inputs["allowed"] == "400000"
    assert steps["deduct_solar_panel_relief"].output == "0"
    assert steps["deduct_rent_relief"].inputs["allowed"] == "0"
    assert steps["deduct_rent_relief"].output == "0"
    assert steps["apply_personal_relief"].output == "0"
    assert result.final_tax_lkr == "0"


def test_year_packs_pr_slabs_unchanged_except_new_relief_rows() -> None:
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert ya24.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")
    assert ya25.relief_for_concept("personal_relief").cap_amount == Decimal("1800000")
    assert len(ya24.rate_bands) == 6
    assert ya24.rate_bands[1].rate == Decimal("0.12")
    assert len(ya25.rate_bands) == 5
    assert ya25.rate_bands[0].upper == 1_000_000
    assert ya25.rate_bands[0].rate == Decimal("0.06")
    for pack in (ya24, ya25):
        solar = pack.relief_for_concept("solar_panel_relief")
        rent = pack.relief_for_concept("rent_relief")
        assert solar is not None and solar.cap_amount == Decimal("600000")
        assert rent is not None
        assert rent.cap_pct_of_assessable is None
        assert rent.cap_amount is None
