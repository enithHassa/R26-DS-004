"""Map catalog strategies to post-adoption deduction profiles."""

from __future__ import annotations

from typing import Any

from rules.engine import TaxRules, apply_deductions, compute_annual_tax

from impact.types import DeductionProfile, SimulationSnapshot


def _deductions_from_context(ctx: dict[str, Any]) -> DeductionProfile:
    return DeductionProfile(
        rent_paid_annual=float(ctx.get("rent_paid_annual_lkr", 0.0) or 0.0),
        life_insurance_premium_annual=float(ctx.get("life_insurance_premium_annual_lkr", 0.0) or 0.0),
        health_insurance_premium_annual=float(ctx.get("health_insurance_premium_annual_lkr", 0.0) or 0.0),
        home_loan_interest_annual=float(ctx.get("home_loan_interest_annual_lkr", 0.0) or 0.0),
        donations_annual=float(ctx.get("donations_annual_lkr", 0.0) or 0.0),
        retirement_contribution_annual=float(ctx.get("retirement_contribution_annual_lkr", 0.0) or 0.0),
    )


def _tax_for_income(
    annual_income: float,
    deductions: DeductionProfile,
    rules: TaxRules,
) -> float:
    taxable = apply_deductions(
        annual_income=annual_income,
        rules=rules,
        rent_paid_annual=deductions.rent_paid_annual,
        life_insurance_premium_annual=deductions.life_insurance_premium_annual,
        health_insurance_premium_annual=deductions.health_insurance_premium_annual,
        home_loan_interest_annual=deductions.home_loan_interest_annual,
        donations_annual=deductions.donations_annual,
        retirement_contribution_annual=deductions.retirement_contribution_annual,
    )
    return float(compute_annual_tax(taxable, rules))


def estimate_first_year_tax_savings(
    *,
    strategy_id: str,
    estimation_type: str,
    context: dict[str, Any],
    rules: TaxRules,
) -> tuple[DeductionProfile | None, float]:
    """Return strategy deduction profile (if any) and year-1 tax savings in LKR."""
    baseline = _deductions_from_context(context)
    annual_income = float(context.get("annual_income", 0.0) or 0.0)
    if annual_income <= 0:
        return None, 0.0

    baseline_tax = _tax_for_income(annual_income, baseline, rules)
    d = rules.deductions
    sid = strategy_id.upper()
    strategy = DeductionProfile(**baseline.__dict__)

    if estimation_type in {"deduction_cap_gap", "deduction_cap_pct_taxable", "deduction_cap_fixed"}:
        if "S001" in sid or "HEALTH_LIFE" in sid:
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "life_insurance_premium_annual": max(
                        baseline.life_insurance_premium_annual,
                        d.get("life_insurance_premium_cap_annual", 0.0),
                    ),
                    "health_insurance_premium_annual": max(
                        baseline.health_insurance_premium_annual,
                        d.get("health_insurance_premium_cap_annual", 0.0),
                    ),
                }
            )
        elif "S002" in sid or "RETIREMENT" in sid:
            cap = min(
                d.get("retirement_contribution_cap_annual", 0.0),
                annual_income * d.get("retirement_contribution_cap_pct_of_income", 0.0),
            )
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "retirement_contribution_annual": max(baseline.retirement_contribution_annual, cap),
                }
            )
        elif "S003" in sid or "CHARITY" in sid:
            cap = annual_income * d.get("charitable_donations_cap_pct_of_taxable", 0.0)
            strategy = DeductionProfile(
                **{**baseline.__dict__, "donations_annual": max(baseline.donations_annual, cap)}
            )
        elif "S004" in sid or "RENT" in sid:
            rent = baseline.rent_paid_annual
            if rent <= 0:
                rent = min(annual_income * 0.15, d.get("rent_relief_cap_annual", 0.0) / max(d.get("rent_relief_pct", 0.25), 1e-6))
            strategy = DeductionProfile(**{**baseline.__dict__, "rent_paid_annual": rent})
        elif "S005" in sid or "HOME_LOAN" in sid:
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "home_loan_interest_annual": max(
                        baseline.home_loan_interest_annual,
                        d.get("home_loan_interest_cap_annual", 0.0),
                    ),
                }
            )
        elif "S008" in sid or "EPF" in sid:
            cap = min(
                d.get("retirement_contribution_cap_annual", 0.0) * 0.5,
                annual_income * 0.05,
            )
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "retirement_contribution_annual": max(baseline.retirement_contribution_annual, cap),
                }
            )
        elif "S009" in sid or "BUSINESS" in sid:
            extra = annual_income * 0.08
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "donations_annual": baseline.donations_annual + extra * 0.25,
                    "retirement_contribution_annual": baseline.retirement_contribution_annual + extra * 0.75,
                }
            )
        else:
            uplift = annual_income * 0.03
            strategy = DeductionProfile(
                **{
                    **baseline.__dict__,
                    "life_insurance_premium_annual": baseline.life_insurance_premium_annual + uplift * 0.5,
                }
            )
    elif estimation_type == "withholding_gap_estimate":
        strategy = baseline
        savings = max(0.0, baseline_tax * 0.05)
        return strategy, savings
    elif estimation_type == "indirect_tax_savings_flag":
        return None, 0.0
    elif "S006" in sid or "CASHFLOW" in sid:
        return None, 0.0
    else:
        strategy = baseline

    strategy_tax = _tax_for_income(annual_income, strategy, rules)
    return strategy, max(0.0, baseline_tax - strategy_tax)


def build_strategy_snapshot(
    *,
    strategy_id: str,
    estimation_type: str,
    context: dict[str, Any],
    rules: TaxRules,
    snapshot: SimulationSnapshot,
) -> SimulationSnapshot:
    """Attach ``strategy_deductions`` to a :class:`SimulationSnapshot`."""
    from impact.types import SimulationSnapshot as Snap

    strategy_deductions, _ = estimate_first_year_tax_savings(
        strategy_id=strategy_id,
        estimation_type=estimation_type,
        context=context,
        rules=rules,
    )
    if strategy_deductions is None:
        return snapshot
    return Snap(
        annual_income=snapshot.annual_income,
        monthly_expenses=snapshot.monthly_expenses,
        monthly_debt_service=snapshot.monthly_debt_service,
        liquid_savings=snapshot.liquid_savings,
        existing_investments=snapshot.existing_investments,
        baseline_deductions=snapshot.baseline_deductions,
        strategy_deductions=strategy_deductions,
    )


__all__ = [
    "build_strategy_snapshot",
    "estimate_first_year_tax_savings",
]
