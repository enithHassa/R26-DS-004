/**
 * Typed contracts mirroring `app.schemas.profile` on the FastAPI side.
 * Keep these in sync with the backend Pydantic models. The Decimal fields
 * are serialised by FastAPI as JSON strings — we keep them as strings on
 * the wire and convert at the form boundary.
 */

export type Occupation =
  | "employee"
  | "self_employed"
  | "business_owner"
  | "investor"
  | "professional"
  | "other";

export type Gender = "male" | "female" | "other";

export type MaritalStatus = "single" | "married" | "divorced" | "widowed";

export type ResidencyStatus = "resident" | "non_resident" | "dual";

export type EmploymentType = "permanent" | "contract" | "part_time" | "freelance" | "unemployed";

export type EmployerSector = "private" | "public" | "ngo" | "self_employed";

export type RiskTolerance = "low" | "medium" | "high";

export type IncomeSourceKind =
  | "employment"
  | "business"
  | "rental"
  | "interest"
  | "dividend"
  | "capital_gain"
  | "other";

export interface IncomeSource {
  kind: string;
  monthly_amount: string;
  currency?: "LKR" | "USD";
  is_taxable?: boolean;
}

export interface FinancialProfileBase {
  full_name: string;
  date_of_birth: string;
  gender: Gender;
  district: string;
  marital_status: MaritalStatus;
  residency_status: ResidencyStatus;
  nationality?: string | null;
  occupation: Occupation;
  employment_type: EmploymentType;
  employer_sector: EmployerSector;
  dependents: number;
  years_employed: number;
  gross_monthly_income: string;
  annual_bonus_lkr: string;
  monthly_expenses: string;
  monthly_debt_service: string;
  liquid_savings: string;
  existing_investments: string;
  total_debt: string;
  epf_balance: string;
  etf_balance: string;
  vehicle_value: string;
  property_value: string;
  health_insurance: boolean;
  life_insurance_premium_annual: string;
  home_loan_interest_annual: string;
  donations_annual: string;
  risk_tolerance: RiskTolerance;
  investment_horizon_years: number;
  retirement_age_target: number;
  income_sources: IncomeSource[];
  tax_year: string;
}

export interface FinancialProfileCreate {
  full_name: string;
  age_band: string;
  province: string;
  gender: Gender;
  marital_status: MaritalStatus;
  residency_status: ResidencyStatus;
  nationality?: string | null;
  occupation: Occupation;
  employment_type: EmploymentType;
  employer_sector: EmployerSector;
  dependents: number;
  years_employed: number;
  gross_monthly_income: string;
  annual_bonus_lkr: string;
  monthly_expenses: string;
  monthly_debt_service: string;
  liquid_savings: string;
  existing_investments: string;
  total_debt: string;
  epf_balance: string;
  etf_balance: string;
  vehicle_value: string;
  property_value: string;
  health_insurance: boolean;
  life_insurance_premium_annual: string;
  home_loan_interest_annual: string;
  donations_annual: string;
  risk_tolerance: RiskTolerance;
  investment_horizon_years: number;
  retirement_age_target: number;
  income_sources: IncomeSource[];
  tax_year: string;
}

export interface FinancialProfile extends FinancialProfileBase {
  id: string;
  created_at: string;
  updated_at: string | null;
  eligibility_overrides: Record<string, boolean>;
}

export interface ProfileHistorySnapshot {
  snapshot_month: string;
  gross_monthly_income: string;
  monthly_expenses: string;
  liquid_savings: string;
  existing_investments: string;
  total_debt: string;
  epf_balance: string;
  etf_balance: string;
  savings_rate: number;
}

export interface DerivedFeatures {
  profile_id: string;
  age_years: number;
  disposable_income_monthly: string;
  disposable_income_annual: string;
  savings_rate: number;
  debt_to_income: number;
  liquidity_ratio: number;
  gross_annual_taxable_income: string;
  baseline_tax_liability_annual: string;
  effective_tax_rate: number;
  eligibility_flags: Record<string, boolean>;
  eligibility_overrides: Record<string, boolean>;
}

