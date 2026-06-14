import type { DerivedFeatures } from "../types";

/** Maps catalog strategy codes to profile eligibility flags used in rules filtering. */
export const STRATEGY_FLAG_REQUIREMENTS: Record<
  string,
  { flags: (keyof DerivedFeatures["eligibility_flags"] extends never ? string : string)[]; rationale: string }
> = {
  S001_health_life_premium_optimisation: {
    flags: ["above_tax_threshold", "has_health_insurance"],
    rationale: "Requires taxable income and existing health cover to optimise premium reliefs.",
  },
  S002_retirement_contribution_topup: {
    flags: ["has_employer_provident", "has_disposable_income"],
    rationale: "EPF/retirement top-ups need provident participation and surplus cashflow.",
  },
  S003_charity_optimisation: {
    flags: ["above_tax_threshold", "has_disposable_income"],
    rationale: "Charitable deductions matter when you pay tax and can fund donations.",
  },
  S004_rent_relief_capture: {
    flags: ["above_tax_threshold"],
    rationale: "Rental relief applies when annual income exceeds the tax threshold.",
  },
  S005_home_loan_interest_optimisation: {
    flags: ["has_home_loan", "above_tax_threshold"],
    rationale: "Requires an active home-loan interest claim and taxable income.",
  },
  S006_cashflow_stabilise_before_deductions: {
    flags: ["has_liquidity_buffer"],
    rationale: "Stabilise cashflow before claiming further deductions.",
  },
  S007_employment_withholding_reconciliation: {
    flags: ["above_tax_threshold", "has_employer_provident"],
    rationale: "Payroll withholding reconciliation for employed taxpayers.",
  },
  S008_epf_voluntary_topup: {
    flags: ["has_employer_provident", "has_disposable_income"],
    rationale: "Voluntary EPF contributions when employed with surplus income.",
  },
  S009_business_expense_deduction: {
    flags: ["above_tax_threshold", "has_disposable_income"],
    rationale: "Business expense planning for professionals and owners with tax exposure.",
  },
};

export type EligibilityTraceItem = {
  flag: string;
  required: boolean;
  met: boolean;
  label: string;
};

const FLAG_LABELS: Record<string, string> = {
  above_tax_threshold: "Above personal tax threshold",
  has_disposable_income: "Positive disposable income",
  has_employer_provident: "Employer / EPF participation",
  has_health_insurance: "Health insurance in place",
  has_home_loan: "Home loan interest declared",
  is_retirement_eligible: "Age 50+ (retirement planning)",
  has_dependents: "Has dependents",
  has_liquidity_buffer: "3+ months liquidity buffer",
};

export function buildEligibilityTrace(
  strategyCode: string,
  features: DerivedFeatures | undefined,
): { items: EligibilityTraceItem[]; allMet: boolean; rationale: string } {
  const spec = STRATEGY_FLAG_REQUIREMENTS[strategyCode];
  if (!spec || !features) {
    return { items: [], allMet: false, rationale: spec?.rationale ?? "Select a profile to evaluate eligibility." };
  }

  const items: EligibilityTraceItem[] = spec.flags.map((flag) => {
    const met = Boolean(features.eligibility_flags[flag]);
    return {
      flag,
      required: true,
      met,
      label: FLAG_LABELS[flag] ?? flag,
    };
  });

  return {
    items,
    allMet: items.every((i) => i.met),
    rationale: spec.rationale,
  };
}
