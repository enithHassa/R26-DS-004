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

/** Optional FR5 flags (embedded in POST JSON; defaults false / summary on backend). */
export interface TaxOptBExplainRequestFlagsV1 {
  include_explanations?: boolean;
  explanation_detail?: "summary" | "detailed";
}

export interface ComplianceCheckRequest extends TaxOptBExplainRequestFlagsV1 {
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
export interface TaxOptBComplianceFromFinancialInputsRequestV1 extends TaxOptBExplainRequestFlagsV1 {
  tax_year: string;
  employment_type: TaxOptBEmploymentTypeV1;
  dependents: number;
  annual_salary_income: string;
  annual_business_income: string;
  annual_investment_income?: string;
  annual_other_income: string;
  residency?: "resident" | "non_resident";
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

export type TaxOptBExplanationBulletKindV1 =
  | "summary"
  | "compliance"
  | "relief"
  | "slab"
  | "comparison"
  | "disclaimer";

export interface TaxOptBExplanationBulletV1 {
  kind: TaxOptBExplanationBulletKindV1;
  text: string;
  source_refs: string[];
  detail_text?: string | null;
}

export interface TaxOptBExplanationSectionV1 {
  title: string;
  bullets: TaxOptBExplanationBulletV1[];
}

/** Template-based deterministic narrative from Component B (FR5). */
export interface TaxOptBExplanationBundleV1 {
  summary: string;
  sections: TaxOptBExplanationSectionV1[];
  detail_level: "summary" | "detailed";
  provenance: Record<string, string | boolean>;
  rules_version_label?: string | null;
  ruleset_assessment_year?: string | null;
}

/** ``POST .../compliance/compute-tax`` and ``.../compute-tax-from-financial-inputs``. */
export interface TaxOptBComputeTaxResponseV1 {
  compliance: ComplianceResult;
  tax_computation: TaxOptBTaxComputationV1 | null;
  research_disclaimer: string;
  explanations?: TaxOptBExplanationBundleV1 | null;
}

/** One row in ``POST .../compliance/compare-strategies`` variants list. */
export interface TaxOptBStrategyVariantV1 {
  variant_id: string;
  label?: string | null;
  strategy: TaxOptBStrategyProposalV1;
}

/** ``POST .../compliance/compare-strategies``. */
export interface TaxOptBCompareStrategiesRequestV1 extends TaxOptBExplainRequestFlagsV1 {
  profile: TaxOptBProfileV1;
  variants: TaxOptBStrategyVariantV1[];
  baseline_variant_id?: string | null;
  include_result_detail?: boolean;
}

export interface TaxOptBCompareStrategyResultRowV1 {
  variant_id: string;
  label?: string | null;
  rank: number | null;
  passed: boolean;
  total_tax: string | null;
  delta_total_tax_vs_baseline: string | null;
  violation_rule_ids: string[];
  result: TaxOptBComputeTaxResponseV1 | null;
}

/** ``POST .../compliance/compare-strategies*`` response. */
export interface TaxOptBCompareStrategiesResponseV1 {
  profile: TaxOptBProfileV1;
  baseline_variant_id?: string | null;
  rows: TaxOptBCompareStrategyResultRowV1[];
  research_disclaimer: string;
  rules_version_label?: string | null;
  explanations?: TaxOptBExplanationBundleV1 | null;
}

/** ``POST .../compliance/compare-strategies-from-financial-inputs``. */
export interface TaxOptBCompareFromFinancialInputsRequestV1 extends TaxOptBComplianceFromFinancialInputsRequestV1 {
  strategy_variants: TaxOptBStrategyVariantV1[];
  include_mapped_strategy?: boolean;
  baseline_variant_id?: string | null;
  include_result_detail?: boolean;
}

export type TaxOptBStrategySearchRankByV1 = "total_tax" | "effective_rate";

/** ``POST .../compliance/search-strategies-from-financial-inputs`` (Function 2). */
export interface TaxOptBSearchStrategiesFromFinancialInputsRequestV1
  extends TaxOptBComplianceFromFinancialInputsRequestV1 {
  top_k: number;
  rank_by: TaxOptBStrategySearchRankByV1;
  max_candidates?: number;
  baseline_candidate_id?: string | null;
  include_result_detail?: boolean;
}

/** ``POST .../strategies/ml-rank`` (Function 3). */
export interface TaxOptBSearchStrategiesMlRankRequestV1
  extends TaxOptBSearchStrategiesFromFinancialInputsRequestV1 {
  feature_version?: string | null;
  model_bundle_path?: string | null;
  max_ml_candidates?: number;
}

export interface TaxOptBAppliedReliefSummaryEntryV1 {
  relief_code: string;
  allowed?: string | null;
  cap?: string | null;
  claimed?: string | null;
}

export interface TaxOptBSearchStrategyMetricsV1 {
  gross_income: string;
  income_basis_before_personal_relief: string;
  personal_relief_annual: string;
  taxable_after_personal_relief: string;
  total_statutory_deductions: string;
  total_relief_amount: string;
  taxable_income_before_slabs: string;
  final_tax: string;
  effective_tax_rate: string | null;
  tax_savings_vs_baseline_lkr: string | null;
}

/** Income sources + assessable/taxable path (phase 2). */
export interface TaxOptBSearchTaxBreakdownV1 {
  employment_income_lkr: string;
  business_income_lkr: string;
  investment_income_lkr?: string;
  other_income_lkr: string;
  gross_income_lkr: string;
  assessable_income_lkr: string;
  personal_relief_lkr: string;
  total_statutory_deductions_lkr: string;
  total_reliefs_lkr: string;
  taxable_income_lkr: string;
  total_tax_lkr: string;
  effective_tax_rate: string | null;
  tax_savings_vs_baseline_lkr: string | null;
}

export type TaxOptBRuleTraceKindV1 = "applied_cap" | "meta";

export type TaxOptBRuleTraceOutcomeV1 = "passed" | "failed";

export type TaxOptBRuleTraceCategoryV1 = "relief_cap" | "compliance_meta";

export interface TaxOptBRuleTraceEntryV1 {
  rule_id: string;
  relief_code?: string | null;
  kind: TaxOptBRuleTraceKindV1;
  outcome?: TaxOptBRuleTraceOutcomeV1;
  short_label?: string;
  category?: TaxOptBRuleTraceCategoryV1 | null;
  summary: string;
  reference: string;
}

export interface TaxOptBSearchStrategyRowV1 {
  candidate_id: string;
  label: string;
  display_name: string;
  rank: number;
  total_tax: string;
  effective_rate: string | null;
  delta_total_tax_vs_baseline: string | null;
  metrics?: TaxOptBSearchStrategyMetricsV1 | null;
  breakdown?: TaxOptBSearchTaxBreakdownV1 | null;
  optimization_summary?: string | null;
  rule_summary: string[];
  detailed_explanations: string[];
  rule_trace: TaxOptBRuleTraceEntryV1[];
  applied_relief_summary: TaxOptBAppliedReliefSummaryEntryV1[];
  included_relief_codes: string[];
  result: TaxOptBComputeTaxResponseV1 | null;
  /** Function 3: 1-based rank under rule-only sort (present on ML-assisted responses). */
  rule_only_rank?: number | null;
  /** Function 3: regressor score used for ML ordering (not a calibrated probability). */
  ml_score?: string | null;
  /** Function 3: 1-based rank after ML-assisted ordering (matches `rank` in ML mode). */
  ml_assist_rank?: number | null;
  /** Function 3: same as `rule_only_rank` for auditing. */
  deterministic_rank?: number | null;
}

/** Function 3 — ML ranking metadata (rules remain authoritative for tax outcomes). */
export interface TaxOptBSearchMlMetaV1 {
  /** Model identifier from training manifest / artifact bundle. */
  model_id: string;
  feature_version: string;
  training_timestamp: string;
  artifact_sha256?: string | null;
  artifact_path_used: string;
  synthetic_training_data_disclaimer: string;
  compliance_assertion: string;
  inference_latency_ms: number;
  utility_alpha?: number | null;
  optimization_objective_label?: string | null;
}

export interface TaxOptBSearchTraceabilityV1 {
  grid_version: string;
  search_space_id: string;
  rules_version_label?: string | null;
  ruleset_assessment_year?: string | null;
}

export interface TaxOptBSearchOptimizationMetaV1 {
  strategies_evaluated: number;
  legal_strategies_count: number;
  rejected_strategies_count: number;
  optimization_mode: string;
  search_space_description: string;
  optimization_objective: string;
  reproducibility_id: string;
}

export interface TaxOptBTopRankExplanationV1 {
  headline: string;
  bullets: string[];
}

export interface TaxOptBSearchStrategiesResponseV1 {
  profile: TaxOptBProfileV1;
  grid_version: string;
  search_space_id: string;
  candidates_evaluated: number;
  passing_count: number;
  baseline_candidate_id: string;
  best_candidate_id: string | null;
  comparison_summary?: string | null;
  traceability?: TaxOptBSearchTraceabilityV1 | null;
  optimization_meta?: TaxOptBSearchOptimizationMetaV1 | null;
  top_rank_explanation?: TaxOptBTopRankExplanationV1 | null;
  rows: TaxOptBSearchStrategyRowV1[];
  research_disclaimer: string;
  rules_version_label?: string | null;
  explanations?: TaxOptBExplanationBundleV1 | null;
  /** Function 3: present when the response used ML-assisted reordering over the legal set. */
  ml_meta?: TaxOptBSearchMlMetaV1 | null;
}
