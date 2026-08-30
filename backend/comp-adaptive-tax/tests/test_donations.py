"""Fifth Schedule 1(a) charitable donations — 75k / one-third of assessable."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import RuleType
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.param_store import (
    clear_param_store_cache,
    is_donation_cap_rule,
    load_tax_param_pack,
    reset_param_override,
    write_donation_cap_override_from_rules,
)
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def test_donation_cap_packs_are_1a_alias() -> None:
    clear_param_store_cache()
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    d24 = ya24.relief_for_concept("donation_cap")
    d25 = ya25.relief_for_concept("donation_cap")
    assert d24 is not None and d24.cap_amount == Decimal("75000")
    assert d25 is not None and d25.cap_amount == Decimal("75000")
    assert d24.rule_source_id == "bootstrap:donation_cap_2024_25"
    assert d25.rule_source_id == "bootstrap:donation_cap_2025_26"


def test_ex03_donation_cap_on_assessable() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("3000000"),
            donations=Decimal("2000000"),
        ),
        kg=default_file_kg(),
    )
    # 2M claimed on 3M assessable → min(2M, 75k, floor(3M/3)=1M) = 75,000
    # taxable 3M − 75k − 1.2M PR = 1,725,000 → tax 234,000
    assert result.final_tax_lkr == "234000"
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.allowable == "75000"
    assert cat.claimed == "2000000"
    assert "75000" in cat.formula
    assert "floor(assessable/3)" in cat.formula
    qp = next(s for s in result.calculation_trace if s.step_id == "deduct_qualifying_payment")
    assert qp.inputs["allowed"] == "75000"
    assert "cap_donation_cap" not in result.rules_applied
    assert "deduct_donation" not in result.rules_applied


def test_ex11_claimed_above_1a_ceiling_capped() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("2000000"),
            donations=Decimal("900000"),
        ),
        kg=default_file_kg(),
    )
    # taxable 2M − 75k − 1.2M = 725,000 → 30k@6% + 27k@12% = 57,000
    assert result.final_tax_lkr == "57000"
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.claimed == "900000"
    assert cat.allowable == "75000"


def test_is_donation_cap_rule() -> None:
    assert is_donation_cap_rule(
        rule_type="limit",
        concept_id="donation_cap",
        section="52",
        amends_section=None,
        engine_handler="cap_percent_assessable",
        threshold=0.33,
    )
    assert not is_donation_cap_rule(
        rule_type="limit",
        concept_id="qualifying_payment_cap",
        section="52",
        amends_section=None,
        threshold=0.33,
    )


def test_write_donation_cap_override_stamps_pct() -> None:
    settings = get_adaptive_tax_settings()
    reset_param_override(settings=settings)
    clear_param_store_cache()
    rule_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        rule_type=RuleType.LIMIT,
        concept_id="donation_cap",
        section="52",
        amends_section=None,
        engine_handler="cap_percent_assessable",
        threshold=0.33,
        assessment_years=["2024_25"],
        amendment_job_id=uuid.uuid4(),
    )
    result = write_donation_cap_override_from_rules([rule], settings=settings)
    assert result is not None
    assert result.cap_amount == Decimal("0.33")
    pack = load_tax_param_pack(
        assessment_year="2024_25", param_set="current", settings=settings
    )
    assert pack.relief_for_concept("donation_cap").rule_source_id == str(rule_id)
    reset_param_override(settings=settings)
    clear_param_store_cache()


def test_scalar_and_legacy_don_line_do_not_double_count() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("3000000"),
            donations=Decimal("2000000"),
            filing_lines=[
                {"component_id": "don_approved_charitable", "amount": Decimal("2000000")}
            ],
        ),
        kg=default_file_kg(),
    )
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.claimed == "2000000"
    assert cat.allowable == "75000"
    assert "deduct_donation" not in result.rules_applied
    assert "cap_donation_cap" not in result.rules_applied
    assert result.final_tax_lkr == "234000"


def test_1a_one_third_binds_when_below_75k() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("180000"),
            donations=Decimal("200000"),
        ),
        kg=default_file_kg(),
    )
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    # min(200k, 75k, floor(180000/3)=60000) = 60,000 — not 33% (59400)
    assert cat.allowable == "60000"
    assert "deduct_donation" not in result.rules_applied


def test_donation_cap_override_does_not_create_live_33pct_deduct() -> None:
    settings = get_adaptive_tax_settings()
    reset_param_override(settings=settings)
    clear_param_store_cache()
    clear_provenance_cache()
    rule_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        rule_type=RuleType.LIMIT,
        concept_id="donation_cap",
        section="52",
        amends_section=None,
        engine_handler="cap_percent_assessable",
        threshold=0.33,
        assessment_years=["2024_25"],
        amendment_job_id=uuid.uuid4(),
    )
    write_donation_cap_override_from_rules([rule], settings=settings)
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("3000000"),
            donations=Decimal("2000000"),
        ),
        kg=default_file_kg(),
        settings=settings,
    )
    cat = next(
        c
        for c in result.qualifying_payment_categories
        if c.component_id == "qp_approved_charitable"
    )
    assert cat.allowable == "75000"
    assert "deduct_donation" not in result.rules_applied
    assert result.final_tax_lkr == "234000"
    reset_param_override(settings=settings)
    clear_param_store_cache()
