"""Deterministic strategy presets over structured financial intake (research / MVP demo).

Maps ``TaxOptBFinancialInputsV1`` variants that share the same gross profile and
feeds them through ``map_financial_inputs_to_profile_and_strategy`` +
``compare_strategies`` without ML.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import (
    TaxOptBDeductionLineV1,
    TaxOptBFinancialInputsV1,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1

FinancialStrategyPresetIdV1 = Literal["user_proposed", "no_claims", "max_caps_mvp"]

PRESET_LABELS: dict[FinancialStrategyPresetIdV1, str] = {
    "user_proposed": "User proposed (form)",
    "no_claims": "No statutory claims",
    "max_caps_mvp": "MVP maximum caps (rules YAML)",
}

PRESET_SUMMARY_NARRATIVES: dict[str, str] = {
    "user_proposed": "Uses deductions and investments from the form as submitted.",
    "no_claims": "Clears all deduction rows and investments so no statutory reliefs are claimed.",
    "max_caps_mvp": (
        "Claims each relief in the active rules pack at its MVP maximum "
        "(YAML thresholds; charitable % uses the same gross/taxable basis as compliance)."
    ),
}


def profile_from_financial_inputs(fin: TaxOptBFinancialInputsV1) -> TaxOptBProfileV1:
    """Gross aggregation with investment income breakdown.

    Rental income: 25% deemed repair deduction applied automatically per IRA Section 16B.
    Investment income = rental (net of deduction) + interest + other investment income.
    """
    rental_net, _ = apply_rental_deduction(fin.annual_rental_income)

    # Handle backward compatibility: if annual_investment_income is set, use it as other_investment
    other_investment = fin.annual_other_investment_income
    if fin.annual_investment_income is not None and fin.annual_investment_income > 0:
        other_investment = fin.annual_investment_income

    gross = (
        fin.annual_salary_income
        + fin.annual_business_income
        + rental_net
        + fin.annual_interest_income
        + other_investment
        + fin.annual_other_income
    )

    return TaxOptBProfileV1(
        tax_year=fin.tax_year,
        employment_type=fin.employment_type,
        dependents=fin.dependents,
        annual_gross_income=gross,
        estimated_annual_taxable_income=None,
    )


def apply_rental_deduction(rental_income: Decimal) -> tuple[Decimal, Decimal]:
    """Apply 25% deemed repair allowance to rental income.

    Returns (net_rental_income, deduction_amount).
    Deduction = 25% of gross rental income (automatically applied under IRA Section 16B).
    """
    deduction_pct = Decimal("0.25")
    deduction = (rental_income * deduction_pct).quantize(Decimal("1"))
    net = rental_income - deduction
    return net, deduction


def charitable_donation_cap_lkr(profile: TaxOptBProfileV1, pack: TaxOptBRulePack) -> Decimal:
    """Mirror ``evaluate_compliance`` charitable_donation_cap (research alignment)."""
    deductions = pack.thresholds.deductions
    for rule in pack.rules:
        if rule.rule_type != "charitable_donation_cap":
            continue
        pct_field = rule.cap_pct_field
        pct = deductions.get(pct_field, Decimal("0")) if pct_field else Decimal("0")
        basis = profile.estimated_annual_taxable_income
        if basis is None:
            basis = profile.annual_gross_income
        return (basis * pct).quantize(Decimal("1"))
    return Decimal("0")


def retirement_contribution_cap_lkr(profile: TaxOptBProfileV1, pack: TaxOptBRulePack) -> Decimal:
    """Mirror ``evaluate_compliance`` retirement_contribution_cap."""
    deductions = pack.thresholds.deductions
    for rule in pack.rules:
        if rule.rule_type != "retirement_contribution_cap":
            continue
        pct_field = rule.cap_pct_field
        ann_field = rule.cap_annual_field
        pct_g = deductions.get(pct_field, Decimal("0")) if pct_field else Decimal("0")
        cap_ann = deductions.get(ann_field, Decimal("0")) if ann_field else Decimal("0")
        return min(profile.annual_gross_income * pct_g, cap_ann).quantize(Decimal("1"))
    return Decimal("0")


def max_caps_mvp_deduction_lines(profile: TaxOptBProfileV1, pack: TaxOptBRulePack) -> list[TaxOptBDeductionLineV1]:
    """Build one deduction row per MVP cap rule at the statutory maximum (YAML-driven)."""
    deductions_thresh = pack.thresholds.deductions
    lines: list[TaxOptBDeductionLineV1] = []
    seen: set[str] = set()

    for rule in pack.rules:
        rtype = rule.rule_type

        if rtype == "deduction_cap":
            relief = (rule.relief_code or "").strip()
            if not relief or relief in seen:
                continue
            cap_field = rule.cap_field
            if not cap_field:
                continue
            cap = deductions_thresh.get(cap_field)
            if cap is None:
                continue
            lines.append(
                TaxOptBDeductionLineV1(
                    relief_code=relief,
                    amount_annual=cap,
                    description="preset: MVP annual cap",
                ),
            )
            seen.add(relief)

        elif rtype == "charitable_donation_cap":
            relief = (rule.relief_code or "charitable_donations").strip()
            if relief in seen:
                continue
            cap_amt = charitable_donation_cap_lkr(profile, pack)
            if cap_amt <= 0:
                continue
            lines.append(
                TaxOptBDeductionLineV1(
                    relief_code=relief,
                    amount_annual=cap_amt,
                    description="preset: % of taxable basis (same as compliance)",
                ),
            )
            seen.add(relief)

        elif rtype == "retirement_contribution_cap":
            relief = (rule.relief_code or "retirement_contribution").strip()
            if relief in seen:
                continue
            cap_amt = retirement_contribution_cap_lkr(profile, pack)
            if cap_amt <= 0:
                continue
            lines.append(
                TaxOptBDeductionLineV1(
                    relief_code=relief,
                    amount_annual=cap_amt,
                    description="preset: min(% gross, annual ceiling)",
                ),
            )
            seen.add(relief)

    lines.sort(key=lambda d: d.relief_code)
    return lines


def relief_max_claim_amounts_by_code(profile: TaxOptBProfileV1, pack: TaxOptBRulePack) -> dict[str, Decimal]:
    """Statutory MVP max claim per relief (same basis as ``max_caps_mvp`` preset). Used by strategy search grid."""
    return {d.relief_code: d.amount_annual for d in max_caps_mvp_deduction_lines(profile, pack)}


def actual_claimable_amounts_by_code(
    financial_inputs: TaxOptBFinancialInputsV1,
    profile: TaxOptBProfileV1,
    pack: TaxOptBRulePack,
) -> dict[str, Decimal]:
    """Claimable amount per relief code based on what the user *actually spent*, capped at statutory limits.

    Used by the strategy search grid so it only enumerates reliefs the user actually incurred.
    If the user spent LKR 0 on a relief, it is excluded from the grid entirely.
    """
    actual: dict[str, Decimal] = {}
    for d in financial_inputs.deductions:
        code = d.relief_code
        actual[code] = actual.get(code, Decimal("0")) + d.amount_annual

    caps = relief_max_claim_amounts_by_code(profile, pack)

    result: dict[str, Decimal] = {}
    for code, cap in caps.items():
        spent = actual.get(code, Decimal("0"))
        if spent > 0:
            result[code] = min(spent, cap)

    return result


def build_preset_financial_inputs(
    base: TaxOptBFinancialInputsV1,
    preset_id: FinancialStrategyPresetIdV1,
    pack: TaxOptBRulePack,
) -> TaxOptBFinancialInputsV1:
    if preset_id == "user_proposed":
        return base.model_copy(deep=True)

    if preset_id == "no_claims":
        return base.model_copy(
            deep=True,
            update={
                "deductions": [],
                "investments": [],
            },
        )

    if preset_id == "max_caps_mvp":
        profile = profile_from_financial_inputs(base)
        lines = max_caps_mvp_deduction_lines(profile, pack)
        return base.model_copy(
            deep=True,
            update={
                "deductions": lines,
                "investments": [],
                "strategy_notes": base.strategy_notes,
            },
        )

    raise ValueError(f"unknown preset_id: {preset_id!r}")


def build_financial_inputs_presets_dict(
    base: TaxOptBFinancialInputsV1,
    preset_ids: list[FinancialStrategyPresetIdV1],
    pack: TaxOptBRulePack,
) -> dict[str, TaxOptBFinancialInputsV1]:
    out: dict[str, TaxOptBFinancialInputsV1] = {}
    for pid in preset_ids:
        out[pid] = build_preset_financial_inputs(base, pid, pack)
    return out


def preset_order_labels(preset_ids: list[FinancialStrategyPresetIdV1]) -> list[tuple[str, str]]:
    return [(pid, PRESET_LABELS[pid]) for pid in preset_ids]


__all__ = [
    "FinancialStrategyPresetIdV1",
    "PRESET_LABELS",
    "PRESET_SUMMARY_NARRATIVES",
    "actual_claimable_amounts_by_code",
    "build_financial_inputs_presets_dict",
    "build_preset_financial_inputs",
    "charitable_donation_cap_lkr",
    "max_caps_mvp_deduction_lines",
    "preset_order_labels",
    "profile_from_financial_inputs",
    "relief_max_claim_amounts_by_code",
    "retirement_contribution_cap_lkr",
]
