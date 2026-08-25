/**
 * Dev-only QA helpers for the Adaptive Tax calculator form.
 * Fill always switches cards to detailed/components mode and populates
 * a rich worked example (~75% of fields per card) for manual QA demos.
 */

export type TestDataResidentStatus = "resident" | "non_resident";

export type CalculatorTestDataContext = {
  resident_status: TestDataResidentStatus;
  employmentFieldIds: string[];
  businessFieldIds: string[];
  investmentFieldIds: string[];
  otherFieldIds: string[];
  qpFieldIds: string[];
  statutoryFieldIds: string[];
  creditFieldIds: string[];
};

export type CalculatorTestDataFillPatch = {
  modes: {
    employmentMode: "components";
    businessInputMode: "breakdown";
    investmentMode: "components";
    otherMode: "components";
    qpMode: "components";
    creditMode: "components";
  };
  employmentAmounts: Record<string, string>;
  businessAmounts: Record<string, string>;
  investmentAmounts: Record<string, string>;
  otherAmounts: Record<string, string>;
  qpAmounts: Record<string, string>;
  statutoryAmounts: Record<string, string>;
  creditAmounts: Record<string, string>;
};

export type CalculatorTestDataClearPatch = {
  formScalars: {
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
    qualifying_payments: string;
    apit_already_paid: string;
  };
  employmentAmounts: Record<string, string>;
  businessAmounts: Record<string, string>;
  investmentAmounts: Record<string, string>;
  otherAmounts: Record<string, string>;
  qpAmounts: Record<string, string>;
  statutoryAmounts: Record<string, string>;
  creditAmounts: Record<string, string>;
  otherCustomRows: [];
};

/** Catalog warns inv_rents ↔ inv_final_withholding are mutually exclusive ("not also here"). */
const INVESTMENT_MUTUAL_EXCLUSION = new Set(["inv_rents", "inv_final_withholding"]);

type FieldFill = { id: string; value: string };

function setIfPresent(
  target: Record<string, string>,
  fieldIds: string[],
  componentId: string,
  value: string,
): void {
  if (fieldIds.includes(componentId)) {
    target[componentId] = value;
  }
}

function fillManyIfPresent(
  target: Record<string, string>,
  fieldIds: string[],
  entries: FieldFill[],
): void {
  for (const { id, value } of entries) {
    setIfPresent(target, fieldIds, id, value);
  }
}

function zeroAll(fieldIds: string[]): Record<string, string> {
  const next: Record<string, string> = {};
  for (const id of fieldIds) {
    next[id] = "0";
  }
  return next;
}

export function buildFillTestDataPatch(
  ctx: CalculatorTestDataContext,
): CalculatorTestDataFillPatch {
  const employmentAmounts: Record<string, string> = {};
  fillManyIfPresent(employmentAmounts, ctx.employmentFieldIds, [
    { id: "emp_salary", value: "1500000" },
    { id: "emp_bonus", value: "300000" },
    { id: "emp_overtime", value: "100000" },
    { id: "emp_commission", value: "80000" },
    { id: "emp_wages", value: "50000" },
    { id: "emp_pension", value: "120000" },
    { id: "emp_housing_allowance", value: "60000" },
    { id: "emp_travel_allowance", value: "40000" },
    { id: "emp_cost_of_living_allowance", value: "35000" },
    { id: "emp_entertainment_allowance", value: "25000" },
    { id: "emp_employee_share_scheme", value: "90000" },
    { id: "emp_other_employment_benefits", value: "20000" },
  ]);
  // Intentionally left at 0: emp_gratuity, emp_leave_pay, emp_gifts.
  // Do not fill emp_final_withholding (exclusion line).

  const businessAmounts: Record<string, string> = {};
  fillManyIfPresent(businessAmounts, ctx.businessFieldIds, [
    { id: "biz_gross", value: "1200000" },
    { id: "biz_deductions", value: "400000" },
    { id: "biz_capital_allowances", value: "100000" },
  ]);

  const investmentAmounts: Record<string, string> = {};
  fillManyIfPresent(investmentAmounts, ctx.investmentFieldIds, [
    { id: "inv_dividends", value: "250000" },
    { id: "inv_interest", value: "150000" },
    { id: "inv_royalties", value: "80000" },
    { id: "inv_annuities", value: "60000" },
    { id: "inv_premiums", value: "45000" },
    { id: "inv_gains_investment_assets", value: "120000" },
    { id: "inv_discounts", value: "35000" },
    { id: "inv_charges", value: "25000" },
    { id: "inv_natural_resource_payments", value: "55000" },
    { id: "inv_other_amounts", value: "40000" },
  ]);

  const otherAmounts: Record<string, string> = {};
  setIfPresent(otherAmounts, ctx.otherFieldIds, "oth_residual", "200000");

  const qpAmounts: Record<string, string> = {};
  fillManyIfPresent(qpAmounts, ctx.qpFieldIds, [
    { id: "qp_approved_charitable", value: "75000" },
    { id: "qp_government_sri_lanka", value: "300000" },
    { id: "qp_local_authority", value: "150000" },
  ]);

  const statutoryAmounts: Record<string, string> = {};
  if (ctx.resident_status === "resident") {
    // Above Rs 600,000 cap — triggers "capped, see note" in the estimate UI.
    setIfPresent(statutoryAmounts, ctx.statutoryFieldIds, "relief_solar_panel", "650000");
  } else {
    // Rent allowed = min(claimed, floor(0.25 × inv_rents)); inv_rents is unfilled
    // (mutual-exclusion guard), so cap note will not appear on non-resident fills.
    setIfPresent(statutoryAmounts, ctx.statutoryFieldIds, "relief_rent", "200000");
  }

  const creditAmounts: Record<string, string> = {};
  setIfPresent(creditAmounts, ctx.creditFieldIds, "credit_apit", "150000");

  // Guard: never accidentally fill mutual-exclusion investment pair.
  for (const id of INVESTMENT_MUTUAL_EXCLUSION) {
    delete investmentAmounts[id];
  }

  return {
    modes: {
      employmentMode: "components",
      businessInputMode: "breakdown",
      investmentMode: "components",
      otherMode: "components",
      qpMode: "components",
      creditMode: "components",
    },
    employmentAmounts,
    businessAmounts,
    investmentAmounts,
    otherAmounts,
    qpAmounts,
    statutoryAmounts,
    creditAmounts,
  };
}

export function buildClearTestDataPatch(
  ctx: CalculatorTestDataContext,
): CalculatorTestDataClearPatch {
  return {
    formScalars: {
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
      qualifying_payments: "0",
      apit_already_paid: "0",
    },
    employmentAmounts: zeroAll(ctx.employmentFieldIds),
    businessAmounts: zeroAll(ctx.businessFieldIds),
    investmentAmounts: zeroAll(ctx.investmentFieldIds),
    otherAmounts: zeroAll(ctx.otherFieldIds),
    qpAmounts: zeroAll(ctx.qpFieldIds),
    statutoryAmounts: zeroAll(ctx.statutoryFieldIds),
    creditAmounts: zeroAll(ctx.creditFieldIds),
    otherCustomRows: [],
  };
}
