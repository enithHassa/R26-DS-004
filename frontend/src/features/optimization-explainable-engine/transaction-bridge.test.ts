import { describe, expect, it } from "vitest";

import { mergeBreakdownIntoIncome } from "@/lib/profile-bridge/transaction-summary-to-oe-income";

import {
  interestIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  rebalanceBankTaxablePool,
  totalIncomeLkr,
} from "./income-aggregate";
import type { InterviewIncomeState } from "./types";
import { hydrateIncomeAmounts } from "./types";

function baseIncome(overrides: Partial<InterviewIncomeState> = {}): InterviewIncomeState {
  return hydrateIncomeAmounts({
    taxpayerName: "Test",
    tin: "123",
    form: {
      employment_income: "0",
      employment_final_withholding: "0",
      business_income: "0",
      business_gross: "0",
      business_deductions: "0",
      capital_allowances: "0",
      investment_income: "0",
      investment_final_withholding: "0",
      other_income: "0",
      other_final_withholding: "0",
    },
    employmentMode: "components",
    businessMode: "net",
    investmentMode: "components",
    otherMode: "components",
    employmentAmounts: { emp_salary: "1600000", emp_bonus: "0" },
    businessAmounts: { biz_net_profits: "0" },
    investmentAmounts: {
      inv_interest: "2000000",
      inv_rents: "0",
      inv_dividends: "0",
    },
    otherAmounts: { oth_residual: "0" },
    otherCustomRows: [],
    interestSchedule: [
      { id: "bank-1", label: "Bank interest", interest: "2000000", wht: "0" },
    ],
    apitAlreadyPaid: "0",
    hasTerminalBenefits: false,
    terminalBenefits: [],
    bankTaxablePoolLkr: null,
    ...overrides,
  });
}

describe("Comp1 → OE taxable pool", () => {
  it("puts the YA taxable total in Other, clearing demo seeds", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [{ classKey: "unknown", amount: 31_940_375 }],
      "replace",
    );

    expect(merged.bankTaxablePoolLkr).toBe("31940375");
    expect(merged.employmentAmounts.emp_salary).toBe("0");
    expect(otherIncomeLkr(merged)).toBe(31_940_375);
    expect(totalIncomeLkr(merged)).toBe(31_940_375);
  });

  it("moves known employment out of Other so heads still sum to the pool", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [
        { classKey: "employment_income", amount: 2_310 },
        { classKey: "unknown", amount: 31_938_065 },
      ],
      "replace",
    );

    expect(merged.employmentAmounts.emp_salary).toBe("2310");
    expect(otherIncomeLkr(merged)).toBe(31_938_065);
    expect(totalIncomeLkr(merged)).toBe(31_940_375);
  });

  it("rebalances Other when employment is edited after the Comp 1 push", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [{ classKey: "unknown", amount: 1_000_000 }],
      "replace",
    );

    const afterEdit = rebalanceBankTaxablePool({
      ...merged,
      employmentAmounts: { ...merged.employmentAmounts, emp_salary: "250000" },
    });

    expect(afterEdit.employmentAmounts.emp_salary).toBe("250000");
    expect(otherIncomeLkr(afterEdit)).toBe(750_000);
    expect(totalIncomeLkr(afterEdit)).toBe(1_000_000);
  });

  it("skips zero / non-taxable interest so AIT-exempt Comp1 interest stays out of OE", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome({
        investmentAmounts: { inv_interest: "0", inv_rents: "0", inv_dividends: "0" },
        interestSchedule: [],
      }),
      [
        { classKey: "interest_income", amount: 0 },
        { classKey: "freelance_service", amount: 80_000 },
      ],
      "replace",
    );

    expect(merged.businessAmounts.biz_net_profits).toBe("80000");
    expect(interestIncomeLkr(merged)).toBe(0);
    expect(otherIncomeLkr(merged)).toBe(0);
    expect(totalIncomeLkr(merged)).toBe(80_000);
  });

  it("syncs WHT schedule when taxable interest is present", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [{ classKey: "interest_income", amount: 1443.21 }],
      "replace",
    );

    expect(merged.investmentAmounts.inv_interest).toBe("1443");
    expect(interestIncomeLkr(merged)).toBe(1443);
    expect(investmentIncomeLkr(merged)).toBe(1443);
    expect(otherIncomeLkr(merged)).toBe(0);
    expect(totalIncomeLkr(merged)).toBe(1443);
  });

  it("writes Comp1 withholding_tax onto Bank interest WHT deducted", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome({
        investmentAmounts: { inv_interest: "0", inv_rents: "0", inv_dividends: "0" },
        interestSchedule: [],
        bankTaxablePoolLkr: null,
      }),
      [
        { classKey: "interest_income", amount: 2_310 },
        { classKey: "withholding_tax", amount: 115 },
      ],
      "replace",
    );

    const bankLine = merged.interestSchedule.find((line) => line.id === "comp1-bank-interest");
    expect(bankLine?.label).toBe("Bank interest (classified)");
    expect(bankLine?.interest).toBe("2310");
    expect(bankLine?.wht).toBe("115");
    expect(interestIncomeLkr(merged)).toBe(2_310);
    // WHT must not inflate assessable income / bank pool.
    expect(totalIncomeLkr(merged)).toBe(2_310);
    expect(merged.bankTaxablePoolLkr).toBe("2310");
  });

  it("add mode layers bank evidence on existing profile totals", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome({
        employmentAmounts: { emp_salary: "100000", emp_bonus: "0" },
        interestSchedule: [],
        investmentAmounts: { inv_interest: "0", inv_rents: "0", inv_dividends: "0" },
        bankTaxablePoolLkr: null,
      }),
      [{ classKey: "employment_income", amount: 50_000 }],
      "add",
    );

    expect(merged.employmentAmounts.emp_salary).toBe("150000");
  });
});
