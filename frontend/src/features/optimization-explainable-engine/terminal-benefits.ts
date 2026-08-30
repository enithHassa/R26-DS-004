import { parseLkr } from "./format-lkr";
import type { TerminalBenefitPeriod, TerminalBenefitRow, TerminalBenefitType } from "./types";

export const TERMINAL_BENEFIT_TYPE_OPTIONS: {
  value: Exclude<TerminalBenefitType, "">;
  label: string;
}[] = [
  { value: "commuted_pension", label: "Commuted pension" },
  { value: "retiring_gratuity", label: "Retiring gratuity" },
  { value: "loss_of_office_compensation", label: "Compensation for loss of office" },
  { value: "etf_retirement_payment", label: "ETF at or after retirement" },
];

export type TerminalBenefitPayloadItem = {
  type: Exclude<TerminalBenefitType, "">;
  amount: number;
  employment_period_over_20_years?: boolean;
  loss_of_office_scheme_approved?: boolean;
  terminal_benefit_period?: TerminalBenefitPeriod;
};

type LegacyTerminalScalars = {
  terminalBenefitType?: TerminalBenefitType;
  terminalBenefitAmount?: string;
  employmentPeriodOver20Years?: boolean;
  lossOfOfficeSchemeApproved?: boolean;
  terminalBenefitPeriod?: TerminalBenefitPeriod;
  hasTerminalBenefits?: boolean;
  terminalBenefits?: TerminalBenefitRow[];
};

export function newTerminalBenefitRow(): TerminalBenefitRow {
  return {
    id: `tb-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type: "",
    amount: "0",
    employmentPeriodOver20Years: false,
    lossOfOfficeSchemeApproved: false,
    terminalBenefitPeriod: "",
  };
}

export function terminalBenefitLabel(type: string | null | undefined): string {
  const found = TERMINAL_BENEFIT_TYPE_OPTIONS.find((option) => option.value === type);
  return found?.label ?? type ?? "Terminal benefit";
}

export function showsTerminalPeriod(assessmentYear: string): boolean {
  return assessmentYear === "2019_20";
}

export function showsEmploymentPeriodQuestion(
  assessmentYear: string,
  period: TerminalBenefitPeriod,
): boolean {
  return (
    assessmentYear === "2018_19" ||
    (assessmentYear === "2019_20" && period === "pre_2020")
  );
}

export function hydrateTerminalBenefits(income: LegacyTerminalScalars): {
  hasTerminalBenefits: boolean;
  terminalBenefits: TerminalBenefitRow[];
} {
  if (Array.isArray(income.terminalBenefits)) {
    const rows = income.terminalBenefits.map((row) => ({
      id: row.id || newTerminalBenefitRow().id,
      type: row.type ?? "",
      amount: row.amount ?? "0",
      employmentPeriodOver20Years: Boolean(row.employmentPeriodOver20Years),
      lossOfOfficeSchemeApproved: Boolean(row.lossOfOfficeSchemeApproved),
      terminalBenefitPeriod: row.terminalBenefitPeriod ?? "",
    }));
    return {
      hasTerminalBenefits: Boolean(income.hasTerminalBenefits) && rows.length > 0,
      terminalBenefits: rows,
    };
  }
  const type = income.terminalBenefitType ?? "";
  const amount = income.terminalBenefitAmount ?? "0";
  if (type || parseLkr(amount) > 0) {
    return {
      hasTerminalBenefits: true,
      terminalBenefits: [
        {
          id: "legacy-terminal",
          type,
          amount,
          employmentPeriodOver20Years: Boolean(income.employmentPeriodOver20Years),
          lossOfOfficeSchemeApproved: Boolean(income.lossOfOfficeSchemeApproved),
          terminalBenefitPeriod: income.terminalBenefitPeriod ?? "",
        },
      ],
    };
  }
  return { hasTerminalBenefits: false, terminalBenefits: [] };
}

export function terminalBenefitsTotalLkr(rows: TerminalBenefitRow[] | undefined): number {
  return (rows ?? []).reduce((sum, row) => sum + parseLkr(row.amount), 0);
}

export function isTerminalBenefitRowComplete(
  row: TerminalBenefitRow,
  assessmentYear: string,
): boolean {
  if (!row.type) return false;
  if (parseLkr(row.amount) <= 0) return false;
  if (showsTerminalPeriod(assessmentYear) && !row.terminalBenefitPeriod) return false;
  if (row.type === "loss_of_office_compensation" && !row.lossOfOfficeSchemeApproved) {
    return false;
  }
  return true;
}

export function terminalBenefitsBlockContinue(
  hasTerminalBenefits: boolean,
  rows: TerminalBenefitRow[] | undefined,
  assessmentYear: string,
): boolean {
  if (!hasTerminalBenefits) return false;
  const list = rows ?? [];
  if (list.length === 0) return true;
  return list.some((row) => !isTerminalBenefitRowComplete(row, assessmentYear));
}

export function unusedTerminalBenefitTypes(
  rows: TerminalBenefitRow[],
  currentId: string,
): Exclude<TerminalBenefitType, "">[] {
  const taken = new Set(
    rows.filter((row) => row.id !== currentId && row.type).map((row) => row.type),
  );
  return TERMINAL_BENEFIT_TYPE_OPTIONS.map((option) => option.value).filter(
    (value) => !taken.has(value),
  );
}

export function buildTerminalBenefitsPayload(
  hasTerminalBenefits: boolean,
  rows: TerminalBenefitRow[] | undefined,
  assessmentYear: string,
): TerminalBenefitPayloadItem[] {
  if (!hasTerminalBenefits) return [];
  const items: TerminalBenefitPayloadItem[] = [];
  for (const row of rows ?? []) {
    if (!isTerminalBenefitRowComplete(row, assessmentYear) || !row.type) continue;
    const item: TerminalBenefitPayloadItem = {
      type: row.type,
      amount: parseLkr(row.amount),
    };
    if (showsTerminalPeriod(assessmentYear)) {
      item.terminal_benefit_period = row.terminalBenefitPeriod;
    }
    if (showsEmploymentPeriodQuestion(assessmentYear, row.terminalBenefitPeriod)) {
      item.employment_period_over_20_years = row.employmentPeriodOver20Years;
    }
    if (row.type === "loss_of_office_compensation") {
      item.loss_of_office_scheme_approved = row.lossOfOfficeSchemeApproved;
    }
    items.push(item);
  }
  return items;
}
