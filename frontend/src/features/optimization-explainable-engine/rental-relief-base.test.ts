import { describe, expect, it } from "vitest";

import { hydrateIncomeAmounts, EMPTY_INCOME_FORM, previewAppliedLkr, incomeBaseLkr } from "./types";
import type { ReliefEntry } from "./types";

function rentEntry(patch: Partial<ReliefEntry> = {}): ReliefEntry {
  return {
    entry_id: "rent-1",
    compare_group_id: "rental_income_relief",
    display_name: "Rental income relief",
    input_kind: "boolean",
    unit: "percent",
    cap_amount: "25",
    auto_applied: false,
    engine_binding: { kind: "none" },
    ...patch,
  };
}

describe("rental income relief base", () => {
  const income = hydrateIncomeAmounts({
    taxpayerName: "",
    tin: "",
    form: { ...EMPTY_INCOME_FORM },
    employmentMode: "components",
    businessMode: "net",
    investmentMode: "components",
    otherMode: "components",
    employmentAmounts: { emp_salary: "10000000" },
    businessAmounts: { biz_net_profits: "20000000" },
    investmentAmounts: { inv_rents: "420000", inv_interest: "100000" },
    otherAmounts: {},
    otherCustomRows: [],
    interestSchedule: [],
    apitAlreadyPaid: "0",
    hasTerminalBenefits: false,
    terminalBenefits: [],
  });

  it("uses rents (420k) not total assessable for percent preview", () => {
    const entry = rentEntry();
    expect(incomeBaseLkr(entry, income)).toBe(420_000);
    expect(previewAppliedLkr(entry, income, 0, true)).toBe(105_000);
  });

  it("still uses rents when binding kind is rent_relief", () => {
    const entry = rentEntry({ engine_binding: { kind: "rent_relief" } });
    expect(previewAppliedLkr(entry, income, 0, true)).toBe(105_000);
  });
});
