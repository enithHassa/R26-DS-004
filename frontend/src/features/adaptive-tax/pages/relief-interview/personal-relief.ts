/**
 * Fifth Schedule 2(a) personal relief — auto for resident individuals.
 * Applied amount for display ≈ min(statutory cap, gross income from the Income step).
 */

import { parseLkr } from "./income-cards";
import type { ReliefInterviewIncomeState } from "./types";

export const PERSONAL_RELIEF_GROUP = "personal_relief";

export function isPersonalReliefGroup(compareGroupId: string): boolean {
  return compareGroupId === PERSONAL_RELIEF_GROUP;
}

/** Rough assessable proxy from interview income (before QP / other reliefs). */
export function estimateGrossIncomeLkr(
  income: ReliefInterviewIncomeState,
): number {
  const form = income.form;
  const sumAmounts = (amounts: Record<string, string>) =>
    Object.values(amounts).reduce((acc, v) => acc + parseLkr(v), 0);

  const employment =
    income.employmentMode === "components"
      ? sumAmounts(income.employmentAmounts)
      : parseLkr(form.employment_income);

  let business = 0;
  if (income.businessMode === "net") {
    business = parseLkr(
      income.businessAmounts.biz_net_profits ?? form.business_income,
    );
  } else if (income.businessMode === "breakdown") {
    business = Math.max(
      0,
      parseLkr(income.businessAmounts.biz_gross ?? "0") -
        parseLkr(income.businessAmounts.biz_deductions ?? "0") -
        parseLkr(income.businessAmounts.biz_capital_allowances ?? "0"),
    );
  } else {
    business = parseLkr(form.business_income);
  }

  const investment =
    income.investmentMode === "components"
      ? sumAmounts(income.investmentAmounts)
      : parseLkr(form.investment_income);

  let other = 0;
  if (income.otherMode === "components") {
    other += parseLkr(income.otherAmounts.oth_residual ?? "0");
    for (const row of income.otherCustomRows) other += parseLkr(row.amount);
  } else {
    other = parseLkr(form.other_income);
  }

  return Math.max(0, employment + business + investment + other);
}

/**
 * Relief that applies for a resident: full cap if income ≥ cap;
 * otherwise income (you cannot get more relief than income).
 */
export function personalReliefAppliedLkr(
  income: ReliefInterviewIncomeState,
  statutoryCap: string | null | undefined,
): number {
  const cap = parseLkr(String(statutoryCap ?? "0"));
  if (cap <= 0) return 0;
  const gross = estimateGrossIncomeLkr(income);
  if (gross <= 0) return 0;
  return Math.min(cap, gross);
}
