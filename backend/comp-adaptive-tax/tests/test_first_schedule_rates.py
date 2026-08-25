"""Phase 5.2 — First Schedule rate packs + rate approve writer."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import RuleType
from adaptive_tax_app.services.param_store import (
    clear_param_store_cache,
    is_rate_band_rule,
    load_tax_param_pack,
    read_param_override,
    reset_param_override,
    write_rate_band_override_from_rules,
)
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1


def test_is_rate_band_rule_matches_rate_type_and_schedule() -> None:
    assert is_rate_band_rule(
        rule_type="rate",
        concept_id="first_schedule_rates",
        section="First Schedule",
        amends_section=None,
        engine_handler="slab_band",
    )
    assert not is_rate_band_rule(
        rule_type="limit",
        concept_id="qualifying_payment_cap",
        section="52",
        amends_section="52",
    )


def test_ya_packs_are_act_verified_and_differ() -> None:
    clear_param_store_cache()
    ya24 = load_tax_param_pack(assessment_year="2024_25", param_set="current")
    ya25 = load_tax_param_pack(assessment_year="2025_26", param_set="current")
    assert len(ya24.rate_bands) == 6
    assert ya24.rate_bands[1].rate == Decimal("0.12")
    assert len(ya25.rate_bands) == 5
    assert ya25.rate_bands[0].upper == 1_000_000
    assert ya25.rate_bands[1].rate == Decimal("0.18")
    assert ya24.rate_bands[0].rule_source_id == "bootstrap:first_schedule_rates_2024_25"
    assert ya25.rate_bands[0].rule_source_id == "bootstrap:first_schedule_rates_2025_26"


def test_write_rate_band_override_stamps_rule_source_id() -> None:
    settings = get_adaptive_tax_settings()
    reset_param_override(settings=settings)
    clear_param_store_cache()
    rule_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        rule_type=RuleType.RATE,
        concept_id="first_schedule_rates",
        section="First Schedule",
        amends_section=None,
        engine_handler="slab_band",
        schedule_ref="First Schedule",
        assessment_years=["2025_26"],
        amendment_job_id=uuid.uuid4(),
        paragraph=None,
        maximum=None,
        formula=None,
        threshold=None,
    )
    result = write_rate_band_override_from_rules([rule], settings=settings)
    assert result is not None
    assert result.band_update_count == 5
    doc = read_param_override(settings=settings)
    assert doc is not None
    assert doc["source"] == "rate_approve"
    assert all(
        u["rule_source_id"] == str(rule_id)
        for u in doc["rate_band_updates"]
        if u["assessment_year"] == "2025_26"
    )
    pack = load_tax_param_pack(
        assessment_year="2025_26", param_set="current", settings=settings
    )
    assert pack.rate_bands[0].rule_source_id == str(rule_id)
    reset_param_override(settings=settings)
    clear_param_store_cache()


def test_ex09_band_edges_dual_ya() -> None:
    kg = default_file_kg()
    top24 = calculate(
        CalculateTaxRequestV1.model_validate(
            {
                "assessment_year": "2024_25",
                "employment_income": "1700000",
                "resident_status": "resident",
            }
        ),
        kg=kg,
    )
    assert top24.final_tax_lkr == "30000"
    assert "slab_band_2" not in top24.rules_applied

    same_emp_ya25 = calculate(
        CalculateTaxRequestV1.model_validate(
            {
                "assessment_year": "2025_26",
                "employment_income": "2200000",
                "resident_status": "resident",
            }
        ),
        kg=kg,
    )
    # YA 2025/26: 2.2M − 1.8M personal relief = 400k taxable → 6% band only = 24000
    assert same_emp_ya25.final_tax_lkr == "24000"
    assert same_emp_ya25.rules_applied.count("slab_band_1") == 1
    assert "slab_band_2" not in same_emp_ya25.rules_applied
