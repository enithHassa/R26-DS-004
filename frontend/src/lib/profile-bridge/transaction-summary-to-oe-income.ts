import type { TaxableIncomeLineItem } from "@/features/transaction-semantic/api";
import type {
  InterestScheduleLine,
  InterviewIncomeState,
} from "@/features/optimization-explainable-engine/types";

const COMP1_BANK_INTEREST_LINE_ID = "comp1-bank-interest";
/** Default interview seed line — replaced when Comp 1 supplies bank interest. */
const DEFAULT_SEED_INTEREST_LINE_ID = "bank-1";

export type MergeBreakdownMode = "replace" | "add";

function num(raw: number | string | undefined | null): number {
  if (raw == null) return 0;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) ? n : 0;
}

function amountStr(value: number): string {
  return value > 0 ? String(Math.round(value)) : "0";
}

function addAmount(current: string, delta: number): string {
  return amountStr(num(current) + delta);
}

function setAmount(_current: string, value: number): string {
  return amountStr(value);
}

type FieldTarget =
  | { bucket: "employment"; id: string }
  | { bucket: "business"; id: string }
  | { bucket: "investment"; id: string }
  | { bucket: "other"; id: string }
  | { bucket: "interest" };

function targetForClassKey(classKey: string): FieldTarget {
  switch (classKey) {
    case "employment_income":
      return { bucket: "employment", id: "emp_salary" };
    case "bonus_performance":
      return { bucket: "employment", id: "emp_bonus" };
    case "gratuity":
      return { bucket: "employment", id: "emp_gratuity" };
    case "freelance_service":
    case "business_profit":
      return { bucket: "business", id: "biz_net_profits" };
    case "interest_income":
      return { bucket: "interest" };
    case "dividend_income":
      return { bucket: "investment", id: "inv_dividends" };
    case "rental_income":
      return { bucket: "investment", id: "inv_rents" };
    case "capital_gain":
      return { bucket: "investment", id: "inv_gains_investment_assets" };
    default:
      return { bucket: "other", id: "oth_residual" };
  }
}

function applyToRecord(
  record: Record<string, string>,
  id: string,
  amount: number,
  mode: MergeBreakdownMode,
): void {
  record[id] = mode === "replace" ? setAmount(record[id] ?? "0", amount) : addAmount(record[id] ?? "0", amount);
}

/**
 * Keep the WHT schedule in sync with Comp 1 bank interest so OE totals and the
 * Interest schedule UI match `inv_interest` (schedule wins when non-empty).
 */
function syncInterestSchedule(
  schedule: InterestScheduleLine[],
  interestAmount: number,
  mode: MergeBreakdownMode,
): InterestScheduleLine[] {
  const rounded = Math.round(interestAmount);
  if (rounded <= 0) {
    return schedule;
  }

  const preservedWht =
    schedule.find((line) => line.id === COMP1_BANK_INTEREST_LINE_ID)?.wht ??
    schedule.find((line) => line.id === DEFAULT_SEED_INTEREST_LINE_ID)?.wht ??
    "0";

  const others = schedule.filter(
    (line) =>
      line.id !== COMP1_BANK_INTEREST_LINE_ID &&
      line.id !== DEFAULT_SEED_INTEREST_LINE_ID,
  );

  if (mode === "add") {
    const existing = schedule.find((line) => line.id === COMP1_BANK_INTEREST_LINE_ID);
    const nextInterest = Math.round(num(existing?.interest) + rounded);
    const bankLine: InterestScheduleLine = {
      id: COMP1_BANK_INTEREST_LINE_ID,
      label: "Bank interest (classified)",
      interest: amountStr(nextInterest),
      wht: existing?.wht ?? preservedWht,
    };
    return [
      ...others.filter((line) => line.id !== COMP1_BANK_INTEREST_LINE_ID),
      bankLine,
    ];
  }

  return [
    ...others,
    {
      id: COMP1_BANK_INTEREST_LINE_ID,
      label: "Bank interest (classified)",
      interest: amountStr(rounded),
      wht: preservedWht,
    },
  ];
}

/**
 * Merge Comp 1 taxable income buckets into OE interview income.
 *
 * - Default `replace`: bank taxable amounts become the source of truth for each
 *   mapped field present in the breakdown (avoids stacking on demo seed values).
 * - `add`: layer bank evidence on existing profile/interview totals.
 * - Interest updates both `inv_interest` and the WHT schedule line OE uses in UI/Result.
 * - Zero / non-taxable amounts are skipped (Comp 1 AIT-exempt interest stays out).
 */
export function mergeBreakdownIntoIncome(
  income: InterviewIncomeState,
  lines: { classKey: string; amount: number }[],
  mode: MergeBreakdownMode = "replace",
): InterviewIncomeState {
  const asApiLines = lines
    .filter((line) => Number.isFinite(line.amount) && line.amount > 0)
    .map((line) => ({
      class_key: line.classKey,
      tax_rule_code: null,
      taxability_status: "taxable" as const,
      transaction_count: 0,
      gross_amount_lkr: String(line.amount),
      taxable_amount_lkr: String(line.amount),
    }));
  return mergeTaxableSummaryIntoIncome(income, asApiLines, mode);
}

export function mergeTaxableSummaryIntoIncome(
  income: InterviewIncomeState,
  lines: TaxableIncomeLineItem[],
  mode: MergeBreakdownMode = "replace",
): InterviewIncomeState {
  const employment = { ...income.employmentAmounts };
  const business = { ...income.businessAmounts };
  const investment = { ...income.investmentAmounts };
  const other = { ...income.otherAmounts };
  let interestSchedule = [...(income.interestSchedule ?? [])];

  // Sum by class first so replace mode does not clobber duplicate months/docs.
  const byClass = new Map<string, number>();
  for (const line of lines) {
    const amount = num(line.taxable_amount_lkr);
    if (amount <= 0) continue;
    byClass.set(line.class_key, (byClass.get(line.class_key) ?? 0) + amount);
  }

  // Collapse class keys that share one OE field before replace.
  const fieldTotals = new Map<string, { target: FieldTarget; amount: number }>();
  for (const [classKey, amount] of byClass) {
    const target = targetForClassKey(classKey);
    const key =
      target.bucket === "interest"
        ? "interest"
        : `${target.bucket}:${target.id}`;
    const existing = fieldTotals.get(key);
    if (existing) {
      existing.amount += amount;
    } else {
      fieldTotals.set(key, { target, amount });
    }
  }

  for (const { target, amount } of fieldTotals.values()) {
    if (target.bucket === "interest") {
      applyToRecord(investment, "inv_interest", amount, mode);
      interestSchedule = syncInterestSchedule(interestSchedule, amount, mode);
      continue;
    }
    if (target.bucket === "employment") {
      applyToRecord(employment, target.id, amount, mode);
    } else if (target.bucket === "business") {
      applyToRecord(business, target.id, amount, mode);
    } else if (target.bucket === "investment") {
      applyToRecord(investment, target.id, amount, mode);
    } else {
      applyToRecord(other, target.id, amount, mode);
    }
  }

  return {
    ...income,
    employmentMode: "components",
    businessMode: num(business.biz_net_profits) > 0 ? "net" : income.businessMode,
    investmentMode: "components",
    otherMode: "components",
    employmentAmounts: employment,
    businessAmounts: business,
    investmentAmounts: investment,
    otherAmounts: other,
    interestSchedule,
  };
}
