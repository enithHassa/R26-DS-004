import { parseLkr } from "./format-lkr";
import {
  employmentIncomeLkr,
  interestIncomeLkr,
  rentsIncomeLkr,
  totalIncomeLkr,
} from "./income-aggregate";
import { emptyAmountsForCard, incomeCatalogCard } from "./income-catalog";

export type OtherCustomRow = {
  key: string;
  label: string;
  amount: string;
};

export {
  employmentIncomeLkr,
  businessIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  interestIncomeLkr,
  rentsIncomeLkr,
  totalIncomeLkr,
  whtAlreadyPaidLkr,
} from "./income-aggregate";

export type ReliefInputKind = "notice" | "yes_no_amount" | "amount" | "boolean";

export type ReliefEngineBinding = {
  kind: string;
  component_id?: string;
};

/** One recipient of a relief the Act enumerates as (i), (ii), (iii)... */
export type ReliefSubItem = {
  component_id: string;
  roman: string;
  label: string;
  quote: string;
};

/** The Act's own wording for a term the relief's eligibility turns on. */
export type ReliefDefinition = {
  term: string;
  text: string;
  section_ref: string;
};

/**
 * Where a relief names only numbered items of another provision, the items it
 * points at, resolved against that provision as compiled for the same year.
 */
export type ReliefCovers = {
  paragraph_ref: string;
  source_group: string;
  source_display_name: string;
  source_act_name: string;
  source_section_ref: string;
  items: ReliefSubItem[];
};

export type ReliefEntry = {
  doc_id?: string;
  assessment_year: string;
  entry_id: string;
  compare_group_id: string;
  display_name: string;
  question_prompt: string;
  help?: string | null;
  sort_order: number;
  input_kind: ReliefInputKind | string;
  auto_applied?: boolean;
  cap_amount?: string | null;
  unit?: "lkr" | "percent" | "text" | string;
  engine_binding?: ReliefEngineBinding;
  act_name: string;
  section_ref: string;
  quote: string;
  source_doc_id: string;
  needs_manual_verification?: boolean;
  eligibility_text?: string;
  eligibility_status?: string;
  eligibility_quote?: string;
  required_evidence?: string[];
  sub_items?: ReliefSubItem[];
  covers?: ReliefCovers | null;
  definitions?: ReliefDefinition[];
};

export type ReliefAnswer = {
  entry_id: string;
  compare_group_id: string;
  affirmed?: boolean;
  amount?: string;
  skipped?: boolean;
  /** Per-recipient amounts, keyed by `component_id`, for enumerated reliefs. */
  components?: Record<string, string>;
};

export type EmploymentInputMode = "components" | "total";
export type InvestmentInputMode = "components" | "total";
export type OtherInputMode = "components" | "total";
export type BusinessInputMode = "net" | "breakdown";

export type IncomeFormSlice = {
  employment_income: string;
  employment_final_withholding: string;
  business_income: string;
  business_gross: string;
  business_deductions: string;
  capital_allowances: string;
  investment_income: string;
  investment_final_withholding: string;
  other_income: string;
  other_final_withholding: string;
};

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

export type InterestScheduleLine = {
  id: string;
  label: string;
  interest: string;
  wht: string;
};

export type InterviewIncomeState = {
  taxpayerName: string;
  tin: string;
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
  interestSchedule: InterestScheduleLine[];
};

function sortAssessmentYears(years: string[]): string[] {
  return [...years].sort((a, b) => {
    const [aStart, aEnd = "0"] = a.split("_");
    const [bStart, bEnd = "0"] = b.split("_");
    const aKey = Number(aStart) * 100 + Number(aEnd);
    const bKey = Number(bStart) * 100 + Number(bEnd);
    return aKey - bKey;
  });
}

export function adjacentCompareYa(assessmentYear: string, availableYears?: string[]): string {
  const sorted = sortAssessmentYears(availableYears ?? []);
  if (!sorted.length) {
    if (assessmentYear === "2025_26") return "2024_25";
    return assessmentYear;
  }
  const idx = sorted.indexOf(assessmentYear);
  if (idx <= 0) return sorted[Math.min(1, sorted.length - 1)] ?? assessmentYear;
  return sorted[idx - 1] ?? assessmentYear;
}

export type InterviewSession = {
  assessmentYear: string;
  compareYear: string;
  excludeSourceDocId: string | null;
  selectedCompareGroupId: string | null;
  income: InterviewIncomeState;
  reliefAnswers: ReliefAnswer[];
  evidenceChecks: Record<string, Record<string, boolean>>;
};

export const SESSION_STORAGE_KEY = "optimization-explainable-engine.interview.v2";

