/** Display-only maps. Internal step / concept IDs are not renamed. */

export const ASSESSMENT_YEAR_LABELS = {
  "2024_25": "2024/25",
  "2025_26": "2025/26",
} as const;

export type AssessmentYearKey = keyof typeof ASSESSMENT_YEAR_LABELS;

/** Closed allowlist — do not iterate every `sum_assessable.inputs` key (skips `provenance`). */
export const INCOME_HEAD_KEYS = [
  "employment_income",
  "business_income",
  "investment_income",
  "other_income",
] as const;

export type IncomeHeadKey = (typeof INCOME_HEAD_KEYS)[number];

export const INCOME_HEAD_LABELS: Record<IncomeHeadKey, string> = {
  employment_income: "Employment income",
  business_income: "Business income",
  investment_income: "Investment income",
  other_income: "Other income",
};

/** Lowercase fragments for the one-sentence explanation. */
export const INCOME_HEAD_SENTENCE: Record<IncomeHeadKey, string> = {
  employment_income: "employment income",
  business_income: "business income",
  investment_income: "investment income",
  other_income: "other income",
};

export const DEDUCTION_STEP_LABELS: Record<string, string> = {
  deduct_qualifying_payment: "Qualifying payments",
  deduct_solar_panel_relief: "Solar panel relief",
  deduct_rent_relief: "Rent relief",
  apply_personal_relief: "Personal relief",
  apply_tax_credit: "Tax already paid (APIT)",
};

export const RELIEF_SENTENCE: Record<string, string> = {
  deduct_qualifying_payment: "qualifying payments",
  deduct_solar_panel_relief: "solar panel relief",
  deduct_rent_relief: "rent relief",
  apply_personal_relief: "personal relief",
};

/** Closed map — report-facing step_id → human label (reuses strings above). */
export const STEP_LABELS: Record<string, string> = {
  aggregate_employment_components: INCOME_HEAD_LABELS.employment_income,
  exclude_employment_exempt_lines: "Employment excluded",
  exclude_employment_final_withholding: "Employment final withholding",
  aggregate_business_components: INCOME_HEAD_LABELS.business_income,
  compute_business_net: INCOME_HEAD_LABELS.business_income,
  aggregate_investment_components: INCOME_HEAD_LABELS.investment_income,
  exclude_investment_final_withholding: "Investment final withholding",
  aggregate_other_income_components: INCOME_HEAD_LABELS.other_income,
  exclude_other_final_withholding: "Other income final withholding",
  sum_assessable: "Assessable income",
  aggregate_qualifying_payment_components: "Qualifying payments claimed",
  cap_qualifying_payment_cap: DEDUCTION_STEP_LABELS.deduct_qualifying_payment,
  deduct_qualifying_payment: DEDUCTION_STEP_LABELS.deduct_qualifying_payment,
  apply_qualifying_payment_brought_forward: "Qualifying payments brought forward",
  carry_forward_qualifying_payment_out: "Qualifying payments carried forward",
  cap_solar_panel_relief: DEDUCTION_STEP_LABELS.deduct_solar_panel_relief,
  deduct_solar_panel_relief: DEDUCTION_STEP_LABELS.deduct_solar_panel_relief,
  cap_rent_relief: DEDUCTION_STEP_LABELS.deduct_rent_relief,
  deduct_rent_relief: DEDUCTION_STEP_LABELS.deduct_rent_relief,
  apply_personal_relief: DEDUCTION_STEP_LABELS.apply_personal_relief,
  apply_tax_credit: DEDUCTION_STEP_LABELS.apply_tax_credit,
  final_tax: "Income tax",
};

/** Seeded from live explain data only — do not guess catalog suffixes. */
export const QP_CATEGORY_LABELS: Record<string, string> = {
  qp_approved_charitable: "Approved charitable donation",
};

/** Unresolved-claim concept_id → phrase used in banner copy. */
export const CLAIM_CONCEPT_LABELS: Record<string, string> = {
  solar_panel_relief: RELIEF_SENTENCE.deduct_solar_panel_relief,
  qualifying_payment: RELIEF_SENTENCE.deduct_qualifying_payment,
  qualifying_payment_cap: RELIEF_SENTENCE.deduct_qualifying_payment,
  rent_relief: RELIEF_SENTENCE.deduct_rent_relief,
};

export const SOURCE_DOC_LABELS: Record<string, string> = {
  "ird-ira-2017-base": "Inland Revenue Act No. 24 of 2017",
  "ird-amend-2021-10": "Act No. 10 of 2021",
  "ird-amend-2022-45": "Act No. 45 of 2022",
  "ird-amend-2025-02": "Act No. 02 of 2025",
  "ird-amend-2026-11": "Act No. 11 of 2026",
  "ird-consolidated-2025": "Inland Revenue Act (consolidated 2025)",
};

const QP_CATEGORY_PREFIX = "qp_category:";

export function stepLabel(stepId: string): string | null {
  if (STEP_LABELS[stepId]) return STEP_LABELS[stepId];
  if (/^slab_band_\d+$/.test(stepId)) return "Tax on taxable income";
  if (stepId.startsWith(QP_CATEGORY_PREFIX)) {
    const suffix = stepId.slice(QP_CATEGORY_PREFIX.length);
    return QP_CATEGORY_LABELS[suffix] ?? null;
  }
  return null;
}

/** Plain Act title for graph-delta sentences. Null = omit the source name (never print a raw id). */
export function sourceDocPlainName(sourceDocId: string | null | undefined): string | null {
  if (!sourceDocId) return null;
  if (SOURCE_DOC_LABELS[sourceDocId]) return SOURCE_DOC_LABELS[sourceDocId];
  if (sourceDocId.startsWith("ird-")) {
    const rest = sourceDocId.slice(4).replace(/-/g, " ").trim();
    if (!rest) return null;
    return rest.replace(/\b\w/g, (ch) => ch.toUpperCase());
  }
  return null;
}

export function assessmentYearLabel(year: string | null | undefined): string {
  if (year === "2024_25" || year === "2025_26") {
    return ASSESSMENT_YEAR_LABELS[year];
  }
  return year || "this year";
}
