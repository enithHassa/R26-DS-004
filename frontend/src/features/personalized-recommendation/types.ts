/**
 * Typed contracts mirroring `app.schemas.profile` on the FastAPI side.
 * Keep these in sync with the backend Pydantic models. The Decimal fields
 * are serialised by FastAPI as JSON strings — we keep them as strings on
 * the wire and convert at the form boundary.
 */

export type Occupation = "employee" | "business_owner" | "professional";

export type Gender = "male" | "female";

export type MaritalStatus = "single" | "married" | "divorced";

export type RiskTolerance = "low" | "medium" | "high";

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
  occupation: Occupation;
}

export interface FinancialProfileCreate {
  full_name: string;
  age_band: string;
  province: string;
  gender: Gender;
  marital_status: MaritalStatus;
  occupation: Occupation;
  dependents: number;
  years_employed: number;
  gross_monthly_income: string;
  monthly_expenses: string;
  monthly_debt_service: string;
  liquid_savings: string;
  existing_investments: string;
  total_debt: string;
  epf_balance: string;
  etf_balance: string;
  health_insurance: boolean;
  life_insurance_premium_annual: string;
  home_loan_interest_annual: string;
  donations_annual: string;
  risk_tolerance: RiskTolerance;
  investment_horizon_years: number;
  income_sources: IncomeSource[];
  tax_year: string;
}

export interface FinancialProfile extends FinancialProfileBase {
  id: string;
  created_at: string;
  updated_at: string | null;
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

export const SL_PROVINCES = [
  "Western",
  "Central",
  "Southern",
  "North Western",
] as const;

export const AGE_BANDS = [
  "18-24", "25-29", "30-34", "35-39", "40-44",
  "45-49", "50-54", "55-59", "60-64", "65-70", "70+",
] as const;
