import type { TaxableIncomeLineItem } from "@/features/transaction-semantic/api";
import type { InterviewIncomeState } from "@/features/optimization-explainable-engine/types";

function num(raw: number | string | undefined | null): number {
  if (raw == null) return 0;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) ? n : 0;
}

function addAmount(current: string, delta: number): string {
  const next = num(current) + delta;
  return next > 0 ? String(Math.round(next)) : "0";
}

/**
 * Merge transaction-semantic taxable income buckets into existing OE income.
 * Amounts are additive so auditors can layer bank evidence on profile totals.
 */
export function mergeBreakdownIntoIncome(
  income: InterviewIncomeState,
  lines: { classKey: string; amount: number }[],
): InterviewIncomeState {
  const asApiLines = lines.map((line) => ({
    class_key: line.classKey,
    tax_rule_code: null,
    taxability_status: "taxable",
    transaction_count: 0,
    gross_amount_lkr: String(line.amount),
    taxable_amount_lkr: String(line.amount),
  }));
  return mergeTaxableSummaryIntoIncome(income, asApiLines);
}

export function mergeTaxableSummaryIntoIncome(
  income: InterviewIncomeState,
  lines: TaxableIncomeLineItem[],
): InterviewIncomeState {
  const employment = { ...income.employmentAmounts };
  const business = { ...income.businessAmounts };
  const investment = { ...income.investmentAmounts };
  const other = { ...income.otherAmounts };

  for (const line of lines) {
    const amount = num(line.taxable_amount_lkr);
    if (amount <= 0) continue;

    switch (line.class_key) {
      case "employment_income":
        employment.emp_salary = addAmount(employment.emp_salary ?? "0", amount);
        break;
      case "bonus_performance":
        employment.emp_bonus = addAmount(employment.emp_bonus ?? "0", amount);
        break;
      case "freelance_service":
      case "business_profit":
        business.biz_net_profits = addAmount(business.biz_net_profits ?? "0", amount);
        break;
      case "interest_income":
        investment.inv_interest = addAmount(investment.inv_interest ?? "0", amount);
        break;
      case "dividend_income":
        investment.inv_dividends = addAmount(investment.inv_dividends ?? "0", amount);
        break;
      case "rental_income":
        investment.inv_rents = addAmount(investment.inv_rents ?? "0", amount);
        break;
      case "capital_gain":
        investment.inv_gains_investment_assets = addAmount(
          investment.inv_gains_investment_assets ?? "0",
          amount,
        );
        break;
      case "gratuity":
        employment.emp_gratuity = addAmount(employment.emp_gratuity ?? "0", amount);
        break;
      default:
        other.oth_residual = addAmount(other.oth_residual ?? "0", amount);
        break;
    }
  }

  return {
    ...income,
    employmentMode: "components",
    businessMode: num(business.biz_net_profits) > 0 ? "net" : income.businessMode,
    investmentMode: "components",
    otherMode: "components",
    employmentAmounts: employment,
    businessAmounts: business,
    investmentAmounts: investment,
    otherAmounts: other,
  };
}
