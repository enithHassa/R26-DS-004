import { describe, expect, it } from "vitest";

import {
  EMPTY_INCOME_FORM,
  hydrateIncomeAmounts,
  previewAppliedLkr,
  resolveMinQualifyingAmount,
  resolveReliefCapAmount,
  type ReliefEntry,
} from "./types";

const FILM_QUOTE =
  "(i) in the production of a film at a cost of (including promotional expenditure of such film) not less than five million rupees";

const CINEMA_QUOTE =
  "(ii) in the construction and equipping of a new cinema at a cost of not exceeding twenty-five million rupees";

const income = hydrateIncomeAmounts({
  taxpayerName: "",
  tin: "",
  form: { ...EMPTY_INCOME_FORM },
  employmentMode: "components",
  businessMode: "net",
  investmentMode: "components",
  otherMode: "components",
  employmentAmounts: { emp_salary: "1800000" },
  businessAmounts: {},
  investmentAmounts: { inv_interest: "2000000" },
  otherAmounts: {},
  otherCustomRows: [],
  interestSchedule: [],
  apitAlreadyPaid: "0",
  hasTerminalBenefits: false,
  terminalBenefits: [],
});

function filmEntry(overrides: Partial<ReliefEntry> = {}): ReliefEntry {
  return {
    assessment_year: "2025_26",
    entry_id: "film-1",
    compare_group_id: "qp_film_production",
    display_name: "Expenditure on film production",
    question_prompt: "Film?",
    sort_order: 1,
    input_kind: "amount",
    cap_amount: null,
    min_qualifying_amount: "5000000",
    unit: "lkr",
    act_name: "Act",
    section_ref: "1(f)",
    quote: FILM_QUOTE,
    source_doc_id: "doc",
    ...overrides,
  };
}

describe("film / cinema min vs cap", () => {
  it("rejects film claims below five million", () => {
    expect(previewAppliedLkr(filmEntry(), income, 230, true)).toBe(0);
    expect(previewAppliedLkr(filmEntry(), income, 5_000_000, true)).toBe(5_000_000);
  });

  it("parses the floor from the Act quote when the field is missing", () => {
    const entry = filmEntry({ min_qualifying_amount: null, cap_amount: null });
    expect(resolveMinQualifyingAmount(entry)).toBe(5_000_000);
    expect(previewAppliedLkr(entry, income, 230, true)).toBe(0);
  });

  it("keeps cinema as a ceiling, not a minimum", () => {
    const cinema = filmEntry({
      compare_group_id: "qp_cinema",
      display_name: "Cinema",
      quote: CINEMA_QUOTE,
      cap_amount: "25000000",
      min_qualifying_amount: null,
    });
    expect(resolveMinQualifyingAmount(cinema)).toBeNull();
    expect(resolveReliefCapAmount(cinema)).toBe(25_000_000);
    expect(previewAppliedLkr(cinema, income, 30_000_000, true)).toBe(25_000_000);
    expect(previewAppliedLkr(cinema, income, 230, true)).toBe(230);
  });
});
