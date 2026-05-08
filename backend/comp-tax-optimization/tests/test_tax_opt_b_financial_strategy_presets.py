"""Strategy preset builders — caps aligned with ``evaluate_compliance``."""

from __future__ import annotations

from decimal import Decimal

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import (
    build_preset_financial_inputs,
    charitable_donation_cap_lkr,
    retirement_contribution_cap_lkr,
)
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import map_financial_inputs_to_profile_and_strategy
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import (
    TaxOptBDeductionLineV1,
    TaxOptBFinancialInputsV1,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1


def _pack():
    return load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)


def test_charitable_cap_helper_matches_compliance_applied_cap() -> None:
    pack = _pack()
    profile = TaxOptBProfileV1(
        tax_year=pack.assessment_year,
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1500000"),
    )
    cap = charitable_donation_cap_lkr(profile, pack)
    assert cap > 0
    strat = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(relief_code="charitable_donations", claimed_amount_annual=cap),
        ],
    )
    out = evaluate_compliance(profile, strat, pack)
    assert out.passed
    assert Decimal(out.applied_relief["charitable_donations"]["cap"]) == cap


def test_retirement_cap_helper_matches_compliance_applied_cap() -> None:
    pack = _pack()
    profile = TaxOptBProfileV1(
        tax_year=pack.assessment_year,
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=None,
    )
    cap = retirement_contribution_cap_lkr(profile, pack)
    assert cap > 0
    strat = TaxOptBStrategyProposalV1(
        claims=[
            TaxOptBReliefClaimV1(relief_code="retirement_contribution", claimed_amount_annual=cap),
        ],
    )
    out = evaluate_compliance(profile, strat, pack)
    assert out.passed
    assert Decimal(out.applied_relief["retirement_contribution"]["cap"]) == cap


def test_no_claims_preset_maps_to_empty_strategy() -> None:
    pack = _pack()
    base = TaxOptBFinancialInputsV1(
        tax_year=pack.assessment_year,
        annual_salary_income=Decimal("1000000"),
        deductions=[
            TaxOptBDeductionLineV1(relief_code="life_insurance_premium", amount_annual=Decimal("50000")),
        ],
    )
    fin = build_preset_financial_inputs(base, "no_claims", pack)
    _p, strat = map_financial_inputs_to_profile_and_strategy(fin)
    assert strat.claims == []


def test_max_caps_mvp_matches_engine_caps_golden_profiles() -> None:
    """Preset deduction lines are exactly at statutory caps accepted by ``evaluate_compliance``."""
    pack = _pack()
    assert pack.assessment_year == "2024_25"
    goldens: list[dict[str, Decimal]] = [
        {
            "annual_salary_income": Decimal("1800000"),
            "annual_business_income": Decimal("0"),
            "annual_other_income": Decimal("0"),
        },
        {
            "annual_salary_income": Decimal("900000"),
            "annual_business_income": Decimal("700000"),
            "annual_other_income": Decimal("0"),
        },
        {
            "annual_salary_income": Decimal("5000000"),
            "annual_business_income": Decimal("0"),
            "annual_other_income": Decimal("0"),
        },
    ]
    for g in goldens:
        base = TaxOptBFinancialInputsV1(tax_year=pack.assessment_year, **g)
        fin = build_preset_financial_inputs(base, "max_caps_mvp", pack)
        profile, strategy = map_financial_inputs_to_profile_and_strategy(fin)
        res = evaluate_compliance(profile, strategy, pack)
        assert res.passed, res.violations
        assert strategy.claims, "max_caps_mvp should propose at least one relief for MVP pack"
        for c in strategy.claims:
            row = res.applied_relief[c.relief_code]
            cap = Decimal(str(row["cap"]))
            allowed = Decimal(str(row["allowed"]))
            assert cap == c.claimed_amount_annual == allowed
