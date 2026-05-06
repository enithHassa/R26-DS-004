/** Mirrors backend `TaxOptBProfileV1` / strategy / compliance response (Function 1). */

export type TaxOptBEmploymentTypeV1 =
  | "employee"
  | "self_employed"
  | "business_owner"
  | "other";

export interface TaxOptBProfileV1 {
  tax_year: string;
  employment_type: TaxOptBEmploymentTypeV1;
  dependents: number;
  annual_gross_income: string;
  estimated_annual_taxable_income?: string | null;
}

export interface TaxOptBReliefClaimV1 {
  relief_code: string;
  claimed_amount_annual: string | number;
}

export interface TaxOptBStrategyProposalV1 {
  claims: TaxOptBReliefClaimV1[];
  notes?: string | null;
}

export interface ComplianceCheckRequest {
  profile: TaxOptBProfileV1;
  strategy: TaxOptBStrategyProposalV1;
}

/** Option B: Component B fetches Component 1 income snapshot, then runs compliance. */
export interface ComplianceFromTransactionsRequest {
  user_id: string;
  tax_year: string;
  employment_type: TaxOptBEmploymentTypeV1;
  dependents: number;
  strategy: TaxOptBStrategyProposalV1;
}

/** Component 1 aggregate (mirrors backend ``IncomeSnapshotV1``). */
export interface IncomeSnapshotV1 {
  schema_version: string;
  user_id: string;
  assessment_year: string;
  annual_gross_income: string;
  estimated_annual_taxable_income: string;
  charity_outflows_annual?: string | null;
  source: string;
  derivation_summary: string;
  pipeline_version: string;
  transaction_count: number;
}

export interface ComplianceViolation {
  rule_id: string;
  severity: string;
  message: string;
  reference: string;
}

export interface ComplianceResult {
  passed: boolean;
  violations: ComplianceViolation[];
  applied_relief: Record<string, unknown>;
  ruleset_assessment_year: string | null;
  ruleset_schema_version: string | null;
  rules_version_label: string | null;
  income_snapshot?: IncomeSnapshotV1 | null;
  /** Populated by ``POST .../compliance/check-from-financial-inputs`` only. */
  mapped_profile?: TaxOptBProfileV1 | null;
  mapped_strategy?: TaxOptBStrategyProposalV1 | null;
}

/** MVP relief codes from rules YAML — use for deduction / investment mapping UI. */
export const TAX_OPT_B_MVP_RELIEF_CODES = [
  "life_insurance_premium",
  "health_insurance_premium",
  "home_loan_interest",
  "rent_relief",
  "charitable_donations",
  "retirement_contribution",
] as const;

export type TaxOptBMvpReliefCode = (typeof TAX_OPT_B_MVP_RELIEF_CODES)[number];

export type TaxOptBInvestmentTaxTreatmentV1 = "informational" | "map_to_relief";

export interface TaxOptBDeductionLineV1 {
  relief_code: string;
  amount_annual: string;
  description?: string | null;
}

export interface TaxOptBInvestmentLineV1 {
  investment_type: string;
  amount_annual: string;
  tax_treatment: TaxOptBInvestmentTaxTreatmentV1;
  relief_code?: string | null;
}

/** Request body for ``POST .../compliance/check-from-financial-inputs``. */
export interface TaxOptBComplianceFromFinancialInputsRequestV1 {
  tax_year: string;
  employment_type: TaxOptBEmploymentTypeV1;
  dependents: number;
  annual_salary_income: string;
  annual_business_income: string;
  annual_other_income: string;
  deductions: TaxOptBDeductionLineV1[];
  investments: TaxOptBInvestmentLineV1[];
  strategy_notes?: string | null;
}

export interface TaxOptBSlabTaxSliceV1 {
  slab_index: number;
  rate: string;
  slice_width_cap: string | null;
  taxable_in_slice: string;
  tax_in_slice: string;
}

export interface TaxOptBTaxComputationV1 {
  income_basis_before_personal_relief: string;
  annual_gross_income: string;
  estimated_annual_taxable_income: string | null;
  personal_relief_annual: string;
  taxable_after_personal_relief: string;
  total_allowed_deductions: string;
  per_deduction_allowed: Record<string, unknown>[];
  taxable_after_deductions: string;
  slab_slices: TaxOptBSlabTaxSliceV1[];
  total_tax: string;
  algorithm_documentation: string;
}

/** ``POST .../compliance/compute-tax`` and ``.../compute-tax-from-financial-inputs``. */
export interface TaxOptBComputeTaxResponseV1 {
  compliance: ComplianceResult;
  tax_computation: TaxOptBTaxComputationV1 | null;
  research_disclaimer: string;
}
