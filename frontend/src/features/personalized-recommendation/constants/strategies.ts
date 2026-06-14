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
