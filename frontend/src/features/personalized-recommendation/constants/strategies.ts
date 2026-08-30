/** Catalog strategy keys aligned with `strategy_catalog.yaml`. */
export const CATALOG_STRATEGIES = [
  { code: "S001_health_life_premium_optimisation", label: "Insurance Relief Optimisation" },
  { code: "S002_retirement_contribution_topup", label: "Retirement Contribution Top-up" },
  { code: "S003_charity_optimisation", label: "Charitable Donation Timing & Sizing" },
  { code: "S004_rent_relief_capture", label: "Rental Relief Capture" },
  { code: "S005_home_loan_interest_optimisation", label: "Home Loan Interest Optimisation" },
  { code: "S006_cashflow_stabilise_before_deductions", label: "Cashflow Stabilisation" },
  { code: "S007_employment_withholding_reconciliation", label: "Withholding Reconciliation" },
  { code: "S008_epf_voluntary_topup", label: "EPF Voluntary Top-up" },
  { code: "S009_business_expense_deduction", label: "Business Expense Deduction" },
] as const;

/** Map API recommendation `strategy.code` to catalog `strategy_code`. */
export function recommendationCodeToCatalog(code: string): string {
  const normalized = code.replace(/[^A-Za-z0-9_]/g, "_").toLowerCase();
  const hit = CATALOG_STRATEGIES.find(
    (s) =>
      s.code.toLowerCase() === normalized ||
      normalized.includes(s.code.split("_")[0].toLowerCase()),
  );
  return hit?.code ?? code;
}

/**
 * Plain-language, zero-tax-knowledge subtitle for each catalog strategy —
 * shown in place of the technical `description` field on the user-facing
 * recommendation card. Keyed by catalog code from `strategy_catalog.yaml`.
 */
export const STRATEGY_PLAIN_SUMMARY: Record<string, string> = {
  S001_health_life_premium_optimisation:
    "Pay a bit more for health or life insurance, up to the allowed limit, and pay less tax in return.",
  S002_retirement_contribution_topup:
    "Put a bit more into your retirement savings, up to the allowed limit, and pay less tax now.",
  S003_charity_optimisation:
    "Give a well-timed, well-sized donation to charity to lower your tax bill without straining your budget.",
  S004_rent_relief_capture:
    "If you pay rent and have proof of it, you may be able to claim a tax break for it.",
  S005_home_loan_interest_optimisation:
    "If you're paying interest on a home loan, you may be able to deduct some of it from your tax, without over-committing to debt.",
  S006_cashflow_stabilise_before_deductions:
    "Your day-to-day finances look stretched — this suggests steadying your cashflow and debt first, before taking on more tax-saving commitments.",
  S007_employment_withholding_reconciliation:
    "Your employer takes tax out of your pay each month automatically — this checks whether they've taken the right amount, or too much/too little.",
  S008_epf_voluntary_topup:
    "Contribute a bit more than the required minimum to your EPF retirement fund to lower your taxable income.",
  S009_business_expense_deduction:
    "Make sure all your allowed business costs are being claimed, so you're not paying tax on money you already spent running your business.",
  S010_terminal_benefit_planning:
    "Time your retirement or resignation carefully so more of your final retirement payout is tax-free.",
};