function seedEmploymentAmounts(): Record<string, string> {
  const amounts = emptyAmountsForCard(incomeCatalogCard("employment"));
  amounts.emp_salary = "1600000";
  amounts.emp_bonus = "200000";
  return amounts;
}

export function hydrateIncomeAmounts(income: InterviewIncomeState): InterviewIncomeState {
  return {
    ...income,
    employmentAmounts: {
      ...emptyAmountsForCard(incomeCatalogCard("employment")),
      ...income.employmentAmounts,
    },
    businessAmounts: {
      ...emptyAmountsForCard(incomeCatalogCard("business")),
      ...income.businessAmounts,
    },
    investmentAmounts: {
      ...emptyAmountsForCard(incomeCatalogCard("investment")),
      ...income.investmentAmounts,
    },
    otherAmounts: {
      ...emptyAmountsForCard(incomeCatalogCard("other_income")),
      ...income.otherAmounts,
    },
  };
}

export function createDefaultSession(): InterviewSession {
  const assessmentYear = "2025_26";
  return {
    assessmentYear,
    compareYear: adjacentCompareYa(assessmentYear),
    excludeSourceDocId: null,
    selectedCompareGroupId: "personal_relief",
    income: hydrateIncomeAmounts({
      taxpayerName: "",
      tin: "",
      form: {
        ...EMPTY_INCOME_FORM,
        employment_income: "1800000",
      },
      employmentMode: "components",
      businessMode: "net",
      investmentMode: "components",
      otherMode: "components",
      employmentAmounts: seedEmploymentAmounts(),
      businessAmounts: {},
      investmentAmounts: {
        inv_interest: "2000000",
        inv_rents: "0",
        inv_dividends: "0",
      },
      otherAmounts: {},
      otherCustomRows: [],
      interestSchedule: [
        { id: "bank-1", label: "Bank interest", interest: "2000000", wht: "0" },
      ],
    }),
    reliefAnswers: [],
    evidenceChecks: {},
  };
}

export function hasSubItems(entry: ReliefEntry): boolean {
  return (entry.sub_items?.length ?? 0) > 0;
}

/** Combined claim for an enumerated relief: the sub-boxes added together. */
export function subItemTotalLkr(
  entry: ReliefEntry,
  components: Record<string, string>,
): number {
  return (entry.sub_items ?? []).reduce(
    (sum, item) => sum + parseLkr(components[item.component_id] ?? "0"),
    0,
  );
}

export function parseCap(raw: string | null | undefined): number | null {
  if (raw == null || raw === "") return null;
  const n = Number(String(raw).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

/**
 * Preview amount shown on a relief card. Driven by RAG `input_kind` / `unit` /
 * `engine_binding.kind` — not a per-relief TypeScript module.
 */
export function previewAppliedLkr(
  entry: ReliefEntry,
  income: InterviewIncomeState,
  claimLkr: number,
  affirmed: boolean,
): number {
  const cap = parseCap(entry.cap_amount);
  const kind = entry.engine_binding?.kind ?? "none";
  const inputKind = entry.input_kind;

  if (entry.unit === "percent" && cap != null) {
    if (
      (inputKind === "yes_no_amount" || inputKind === "boolean") &&
      !affirmed
    ) {
      return 0;
    }
    const base = kind === "rent_relief" ? rentsIncomeLkr(income) : totalIncomeLkr(income);
    return Math.floor((base * cap) / 100);
  }

  if (inputKind === "notice") {
    const base = incomeBaseForEntry(entry, income);
    if (cap == null) return 0;
    return Math.min(cap, base);
  }

  if (inputKind === "boolean") {
    if (!affirmed) return 0;
    if (cap == null) return 0;
    return Math.min(cap, incomeBaseForEntry(entry, income));
  }

  if (inputKind === "yes_no_amount") {
    if (!affirmed) return 0;
    if (kind === "senior_citizen_interest_relief") {
      const interest = interestIncomeLkr(income);
      return cap == null ? interest : Math.min(cap, interest);
    }
    if (cap == null) return claimLkr;
    return Math.min(cap, claimLkr);
  }

  if (cap == null) return claimLkr;
  return Math.min(cap, claimLkr);
}

function incomeBaseForEntry(entry: ReliefEntry, income: InterviewIncomeState): number {
  const kind = entry.engine_binding?.kind ?? "none";
  if (kind === "senior_citizen_interest_relief") return interestIncomeLkr(income);
  if (kind === "rent_relief") return rentsIncomeLkr(income);
  if (entry.compare_group_id === "employment_income_relief") {
    return employmentIncomeLkr(income);
  }
  return totalIncomeLkr(income);
}

export function incomeBaseLkr(
  entry: ReliefEntry,
  income: InterviewIncomeState,
): number {
  return incomeBaseForEntry(entry, income);
}
