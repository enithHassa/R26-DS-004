/** Map raw SHAP / pipeline feature names to user-facing labels. */

import { CATALOG_STRATEGIES } from "../constants/strategies";

const EXACT: Record<string, string> = {
  remainder__strategy_priority_hint: "Strategy catalog priority",
  remainder__gross_monthly_income_lkr: "Gross monthly income",
  remainder__monthly_expenses_lkr: "Monthly expenses",
  remainder__liquid_savings_lkr: "Liquid savings",
  remainder__debt_to_income: "Debt-to-income ratio",
  remainder__liquidity_months: "Emergency savings buffer (months)",
  remainder__home_loan_interest_annual_lkr: "Home loan interest (annual)",
  remainder__life_insurance_premium_annual_lkr: "Life insurance premium",
  remainder__baseline_tax_liability_lkr: "Current annual tax liability",
  remainder__savings_rate: "Savings rate",
  remainder__effective_tax_rate: "Effective tax rate",
  remainder__gross_annual_taxable_income_lkr: "Annual taxable income",
  remainder__donations_annual_lkr: "Charitable donations (annual)",
  remainder__epf_balance_lkr: "EPF balance",
  remainder__years_employed: "Years employed",
  remainder__dependents: "Number of dependents",
  remainder__expense_ratio: "Expense-to-income ratio",
  remainder__debt_service_ratio: "Debt service ratio",
  remainder__disposable_income_monthly_lkr: "Monthly disposable income",
  remainder__monthly_debt_service_lkr: "Monthly debt repayments",
  remainder__existing_investments_lkr: "Existing investments",
  remainder__total_debt_lkr: "Total debt",
  remainder__etf_balance_lkr: "ETF balance",
  "src employment share": "Employment income share",
  "src business share": "Business income share",
  "src dividend share": "Dividend income share",
  "src interest share": "Interest income share",
  "src rental share": "Rental income share",
  "src other share": "Other income share",
};

const DESCRIPTIONS: Record<string, string> = {
  remainder__debt_to_income:
    "Lower debt relative to income tends to improve feasibility and ranking for deduction strategies.",
  remainder__baseline_tax_liability_lkr:
    "Higher baseline tax means more room for tax-saving strategies to matter.",
  remainder__life_insurance_premium_annual_lkr:
    "Existing insurance premiums signal eligibility for insurance relief strategies.",
  remainder__liquid_savings_lkr:
    "Available cash affects whether the taxpayer can act on strategies that need upfront payments.",
  remainder__savings_rate:
    "A healthy savings rate suggests capacity to adopt new financial commitments.",
  remainder__home_loan_interest_annual_lkr:
    "Home loan interest is a key input for mortgage-related deduction strategies.",
  remainder__gross_monthly_income_lkr:
    "Income level shapes which reliefs and caps apply to this taxpayer.",
  remainder__effective_tax_rate:
    "The taxpayer's current tax rate affects the benefit from additional deductions.",
};

function strategyLabelFromId(id: string): string {
  const hit = CATALOG_STRATEGIES.find(
    (s) => s.code.toLowerCase() === id.toLowerCase() || id.toLowerCase().startsWith(s.code.split("_")[0].toLowerCase()),
  );
  if (hit) return hit.label;
  return id
    .replace(/^S\d+_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function friendlyShapFeature(raw: string): string {
  if (EXACT[raw]) return EXACT[raw];

  if (raw.startsWith("cat__strategy_id_")) {
    const id = raw.replace("cat__strategy_id_", "");
    return `Strategy match: ${strategyLabelFromId(id)}`;
  }

  if (raw.startsWith("cat__strategy_category_")) {
    return `Category: ${raw.replace("cat__strategy_category_", "").replace(/_/g, " ")}`;
  }

  if (raw.startsWith("cat__occupation_")) {
    return `Occupation: ${raw.replace("cat__occupation_", "").replace(/_/g, " ")}`;
  }

  if (raw.startsWith("cat__archetype_")) {
    return `Financial profile type: ${raw.replace("cat__archetype_", "").replace(/_/g, " ")}`;
  }

  if (raw.startsWith("cat__risk_tolerance_")) {
    return `Risk comfort: ${raw.replace("cat__risk_tolerance_", "")}`;
  }

  if (raw.startsWith("cat__gender_")) {
    return `Gender: ${raw.replace("cat__gender_", "")}`;
  }

  if (raw.startsWith("cat__marital_status_")) {
    return `Marital status: ${raw.replace("cat__marital_status_", "").replace(/_/g, " ")}`;
  }

  if (raw.startsWith("cat__province_") || raw.startsWith("cat__district_")) {
    return `District: ${raw.replace(/^cat__(province|district)_/, "").replace(/_/g, " ")}`;
  }

  if (raw.startsWith("remainder__src_")) {
    const key = raw.replace("remainder__", "").replace(/_/g, " ");
    return EXACT[key] ?? key.replace(/ share$/, " income share");
  }

  if (raw.startsWith("remainder__")) {
    const key = raw.replace("remainder__", "");
    return EXACT[`remainder__${key}`] ?? key.replace(/_lkr$/, " (LKR)").replace(/_/g, " ");
  }

  return raw.replace(/_/g, " ");
}

export function describeShapFeature(raw: string): string | undefined {
  if (DESCRIPTIONS[raw]) return DESCRIPTIONS[raw];

  if (raw.startsWith("cat__strategy_id_")) {
    return "The model recognises this strategy as a strong fit for the taxpayer's profile.";
  }

  if (raw.startsWith("cat__occupation_")) {
    return "Occupation affects which strategies are typically relevant for salaried vs self-employed taxpayers.";
  }

  if (raw.startsWith("cat__archetype_")) {
    return "The taxpayer's overall financial behaviour pattern influences strategy suitability.";
  }

  return undefined;
}
