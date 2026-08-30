/**
 * Income totals for Optimization and Explainable calculate API.
 * Matches Relief Interview summation / deduction rules.
 */

import { parseLkr } from "./format-lkr";
import type { InterviewIncomeState } from "./types";

function sumAmounts(amounts: Record<string, string>): number {
  return Object.values(amounts).reduce((acc, value) => acc + parseLkr(value), 0);
}

function investmentIncludeTotal(amounts: Record<string, string>): number {
  const includeIds = ["inv_interest", "inv_rents", "inv_dividends", "inv_royalties"];
  return includeIds.reduce((sum, id) => sum + parseLkr(amounts[id] ?? "0"), 0);
}

function investmentExclusionTotal(amounts: Record<string, string>): number {
  return parseLkr(amounts.inv_final_withholding ?? "0");
}

function otherIncludeTotal(income: InterviewIncomeState): number {
  let total = parseLkr(income.otherAmounts.oth_residual ?? "0");
  for (const row of income.otherCustomRows) {
    total += parseLkr(row.amount);
  }
  return total;
}

export function employmentIncomeLkr(income: InterviewIncomeState): number {
  if (income.employmentMode === "total") {
    return Math.max(
      0,
      parseLkr(income.form.employment_income) -
        parseLkr(income.form.employment_final_withholding),
    );
  }
  return sumAmounts(income.employmentAmounts);
}

export function businessIncomeLkr(income: InterviewIncomeState): number {
  if (income.businessMode === "net") {
    const catalogNet = parseLkr(income.businessAmounts.biz_net_profits ?? "0");
    if (catalogNet > 0) return catalogNet;
    return parseLkr(income.form.business_income);
  }
  if (income.businessMode === "breakdown") {
    const gross = parseLkr(income.businessAmounts.biz_gross ?? income.form.business_gross);
    const deductions = Math.min(
      parseLkr(income.businessAmounts.biz_deductions ?? income.form.business_deductions),
      gross,
    );
    const remaining = gross - deductions;
    const ca = Math.min(
      parseLkr(income.businessAmounts.biz_capital_allowances ?? income.form.capital_allowances),
      remaining,
    );
    return Math.max(0, gross - deductions - ca);
  }
  return parseLkr(income.form.business_income);
}

export function investmentIncomeLkr(income: InterviewIncomeState): number {
  if (income.investmentMode === "total") {
    return Math.max(
      0,
      parseLkr(income.form.investment_income) -
        parseLkr(income.form.investment_final_withholding),
    );
  }
  return Math.max(0, investmentIncludeTotal(income.investmentAmounts) - investmentExclusionTotal(income.investmentAmounts));
}

export function otherIncomeLkr(income: InterviewIncomeState): number {
  if (income.otherMode === "total") {
    return Math.max(
      0,
      parseLkr(income.form.other_income) - parseLkr(income.form.other_final_withholding),
    );
  }
  return Math.max(
    0,
    otherIncludeTotal(income) - parseLkr(income.otherAmounts.oth_final_withholding ?? "0"),
  );
}

export function interestIncomeLkr(income: InterviewIncomeState): number {
  if (income.investmentMode === "components") {
    return parseLkr(income.investmentAmounts.inv_interest ?? "0");
  }
  return 0;
}

export function rentsIncomeLkr(income: InterviewIncomeState): number {
  if (income.investmentMode === "components") {
    return parseLkr(income.investmentAmounts.inv_rents ?? "0");
  }
  return 0;
}

export function totalIncomeLkr(income: InterviewIncomeState): number {
  return (
    employmentIncomeLkr(income) +
    businessIncomeLkr(income) +
    investmentIncomeLkr(income) +
    otherIncomeLkr(income)
  );
}
