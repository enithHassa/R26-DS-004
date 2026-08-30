/**
 * Income totals for Optimization and Explainable Engine calculate API.
 * Gross tax base = employment + business + investment + other.
 * Interest and rents are subsets used as relief bases; they are not added again.
 */

import { parseLkr } from "./format-lkr";
import {
  exclusionFieldIds,
  includeFieldIds,
  incomeCatalogCard,
} from "./income-catalog";
import type { InterviewIncomeState } from "./types";

const EMPLOYMENT_CARD = incomeCatalogCard("employment");
const INVESTMENT_CARD = incomeCatalogCard("investment");
const EMPLOYMENT_INCLUDE_IDS = includeFieldIds(EMPLOYMENT_CARD);
const INVESTMENT_INCLUDE_IDS = includeFieldIds(INVESTMENT_CARD);
const EMPLOYMENT_FWH_IDS = exclusionFieldIds(EMPLOYMENT_CARD).filter(
  (id) => id === "emp_final_withholding",
);
const INVESTMENT_EXCLUSION_IDS = exclusionFieldIds(INVESTMENT_CARD);

function sumIds(amounts: Record<string, string>, ids: string[]): number {
  return ids.reduce((sum, id) => sum + parseLkr(amounts[id] ?? "0"), 0);
}

export function interestScheduleTotals(income: InterviewIncomeState): {
  interest: number;
  wht: number;
} {
  const lines = income.interestSchedule ?? [];
  if (lines.length === 0) {
    return {
      interest: parseLkr(income.investmentAmounts.inv_interest ?? "0"),
      wht: 0,
    };
  }
  return {
    interest: lines.reduce((sum, line) => sum + parseLkr(line.interest), 0),
    wht: lines.reduce((sum, line) => sum + parseLkr(line.wht), 0),
  };
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
  const included = sumIds(income.employmentAmounts, EMPLOYMENT_INCLUDE_IDS);
  const excluded = sumIds(income.employmentAmounts, EMPLOYMENT_FWH_IDS);
  return Math.max(0, included - excluded);
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
  const schedule = interestScheduleTotals(income);
  const otherIncludes = INVESTMENT_INCLUDE_IDS.filter((id) => id !== "inv_interest");
  const included = schedule.interest + sumIds(income.investmentAmounts, otherIncludes);
  const excluded = sumIds(income.investmentAmounts, INVESTMENT_EXCLUSION_IDS);
  return Math.max(0, included - excluded);
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
  return interestScheduleTotals(income).interest;
}

export function whtAlreadyPaidLkr(income: InterviewIncomeState): number {
  return interestScheduleTotals(income).wht;
}

/** APIT deducted from salary — prepaid employment tax credit (not part of assessable income). */
export function apitAlreadyPaidLkr(income: InterviewIncomeState): number {
  return parseLkr(income.apitAlreadyPaid ?? "0");
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
