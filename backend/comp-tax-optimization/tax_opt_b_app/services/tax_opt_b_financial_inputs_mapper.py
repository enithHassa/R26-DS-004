"""Map structured financial inputs to profile + strategy for ``evaluate_compliance``."""

from __future__ import annotations

from collections.abc import Collection
from decimal import Decimal

from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import (
    TaxOptBFinancialInputsV1,
    TaxOptBInvestmentTaxTreatmentV1,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import (
    TaxOptBReliefClaimV1,
    TaxOptBStrategyProposalV1,
)


def _aggregate_claims(fin: TaxOptBFinancialInputsV1) -> dict[str, Decimal]:
    by_code: dict[str, Decimal] = {}
    for row in fin.deductions:
        code = row.relief_code.strip()
        by_code[code] = by_code.get(code, Decimal("0")) + row.amount_annual
    for inv in fin.investments:
        if inv.tax_treatment == TaxOptBInvestmentTaxTreatmentV1.MAP_TO_RELIEF and inv.relief_code:
            code = inv.relief_code.strip()
            by_code[code] = by_code.get(code, Decimal("0")) + inv.amount_annual
    return by_code


def map_financial_inputs_to_profile_and_strategy(
    fin: TaxOptBFinancialInputsV1,
) -> tuple[TaxOptBProfileV1, TaxOptBStrategyProposalV1]:
    gross = fin.annual_salary_income + fin.annual_business_income + fin.annual_investment_income + fin.annual_other_income
    # Gross (salary + business + investment + other) is the income basis for compliance
    # donation % caps and tax slabs; no separate "estimated taxable" on structured intake.
    profile = TaxOptBProfileV1(
        tax_year=fin.tax_year,
        employment_type=fin.employment_type,
        dependents=fin.dependents,
        annual_gross_income=gross,
        estimated_annual_taxable_income=None,
    )
    by_code = _aggregate_claims(fin)
    claims = [
        TaxOptBReliefClaimV1(relief_code=code, claimed_amount_annual=amount)
        for code, amount in sorted(by_code.items(), key=lambda kv: kv[0])
    ]
    strategy = TaxOptBStrategyProposalV1(claims=claims, notes=fin.strategy_notes)
    return profile, strategy


def validate_relief_codes_used(
    fin: TaxOptBFinancialInputsV1,
    allowed: Collection[str],
) -> list[str]:
    """Return unknown relief codes (deduction rows + map_to_relief investments)."""
    allowed_set = frozenset(allowed)
    bad: list[str] = []
    for row in fin.deductions:
        c = row.relief_code.strip()
        if c not in allowed_set:
            bad.append(c)
    for inv in fin.investments:
        if inv.tax_treatment == TaxOptBInvestmentTaxTreatmentV1.MAP_TO_RELIEF and inv.relief_code:
            c = inv.relief_code.strip()
            if c not in allowed_set:
                bad.append(c)
    return sorted(set(bad))


def validate_strategy_relief_codes(
    strategy: TaxOptBStrategyProposalV1,
    allowed: Collection[str],
) -> list[str]:
    """Return unknown relief codes on ``strategy.claims`` (sorted unique)."""
    allowed_set = frozenset(allowed)
    bad: list[str] = []
    for claim in strategy.claims:
        c = claim.relief_code.strip()
        if c not in allowed_set:
            bad.append(c)
    return sorted(set(bad))


__all__ = [
    "map_financial_inputs_to_profile_and_strategy",
    "validate_relief_codes_used",
    "validate_strategy_relief_codes",
]
