"""Phase 5.3 — personal relief (resident-only, dual YA)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import RuleType
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.param_store import (
    clear_param_store_cache,
    is_personal_relief_rule,
    load_tax_param_pack,
    read_param_override,
    reset_param_override,
    write_personal_relief_override_from_rules,
)
from adaptive_tax_app.services.provenance import clear_provenance_cache
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg


def test_personal_relief_packs_versioned_by_ya() -> None:
    clear_param_store_cache()
    clear_provenance_cache()
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    pr24 = ya24.relief_for_concept("personal_relief")
    pr25 = ya25.relief_for_concept("personal_relief")
    assert pr24 is not None and pr24.cap_amount == Decimal("1200000")
    assert pr25 is not None and pr25.cap_amount == Decimal("1800000")
    assert pr24.rule_source_id == "bootstrap:personal_relief_2024_25"
    assert pr25.rule_source_id == "bootstrap:personal_relief_2025_26"


def test_non_resident_personal_relief_zero_with_provenance_on_step() -> None:
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="non_resident",
            employment_income=Decimal("1800000"),
        ),
        kg=default_file_kg(),
    )
    step = next(s for s in result.calculation_trace if s.step_id == "apply_personal_relief")
    assert step.inputs["personal_relief"] == "0"
    assert step.inputs["resident_status"] == "non_resident"
    assert step.output == "1800000"
    assert step.rule_source_ids
    assert any(
        ref.id.startswith("bootstrap:personal_relief") for ref in result.rule_source_refs
    )


def test_ex05_ex06_personal_relief_step_act_backed() -> None:
    clear_provenance_cache()
    kg = default_file_kg()
    for case in (
        {"employment_income": "1800000"},
        {"employment_income": "4000000", "qualifying_payments": "500000"},
    ):
        result = calculate(
            CalculateTaxRequestV1.model_validate(
                {
                    "assessment_year": "2024_25",
                    "resident_status": "resident",
                    **case,
                }
            ),
            kg=kg,
        )
        step = next(s for s in result.calculation_trace if s.step_id == "apply_personal_relief")
        assert step.inputs["personal_relief"] == "1200000"
        assert "bootstrap:personal_relief_2024_25" in step.rule_source_ids
        assert any("first_schedule" in u for u in step.section_uids)


def test_ya_2025_26_salary_1800000_zero_tax_with_18m_relief() -> None:
    """Calculator screenshot case: full personal relief absorbs employment income."""
    clear_provenance_cache()
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2025_26",
            resident_status="resident",
            employment_income=Decimal("1800000"),
        ),
        kg=default_file_kg(),
    )
    assert result.final_tax_lkr == "0"
    step = next(s for s in result.calculation_trace if s.step_id == "apply_personal_relief")
    assert step.inputs["personal_relief"] == "1800000"
    assert step.output == "0"


def test_is_personal_relief_rule() -> None:
    assert is_personal_relief_rule(
        rule_type="limit",
        concept_id="personal_relief",
        section="First Schedule",
        amends_section=None,
        engine_handler="personal_relief_resident",
        maximum=1_800_000,
    )
    assert not is_personal_relief_rule(
        rule_type="limit",
        concept_id="qualifying_payment_cap",
        section="52",
        amends_section="52",
        maximum=1_800_000,
    )


def test_write_personal_relief_override_stamps_ya_scoped_cap() -> None:
    settings = get_adaptive_tax_settings()
    reset_param_override(settings=settings)
    clear_param_store_cache()
    rule_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        rule_type=RuleType.LIMIT,
        concept_id="personal_relief",
        section="First Schedule",
        amends_section=None,
        engine_handler="personal_relief_resident",
        schedule_ref="First Schedule",
        assessment_years=["2025_26"],
        maximum=1_800_000,
        amendment_job_id=uuid.uuid4(),
    )
    result = write_personal_relief_override_from_rules([rule], settings=settings)
    assert result is not None
    assert result.cap_amount == Decimal("1800000")
    doc = read_param_override(settings=settings)
    assert doc is not None
    pr_row = next(r for r in doc["relief_updates"] if r["concept_id"] == "personal_relief")
    assert pr_row["assessment_year"] == "2025_26"
    assert pr_row["rule_source_id"] == str(rule_id)
    pack25 = load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    )
    pack24 = load_tax_param_pack(
        assessment_year="2024_25", param_set="current", settings=settings
    )
    assert pack25.relief_for_concept("personal_relief").cap_amount == Decimal("1800000")
    assert pack24.relief_for_concept("personal_relief").cap_amount == Decimal("1200000")
    reset_param_override(settings=settings)
    clear_param_store_cache()
