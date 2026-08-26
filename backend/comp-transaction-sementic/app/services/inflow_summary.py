"""Credit-only tri-state rollup. Comp 1 does not apply personal relief or tax rates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.shared.schemas.enums import TxnDirection

from .transaction_analyzer import TransactionAnalysisResult, TransactionAnalyzeInput

# Inland Revenue (Amendment) Act No. 2 of 2025 personal relief — consumed by Comp 2/5 only.
PERSONAL_RELIEF_ANNUAL_LKR = Decimal("1800000.00")
PERSONAL_RELIEF_MONTHLY_EQUIVALENT_LKR = Decimal("150000.00")


@dataclass(frozen=True)
class InflowSummary:
    guaranteed_taxable_inflows_lkr: Decimal
    guaranteed_non_taxable_inflows_lkr: Decimal
    indeterminate_inflows_lkr: Decimal
    outflow_lkr: Decimal
    credit_count: int
    debit_count: int
    indeterminate_credit_count: int
    potential_assessable_if_indet_is_income_lkr: Decimal
    exceeds_annual_personal_relief_if_indet_is_income: bool
    exceeds_monthly_relief_equivalent_if_indet_is_income: bool
    relief_hint: str


def summarize_inflows(
    items: list[TransactionAnalyzeInput],
    analyses: list[TransactionAnalysisResult],
) -> InflowSummary:
    taxable = Decimal("0.00")
    non_taxable = Decimal("0.00")
    indeterminate = Decimal("0.00")
    outflow = Decimal("0.00")
    credits = 0
    debits = 0
    indet_credits = 0

    for item, analysis in zip(items, analyses, strict=True):
        amount = item.amount_lkr
        if item.direction == TxnDirection.DR:
            outflow += amount
            debits += 1
            continue
        credits += 1
        tier = analysis.certainty_tier or "indeterminate"
        if tier == "guaranteed_taxable":
            taxable += analysis.taxable_amount_lkr if analysis.taxable_amount_lkr else amount
        elif tier == "guaranteed_non_taxable":
            non_taxable += amount
        else:
            indeterminate += amount
            indet_credits += 1

    potential = taxable + indeterminate
    exceeds_annual = potential > PERSONAL_RELIEF_ANNUAL_LKR
    exceeds_monthly = potential > PERSONAL_RELIEF_MONTHLY_EQUIVALENT_LKR
    if exceeds_annual:
        hint = (
            "Presumptive assessable inflows (labelled interest plus unproven credits, "
            f"{potential} LKR) exceed the {PERSONAL_RELIEF_ANNUAL_LKR} LKR annual personal relief. "
            "Override a credit to loan/gift/own-transfer to exclude it. Comp 2/5 apply relief and rates."
        )
    elif exceeds_monthly:
        hint = (
            "Presumptive assessable inflows "
            f"({potential} LKR) exceed the {PERSONAL_RELIEF_MONTHLY_EQUIVALENT_LKR} LKR "
            "monthly equivalent of personal relief. Unproven credits are in this total until overridden. "
            "Comp 1 does not compute tax payable."
        )
    else:
        hint = (
            "Unproven credits are included in presumptive assessable income until overridden. "
            "Personal relief (LKR 1.8M/year) is applied by Comp 2/5."
        )

    return InflowSummary(
        guaranteed_taxable_inflows_lkr=taxable,
        guaranteed_non_taxable_inflows_lkr=non_taxable,
        indeterminate_inflows_lkr=indeterminate,
        outflow_lkr=outflow,
        credit_count=credits,
        debit_count=debits,
        indeterminate_credit_count=indet_credits,
        potential_assessable_if_indet_is_income_lkr=potential,
        exceeds_annual_personal_relief_if_indet_is_income=exceeds_annual,
        exceeds_monthly_relief_equivalent_if_indet_is_income=exceeds_monthly,
        relief_hint=hint,
    )
