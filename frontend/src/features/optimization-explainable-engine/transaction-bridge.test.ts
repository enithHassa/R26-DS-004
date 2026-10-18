import { describe, expect, it } from "vitest";

import { mergeBreakdownIntoIncome } from "@/lib/profile-bridge/transaction-summary-to-oe-income";

import { interestIncomeLkr, investmentIncomeLkr, otherIncomeLkr } from "./income-aggregate";
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
    ...overrides,
  });
}

describe("Comp1 → OE taxable bridge", () => {
  it("replace mode writes taxable buckets without stacking on demo seeds", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [
        { classKey: "employment_income", amount: 500_000 },
        { classKey: "unknown", amount: 1_200_000 },
      ],
      "replace",
    );

    expect(merged.employmentAmounts.emp_salary).toBe("500000");
    expect(merged.otherAmounts.oth_residual).toBe("1200000");
    expect(otherIncomeLkr(merged)).toBe(1_200_000);
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
    expect(merged.interestSchedule).toEqual([]);
  });

  it("syncs WHT schedule when taxable interest is present so OE totals match", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome(),
      [{ classKey: "interest_income", amount: 1443.21 }],
      "replace",
    );

    expect(merged.investmentAmounts.inv_interest).toBe("1443");
    expect(merged.interestSchedule).toEqual([
      {
        id: "comp1-bank-interest",
        label: "Bank interest (classified)",
        interest: "1443",
        wht: "0",
      },
    ]);
    expect(interestIncomeLkr(merged)).toBe(1443);
    expect(investmentIncomeLkr(merged)).toBe(1443);
  });

  it("add mode layers bank evidence on existing profile totals", () => {
    const merged = mergeBreakdownIntoIncome(
      baseIncome({
        employmentAmounts: { emp_salary: "100000", emp_bonus: "0" },
        interestSchedule: [],
        investmentAmounts: { inv_interest: "0", inv_rents: "0", inv_dividends: "0" },
      }),
      [{ classKey: "employment_income", amount: 50_000 }],
      "add",
    );

    expect(merged.employmentAmounts.emp_salary).toBe("150000");
  });
});
