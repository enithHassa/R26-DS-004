"""Rules scoping: assessment year + IRD-style personal relief schedule."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_rules_scope import (
    personal_relief_lkr_for_assessment_year,
    rules_pack_for_tax_year,
    supported_assessment_years,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1


def test_supported_years_start_2018_19() -> None:
    assert "2017_18" not in supported_assessment_years()
    assert "2018_19" in supported_assessment_years()
    assert "2025_26" in supported_assessment_years()


def test_personal_relief_schedule_matches_ird_bands() -> None:
    assert personal_relief_lkr_for_assessment_year("2018_19") == Decimal("500000")
    assert personal_relief_lkr_for_assessment_year("2019_20") == Decimal("500000")
    assert personal_relief_lkr_for_assessment_year("2020_21") == Decimal("3000000")
    assert personal_relief_lkr_for_assessment_year("2022_23") == Decimal("3000000")
    assert personal_relief_lkr_for_assessment_year("2023_24") == Decimal("1200000")
    assert personal_relief_lkr_for_assessment_year("2024_25") == Decimal("1200000")
    assert personal_relief_lkr_for_assessment_year("2025_26") == Decimal("1800000")


def test_rules_pack_rebases_year_and_relief() -> None:
    base = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    p = rules_pack_for_tax_year(base, "2023_24")
    assert p.assessment_year == "2023_24"
    assert p.thresholds.personal_relief_annual == Decimal("1200000")
    assert p is not base


def test_rules_pack_identity_for_canonical_file_year() -> None:
    base = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    assert base.assessment_year == "2024_25"
    p = rules_pack_for_tax_year(base, "2024_25")
    assert p.thresholds.personal_relief_annual == base.thresholds.personal_relief_annual
    assert p is base


def test_invalid_year_code_raises() -> None:
    with pytest.raises(ValueError, match="Invalid"):
        personal_relief_lkr_for_assessment_year("nope")


def test_evaluate_compliance_rebases_yaml_pack_when_profile_year_differs() -> None:
    """Callers may pass the file-default pack (2024_25) while profile uses another supported YA."""
    base = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    assert base.assessment_year == "2024_25"
    profile = TaxOptBProfileV1(
        tax_year="2023_24",
        employment_type="employee",
        dependents=0,
        annual_gross_income=Decimal("2400000"),
    )
    strategy = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(
                relief_code="life_insurance_premium",
                claimed_amount_annual=Decimal("50000"),
            ),
        ],
    )
    result = evaluate_compliance(profile, strategy, base)
    assert result.passed is True
    assert not any(v.rule_id == "it22064486_optb_year_001" for v in result.violations)
