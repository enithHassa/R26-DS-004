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
    """Same gross aggregation as ``map_financial_inputs_to_profile_and_strategy`` (Option A)."""
    gross = fin.annual_salary_income + fin.annual_business_income + fin.annual_investment_income + fin.annual_other_income
    return TaxOptBProfileV1(
        tax_year=fin.tax_year,
        employment_type=fin.employment_type,
        dependents=fin.dependents,
        annual_gross_income=gross,
        estimated_annual_taxable_income=None,
    )


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
    "build_financial_inputs_presets_dict",
    "build_preset_financial_inputs",
    "charitable_donation_cap_lkr",
    "max_caps_mvp_deduction_lines",
    "preset_order_labels",
    "profile_from_financial_inputs",
    "relief_max_claim_amounts_by_code",
    "retirement_contribution_cap_lkr",
]
