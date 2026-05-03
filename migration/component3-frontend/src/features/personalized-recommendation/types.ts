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

export type FinancialProfileCreate = FinancialProfileBase;

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

export const SL_DISTRICTS = [
  "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya",
  "Galle", "Matara", "Hambantota", "Jaffna", "Kilinochchi", "Mannar",
  "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
  "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
  "Moneragala", "Ratnapura", "Kegalle",
] as const;
