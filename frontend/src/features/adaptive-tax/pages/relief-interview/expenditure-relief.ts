/**
 * Fifth Schedule ¶2(f) expenditure relief — presentation subcategories.
 * Act lists (i)–(v); the engine still takes one combined filing line
 * (`relief_fifth_sch_2f_expenditure`). Do not invent per-item component_ids.
 */

export const EXPENDITURE_RELIEF_GROUP = "expenditure_relief";

export type ExpenditureSubcategoryId =
  | "health"
  | "education"
  | "housing_loan_interest"
  | "local_pension"
  | "listed_securities";

export type ExpenditureSubcategoryDef = {
  id: ExpenditureSubcategoryId;
  roman: string;
  short_label: string;
  /** Plain-language help for taxpayers */
  help: string;
};

/** IRD / Fifth Sch 2(f) items (i)–(v). */
export const EXPENDITURE_SUBCATEGORIES: readonly ExpenditureSubcategoryDef[] = [
  {
    id: "health",
    roman: "(i)",
    short_label: "Health & medical insurance",
    help: "Medical bills and contributions to medical insurance for you (and covered family members where the Act allows).",
  },
  {
    id: "education",
    roman: "(ii)",
    short_label: "Education (local)",
    help: "Vocational or other education costs incurred in Sri Lanka for you, or for your children.",
  },
  {
    id: "housing_loan_interest",
    roman: "(iii)",
    short_label: "Housing loan interest",
    help: "Interest you paid on a housing loan (not the loan principal).",
  },
  {
    id: "local_pension",
    roman: "(iv)",
    short_label: "Local pension contributions",
    help: "Amounts you paid into a local pension scheme that is not your employer’s scheme (and not paid on the employer’s behalf).",
  },
  {
    id: "listed_securities",
    roman: "(v)",
    short_label: "Listed shares & approved securities",
    help: "Money spent to buy CSE-listed shares/instruments (SEC-licensed) or Treasury bonds/bills under the relevant Ordinances.",
  },
] as const;

export const EXPENDITURE_RELIEF_HEADLINE =
  "Did you spend on any of these personal items this year?";

export const EXPENDITURE_RELIEF_INTRO =
  "“Qualifying expenditure” means only the five kinds of personal spending listed in Fifth Schedule paragraph 2(f). Enter each type separately below. Leave a row at 0 if you had none. The calculator adds them up and applies the yearly cap. This relief ended after 31 December 2022 — it is only for earlier years (through YA 2022/23, and for that year only the first nine months).";

export function emptyExpenditureBreakdown(): Record<ExpenditureSubcategoryId, string> {
  return {
    health: "0",
    education: "0",
    housing_loan_interest: "0",
    local_pension: "0",
    listed_securities: "0",
  };
}

export function sumExpenditureBreakdown(
  amounts: Partial<Record<string, string>>,
): number {
  let total = 0;
  for (const row of EXPENDITURE_SUBCATEGORIES) {
    const raw = String(amounts[row.id] ?? "0").replace(/,/g, "").trim();
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) total += Math.round(n);
  }
  return total;
}

export function isExpenditureReliefGroup(compareGroupId: string): boolean {
  return compareGroupId === EXPENDITURE_RELIEF_GROUP;
}

/**
 * Fifth Sch 2(f) expenditure relief is **not** available from YA 2023/24 onward
 * (removed w.e.f. 1 January 2023 — Act 45/2022 / IRD guidance).
 * Last partial window: first nine months of YA 2022/23 (cap Rs 900,000).
 */
export function isExpenditureReliefAvailableForYa(assessmentYear: string): boolean {
  // Lexicographic order matches YA slug shape YYYY_YY.
  return assessmentYear <= "2022_23";
}
