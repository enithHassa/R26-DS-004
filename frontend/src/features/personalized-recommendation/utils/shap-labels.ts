/** Map raw SHAP / pipeline feature names to user-facing labels. */

const EXACT: Record<string, string> = {
  remainder__strategy_priority_hint: "Strategy catalog priority",
  remainder__gross_monthly_income_lkr: "Gross monthly income",
  remainder__monthly_expenses_lkr: "Monthly expenses",
  remainder__liquid_savings_lkr: "Liquid savings",
  remainder__debt_to_income: "Debt-to-income ratio",
  remainder__liquidity_months: "Liquidity buffer (months)",
  remainder__home_loan_interest_annual_lkr: "Home loan interest (annual)",
  remainder__life_insurance_premium_annual_lkr: "Life insurance premium",
  remainder__baseline_tax_liability_lkr: "Baseline tax liability",
  remainder__savings_rate: "Savings rate",
  remainder__effective_tax_rate: "Effective tax rate",
};

export function friendlyShapFeature(raw: string): string {
  if (EXACT[raw]) return EXACT[raw];
  if (raw.startsWith("cat__strategy_id_")) {
    const id = raw.replace("cat__strategy_id_", "").replace(/_/g, " ");
    return `Strategy: ${id}`;
  }
  if (raw.startsWith("cat__strategy_category_")) {
    return `Category: ${raw.replace("cat__strategy_category_", "").replace(/_/g, " ")}`;
  }
  if (raw.startsWith("cat__occupation_")) {
    return `Occupation: ${raw.replace("cat__occupation_", "")}`;
  }
  if (raw.startsWith("cat__archetype_")) {
    return `Archetype: ${raw.replace("cat__archetype_", "")}`;
  }
  if (raw.startsWith("remainder__")) {
    return raw
      .replace("remainder__", "")
      .replace(/_lkr$/, " (LKR)")
      .replace(/_/g, " ");
  }
  return raw.replace(/_/g, " ");
}