export interface PaginatedProfiles {
  items: FinancialProfile[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScoreBreakdown {
  tax_savings_norm: number;
  adoption_prob: number;
  feasibility: number;
  risk_penalty: number;
  final_score: number;
}

export interface FeatureAttribution {
  feature: string;
  shap_value: number;
  direction: "positive" | "negative";
}

export interface RecommendationExplanation {
  top_reasons: FeatureAttribution[];
  bottom_reasons: FeatureAttribution[];
  narrative: string | null;
}

export interface StrategySummary {
  id: string;
  created_at: string;
  updated_at: string | null;
  code: string;
  name: string;
  category: string;
  description: string;
  legal_reference: string | null;
  min_income: string | null;
  max_income: string | null;
  min_age: number | null;
  max_age: number | null;
  min_liquidity: string | null;
  risk_profile: string;
  effort_score: number;
  is_active: boolean;
}

export interface RecommendationItem {
  id: string;
  rank: number;
  strategy: StrategySummary;
  estimated_annual_savings: string;
  adoption_probability: number;
  risk_score: number;
  confidence: number;
  scores: ScoreBreakdown;
  explanation: RecommendationExplanation | null;
}

export interface RecommendationResponse {
  id: string;
  profile_id: string;
  generated_at: string;
  model_version: string;
  items: RecommendationItem[];
}

export interface RecommendationRequest {
  profile_id: string;
  top_k: number;
  regenerate_candidates?: boolean;
}

export interface FeedbackCreate {
  recommendation_item_id: string;
  accepted: boolean;
  dismissed_reason?: string | null;
  user_rating?: number | null;
}

export interface BehaviouralAnswerCreate {
  question_key: string;
  answer_value: string;
}

export interface BehaviouralAnswer {
  id: string;
  profile_id: string;
  question_key: string;
  answer_value: string;
  created_at: string;
  updated_at: string | null;
}

export const SL_PROVINCES = [
  "Western",
  "Central",
  "Southern",
  "Northern",
  "Eastern",
  "North Western",
  "North Central",
  "Uva",
  "Sabaragamuwa",
] as const;

export const AGE_BANDS = [
  "18-24", "25-29", "30-34", "35-39", "40-44",
  "45-49", "50-54", "55-59", "60-64", "65-70", "70+",
] as const;

/** Phase 5 — predictive impact (FR7, FR8). */
export interface ImpactScenario {
  name: string;
  salary_growth_mean?: number;
  salary_growth_std?: number;
  inflation_mean?: number;
  investment_return_mean?: number;
  adoption_success_prob?: number;
}

export interface ImpactSimulationRequest {
  profile_id: string;
  strategy_id?: string | null;
  strategy_code?: string | null;
  horizon_years?: number;
  n_paths?: number;
  random_seed?: number | null;
  scenario?: ImpactScenario;
}

export interface YearlyProjection {
  year: number;
  projected_salary: string;
  projected_tax_liability: string;
  projected_savings: string;
  net_worth: string;
}

export interface ProjectionBand {
  year: number;
  p10: string;
  p50: string;
  p90: string;
}

export interface ImpactSummary {
  horizon_years: number;
  expected_total_savings: string;
  expected_net_worth: string;
  savings_std: string;
  value_at_risk_p10: string;
  probability_of_net_gain: number;
}

export interface ImpactSimulationResponse {
  run_id: string;
  profile_id: string;
  strategy_id: string | null;
  horizon_years: number;
  n_paths: number;
  baseline: YearlyProjection[];
  strategy_path: YearlyProjection[] | null;
  net_worth_bands: ProjectionBand[];
  tax_liability_bands: ProjectionBand[];
  summary: ImpactSummary;
}

export interface StrategyComparisonRequest {
  profile_id: string;
  strategy_codes: string[];
  horizon_years?: number;
}

/** Phase 6 — SHAP explain (FR10). */
export interface ExplainRequest {
  profile_id: string;
  strategy_code: string;
  top_k?: number;
}
