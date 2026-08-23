/**
 * Relief Interview session types (Phase 1 confirmed YA range).
 */

import type {
  BusinessInputMode,
  EmploymentInputMode,
  IncomeFormSlice,
  InvestmentInputMode,
  OtherCustomRow,
  OtherInputMode,
} from "./income-cards";
import type { ReliefAnswer } from "./catalog-types";

/** Phase 1 confirmed assessment years (empty catalogs until later phases). */
export const RELIEF_INTERVIEW_YAS = [
  "2018_19",
  "2019_20",
  "2020_21",
  "2021_22",
  "2022_23",
  "2023_24",
  "2024_25",
  "2025_26",
] as const;

export type ReliefInterviewYa = (typeof RELIEF_INTERVIEW_YAS)[number];

/** Filing-catalog / calculate() enum — only these years have a verified field pack. */
export type FilingCatalogYa = "2024_25" | "2025_26";

export function isFilingCatalogYa(ya: string): ya is FilingCatalogYa {
  return ya === "2024_25" || ya === "2025_26";
}

/** Display label e.g. 2024_25 → 2024/25 */
export function yaDisplay(ya: string): string {
  const m = /^(\d{4})_(\d{2})$/.exec(ya);
  if (!m) return ya;
  return `${m[1]}/${m[2]}`;
}

/**
 * Catalog API only accepts engine years. For older interview YAs, reuse the
 * nearest engine pack for field lists and show a limited-verification badge.
 */
export function catalogYaForInterview(ya: ReliefInterviewYa): FilingCatalogYa {
  if (isFilingCatalogYa(ya)) return ya;
  return "2024_25";
}

export function adjacentCompareYa(ya: ReliefInterviewYa): ReliefInterviewYa {
  const idx = RELIEF_INTERVIEW_YAS.indexOf(ya);
  if (idx <= 0) return RELIEF_INTERVIEW_YAS[1] ?? ya;
  return RELIEF_INTERVIEW_YAS[idx - 1] ?? ya;
}

export const EMPTY_INCOME_FORM: IncomeFormSlice = {
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
};

export type ReliefInterviewIncomeState = {
  form: IncomeFormSlice;
  employmentMode: EmploymentInputMode;
  businessMode: BusinessInputMode;
  investmentMode: InvestmentInputMode;
  otherMode: OtherInputMode;
  employmentAmounts: Record<string, string>;
  businessAmounts: Record<string, string>;
  investmentAmounts: Record<string, string>;
  otherAmounts: Record<string, string>;
  otherCustomRows: OtherCustomRow[];
};

export type ReliefInterviewSession = {
  assessmentYear: ReliefInterviewYa;
  compareYear: ReliefInterviewYa;
  income: ReliefInterviewIncomeState;
  /** Answers keyed by entry_id for the as-of YA interview */
  reliefAnswers: ReliefAnswer[];
  /** Compare page: selected compare_group_id */
  selectedCompareGroupId: string | null;
  /** Last official calculate() id from Result (engine years only). */
  lastCalcId: string | null;
  lastOfficialTaxLkr: string | null;
};

export const SESSION_STORAGE_KEY = "adaptive-tax.relief-interview.v1";

export function createDefaultSession(): ReliefInterviewSession {
  const assessmentYear: ReliefInterviewYa = "2025_26";
  return {
    assessmentYear,
    compareYear: adjacentCompareYa(assessmentYear),
    income: {
      form: { ...EMPTY_INCOME_FORM },
      employmentMode: "components",
      businessMode: "net",
      investmentMode: "components",
      otherMode: "components",
      employmentAmounts: {},
      businessAmounts: {},
      investmentAmounts: {},
      otherAmounts: {},
      otherCustomRows: [],
    },
    reliefAnswers: [],
    selectedCompareGroupId: null,
    lastCalcId: null,
    lastOfficialTaxLkr: null,
  };
}
