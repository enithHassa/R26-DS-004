import type {
  CalculateTaxResponse,
  CalculationTraceStep,
  ComponentTraceItem,
} from "./api";
import { formatLkr } from "./format-lkr";
import {
  DEDUCTION_STEP_LABELS,
  INCOME_HEAD_KEYS,
  INCOME_HEAD_LABELS,
  INCOME_HEAD_SENTENCE,
  RELIEF_SENTENCE,
  assessmentYearLabel,
  type IncomeHeadKey,
} from "./taxpayer-labels";

export type BreakdownRowKind =
  | "income"
  | "deduction"
  | "subtotal"
  | "tax"
  | "credit"
  | "payable";

export type BreakdownRow = {
  kind: BreakdownRowKind;
  label: string;
  amount: string;
  note?: string;
  /** Optional quieter line (already human; no ids). */
  detail?: string;
};

export type TaxpayerSummaryView = {
  assessmentYearLabel: string;
  amountOwed: string;
  headline: string;
  explanation: string;
  rows: BreakdownRow[];
  whyParagraphs: string[];
};

function findStep(
  trace: CalculationTraceStep[],
  stepId: string,
): CalculationTraceStep | undefined {
  return trace.find((step) => step.step_id === stepId);
}

function parseMoney(value: string | null | undefined): number | null {
  if (value == null || value === "" || value === "null") return null;
  const n = parseFloat(String(value).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

function isPositiveMoney(value: string | null | undefined): boolean {
  const n = parseMoney(value);
  return n != null && n > 0;
}

function joinEnglish(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function ratePercent(rate: string | undefined): string | null {
  const n = parseFloat(rate ?? "");
  if (!Number.isFinite(n)) return null;
  return String(Math.round(n * 100));
}

export function cappedNote(
  claimed: string | undefined,
  allowed: string | undefined,
): string | undefined {
  const claimedN = parseMoney(claimed);
  const allowedN = parseMoney(allowed);
  if (claimedN != null && allowedN != null && claimedN > allowedN) {
    return "capped, see note";
  }
  return undefined;
}

function resolveAssessmentYear(
  assessmentYear: string | null | undefined,
  result: CalculateTaxResponse,
): string {
  if (assessmentYear === "2024_25" || assessmentYear === "2025_26") {
    return assessmentYear;
  }
  const pack = result.knowledge_versions?.rule_pack_version ?? "";
  if (pack.startsWith("2025_26")) return "2025_26";
  if (pack.startsWith("2024_25")) return "2024_25";
  return assessmentYear || "";
}

function employmentLabel(componentTrace: ComponentTraceItem[] | undefined): string {
  const base = INCOME_HEAD_LABELS.employment_income;
  const names = (componentTrace ?? [])
    .filter(
      (row) =>
        row.card_id === "employment" &&
        row.treatment_applied === "include" &&
        row.display_name,
    )
    .map((row) => row.display_name.trim().toLowerCase())
    .filter(Boolean);
  if (names.length === 0) return base;
  return `${base} (${names.join(", ")})`;
}

/** Smaller of two wire amounts, without reformatting. */
function minMoneyWire(
  left: string | undefined,
  right: string | undefined,
): string | undefined {
  const leftN = parseMoney(left);
  const rightN = parseMoney(right);
  if (leftN == null) return right;
  if (rightN == null) return left;
  return leftN <= rightN ? left : right;
}

function isResident(step: CalculationTraceStep | undefined): boolean {
  return step?.inputs.resident_status === "resident";
}

/** Why / one-liner: resident flag AND statutory personal_relief > 0 (not deducted). */
export function mentionPersonalRelief(step: CalculationTraceStep | undefined): boolean {
  return isResident(step) && isPositiveMoney(step?.inputs.personal_relief);
}

export function buildTaxpayerSummary(
  result: CalculateTaxResponse,
  assessmentYear?: string | null,
): TaxpayerSummaryView {
  const trace = result.calculation_trace ?? [];
  const yearKey = resolveAssessmentYear(assessmentYear, result);
  const yearLabel = assessmentYearLabel(yearKey);
  const amountOwed = result.tax_payable_lkr ?? result.final_tax_lkr;
  const owedN = parseMoney(amountOwed);

  const headline =
    owedN === 0
      ? `You owe no income tax for assessment year ${yearLabel}.`
      : `You owe ${formatLkr(amountOwed)} in income tax for assessment year ${yearLabel}.`;

  const sumAssessable = findStep(trace, "sum_assessable");
  const sumInputs = sumAssessable?.inputs ?? {};

  const qp = findStep(trace, "deduct_qualifying_payment");
  const solar = findStep(trace, "deduct_solar_panel_relief");
  const solarCap = findStep(trace, "cap_solar_panel_relief");
  const rent = findStep(trace, "deduct_rent_relief");
  const rentCap = findStep(trace, "cap_rent_relief");
  const senior = findStep(trace, "deduct_senior_citizen_interest_relief");
  const seniorCap = findStep(trace, "cap_senior_citizen_interest_relief");
  const personal = findStep(trace, "apply_personal_relief");
  const credit = findStep(trace, "apply_tax_credit");
  const finalTax = findStep(trace, "final_tax");
  const mentionPersonal = mentionPersonalRelief(personal);
  const deductedWire = minMoneyWire(
    personal?.inputs.personal_relief,
    personal?.inputs.after_deductions,
  );
  const showPersonalRow = mentionPersonal && isPositiveMoney(deductedWire);

  const rows: BreakdownRow[] = [];

  for (const key of INCOME_HEAD_KEYS) {
    const amount = sumInputs[key];
    if (!isPositiveMoney(amount)) continue;
    const label: string =
      key === "employment_income"
        ? employmentLabel(result.component_trace)
        : INCOME_HEAD_LABELS[key as IncomeHeadKey];
    rows.push({ kind: "income", label, amount });
  }

  if (qp && isPositiveMoney(qp.inputs.allowed)) {
    rows.push({
      kind: "deduction",
      label: DEDUCTION_STEP_LABELS.deduct_qualifying_payment,
      amount: qp.inputs.allowed,
      note: cappedNote(qp.inputs.claimed, qp.inputs.allowed),
    });
  }

  if (solar && isPositiveMoney(solar.inputs.allowed)) {
    rows.push({
      kind: "deduction",
      label: DEDUCTION_STEP_LABELS.deduct_solar_panel_relief,
      amount: solar.inputs.allowed,
      note: cappedNote(
        solarCap?.inputs.claimed ?? solar.inputs.claimed,
        solarCap?.inputs.allowed ?? solar.inputs.allowed,
      ),
    });
  }

  if (rent && isPositiveMoney(rent.inputs.allowed)) {
    rows.push({
      kind: "deduction",
      label: DEDUCTION_STEP_LABELS.deduct_rent_relief,
      amount: rent.inputs.allowed,
      note: cappedNote(
        rentCap?.inputs.claimed ?? rent.inputs.claimed,
        rentCap?.inputs.allowed ?? rent.inputs.allowed,
      ),
    });
  }

  if (senior && isPositiveMoney(senior.inputs.allowed)) {
    rows.push({
      kind: "deduction",
      label: DEDUCTION_STEP_LABELS.deduct_senior_citizen_interest_relief,
      amount: senior.inputs.allowed,
      note: cappedNote(
        seniorCap?.inputs.claimed ?? senior.inputs.claimed,
        seniorCap?.inputs.allowed ?? senior.inputs.allowed,
      ),
    });
  }

  if (showPersonalRow && personal && deductedWire) {
    const statutory = parseMoney(personal.inputs.personal_relief);
    const after = parseMoney(personal.inputs.after_deductions);
    const limited =
      statutory != null && after != null && after < statutory
        ? "limited to remaining income"
        : undefined;
    rows.push({
      kind: "deduction",
      label: DEDUCTION_STEP_LABELS.apply_personal_relief,
      amount: deductedWire,
      note: limited,
    });
  }

  const taxable =
    personal?.output ?? finalTax?.inputs.taxable_income ?? "0";
  rows.push({
    kind: "subtotal",
    label: "Taxable income",
    amount: taxable,
  });

  const slabSteps = trace.filter(
    (step) =>
      /^slab_band_\d+$/.test(step.step_id) &&
      isPositiveMoney(step.inputs.taxable_in_slice),
  );
  for (const slab of slabSteps) {
    const percent = ratePercent(slab.inputs.rate);
    rows.push({
      kind: "tax",
      label:
        percent != null
          ? `Tax on taxable income (${percent}% band)`
          : "Tax on taxable income",
      amount: slab.output,
      detail: slab.description || undefined,
    });
  }

  if (credit && isPositiveMoney(credit.inputs.credits_applied)) {
    rows.push({
      kind: "credit",
      label: DEDUCTION_STEP_LABELS.apply_tax_credit,
      amount: credit.inputs.credits_applied,
    });
  }

  rows.push({
    kind: "payable",
    label: "Tax payable",
    amount: amountOwed,
  });

  const incomeNames = INCOME_HEAD_KEYS.filter((key) =>
    isPositiveMoney(sumInputs[key]),
  ).map((key) => INCOME_HEAD_SENTENCE[key]);

  const reliefNames: string[] = [];
  if (qp && isPositiveMoney(qp.inputs.allowed)) {
    reliefNames.push(RELIEF_SENTENCE.deduct_qualifying_payment);
  }
  if (solar && isPositiveMoney(solar.inputs.allowed)) {
    reliefNames.push(RELIEF_SENTENCE.deduct_solar_panel_relief);
  }
  if (rent && isPositiveMoney(rent.inputs.allowed)) {
    reliefNames.push(RELIEF_SENTENCE.deduct_rent_relief);
  }
  if (senior && isPositiveMoney(senior.inputs.allowed)) {
    reliefNames.push(RELIEF_SENTENCE.deduct_senior_citizen_interest_relief);
  }
  if (mentionPersonal) {
    reliefNames.push(RELIEF_SENTENCE.apply_personal_relief);
  }

  let explanation: string;
  if (incomeNames.length > 0 && reliefNames.length > 0) {
    explanation = `This is based on your ${joinEnglish(incomeNames)} after applying your ${joinEnglish(reliefNames)}.`;
  } else if (incomeNames.length > 0) {
    explanation = `This is based on your ${joinEnglish(incomeNames)} for this year.`;
  } else {
    explanation = "This is based on the amounts you entered for this year.";
  }

  const whyParagraphs: string[] = [];

  if (solarCap) {
    const capAmt = solarCap.inputs.cap;
    if (isPositiveMoney(capAmt) || parseMoney(capAmt) === 0) {
      whyParagraphs.push(
        `Solar panel relief is capped at ${formatLkr(capAmt)} under the Fifth Schedule.`,
      );
    }
    const claimed = solarCap.inputs.claimed ?? solar?.inputs.claimed;
    const allowed = solarCap.inputs.allowed ?? solar?.inputs.allowed;
    if (cappedNote(claimed, allowed) && claimed && allowed) {
      whyParagraphs.push(
        `Only ${formatLkr(allowed)} of ${formatLkr(claimed)} claimed was allowed.`,
      );
    }
  }

  if (mentionPersonal && personal) {
    whyParagraphs.push(
      `Personal relief for residents is ${formatLkr(personal.inputs.personal_relief)} for this year.`,
    );
  }

  if (rentCap) {
    const ceiling = rentCap.inputs.ceiling ?? rentCap.inputs.allowed;
    whyParagraphs.push(
      `Rent relief is limited to 25% of included rental income under the Fifth Schedule${
        isPositiveMoney(ceiling) ? ` (${formatLkr(ceiling)} this year)` : ""
      }.`,
    );
  }

  if (slabSteps.length === 1) {
    const percent = ratePercent(slabSteps[0].inputs.rate);
    if (percent != null) {
      whyParagraphs.push(
        `Tax on that taxable income is charged at ${percent}% (first band of the First Schedule).`,
      );
    }
  } else if (slabSteps.length > 1) {
    const percent = ratePercent(slabSteps[0].inputs.rate);
    if (percent != null) {
      whyParagraphs.push(
        `Tax is charged in bands under the First Schedule, starting at ${percent}%.`,
      );
    }
  }

  return {
    assessmentYearLabel: yearLabel,
    amountOwed,
    headline,
    explanation,
    rows,
    whyParagraphs: whyParagraphs.slice(0, 3),
  };
}
