import { recommendationApi } from "../api";
import type {
  DerivedFeatures,
  FinancialProfile,
  FinancialProfileCreate,
  PaginatedProfiles,
  ProfileHistorySnapshot,
} from "../types";
import type { TaxReturnProfileUpdatePayload } from "@/features/tax-return-profile/mappers";

export interface ListProfilesParams {
  page?: number;
  page_size?: number;
  occupation?: string;
  district?: string;
}

export async function createProfile(
  payload: FinancialProfileCreate,
  userId?: string,
): Promise<FinancialProfile> {
  const { data } = await recommendationApi.post<FinancialProfile>("/profiles", payload, {
    params: userId ? { user_id: userId } : undefined,
  });
  return data;
}

export async function listProfiles(params: ListProfilesParams = {}): Promise<PaginatedProfiles> {
  const { data } = await recommendationApi.get<PaginatedProfiles>("/profiles", { params });
  return data;
}

export async function getProfile(profileId: string): Promise<FinancialProfile> {
  const { data } = await recommendationApi.get<FinancialProfile>(`/profiles/${profileId}`);
  return data;
}

export async function getProfileFeatures(profileId: string): Promise<DerivedFeatures> {
  const { data } = await recommendationApi.get<DerivedFeatures>(
    `/profiles/${profileId}/features`,
  );
  return data;
}

export async function getProfileHistory(
  profileId: string,
  months = 36,
): Promise<ProfileHistorySnapshot[]> {
  const { data } = await recommendationApi.get<ProfileHistorySnapshot[]>(
    `/profiles/${profileId}/history`,
    { params: { months } },
  );
  return data;
}

export async function updateProfile(
  profileId: string,
  payload: Partial<FinancialProfileCreate> | TaxReturnProfileUpdatePayload,
): Promise<FinancialProfile> {
  const { data } = await recommendationApi.patch<FinancialProfile>(
    `/profiles/${profileId}`,
    payload,
  );
  return data;
}

export async function deleteProfile(profileId: string): Promise<void> {
  await recommendationApi.delete(`/profiles/${profileId}`);
}

export async function setEligibilityOverride(
  profileId: string,
  flag: string,
  value: boolean | null,
): Promise<DerivedFeatures> {
  const { data } = await recommendationApi.patch<DerivedFeatures>(
    `/profiles/${profileId}/eligibility-overrides`,
    { flag, value },
  );
  return data;
}

export interface ProfileTaxableIncomeMonthlyLine {
  tax_year: string | null;
  calendar_month: string;
  class_key: string;
  taxable_amount_lkr: string;
  transaction_count: number;
  source_document_ids: string[];
  computed_at: string;
}

export interface ProfileTaxableIncomeMonthCoverage {
  calendar_month: string;
  month_label: string;
  status: "covered" | "missing";
  extracted_transaction_count: number;
  classified_transaction_count: number;
  taxable_credit_count: number;
  taxable_amount_lkr: string;
}

export interface ProfileTaxableIncomeMonthlyResponse {
  financial_profile_id: string;
  tax_year: string | null;
  assessment_year_label: string | null;
  ya_period_start: string | null;
  ya_period_end: string | null;
  total_taxable_lkr: string;
  covered_month_count: number;
  missing_month_count: number;
  month_coverage: ProfileTaxableIncomeMonthCoverage[];
  lines: ProfileTaxableIncomeMonthlyLine[];
}

export interface ProfileTaxableIncomeMonthDetailLine {
  extracted_transaction_id: string;
  document_id: string;
  tx_date: string;
  description: string;
  gross_amount_lkr: string;
  taxable_amount_lkr: string;
  class_key: string;
  taxability_status: string;
}

export interface ProfileTaxableIncomeMonthDetailResponse {
  financial_profile_id: string;
  calendar_month: string;
  tax_year: string | null;
  total_taxable_lkr: string;
  lines: ProfileTaxableIncomeMonthDetailLine[];
}

export async function getProfileMonthlyTaxableIncome(
  profileId: string,
  taxYear?: string,
): Promise<ProfileTaxableIncomeMonthlyResponse> {
  const { data } = await recommendationApi.get<ProfileTaxableIncomeMonthlyResponse>(
    `/profiles/${profileId}/taxable-income/monthly`,
    { params: taxYear ? { tax_year: taxYear } : undefined },
  );
  return data;
}

export async function getProfileMonthlyTaxableIncomeDetail(
  profileId: string,
  calendarMonth: string,
  taxYear?: string,
): Promise<ProfileTaxableIncomeMonthDetailResponse> {
  const { data } = await recommendationApi.get<ProfileTaxableIncomeMonthDetailResponse>(
    `/profiles/${profileId}/taxable-income/monthly/${calendarMonth}`,
    { params: taxYear ? { tax_year: taxYear } : undefined },
  );
  return data;
}

export type TaxComputationSnapshotStatus = "draft" | "calculated" | "finalized";

export interface TaxComputationSnapshotSummary {
  id: string;
  financial_profile_id: string;
  assessment_year: string;
  status: TaxComputationSnapshotStatus;
  taxpayer_name: string | null;
  tin: string | null;
  source: "auditor_manual" | "profile_load" | "transaction_merge";
  created_at: string;
  updated_at: string | null;
  has_calculate_result: boolean;
}

export interface TaxComputationSnapshotDetail extends TaxComputationSnapshotSummary {
  income_state: Record<string, unknown>;
  relief_answers: Record<string, unknown>[];
  evidence_checks: Record<string, unknown>;
  session_meta: Record<string, unknown> | null;
  calculate_result: Record<string, unknown> | null;
  explain_narrative: string | null;
  created_by: string | null;
}

export type TaxComputationSnapshotUpsert = {
  assessment_year: string;
  status: TaxComputationSnapshotStatus;
  taxpayer_name?: string | null;
  tin?: string | null;
  income_state: Record<string, unknown>;
  relief_answers?: Record<string, unknown>[];
  evidence_checks?: Record<string, unknown>;
  session_meta?: Record<string, unknown> | null;
  calculate_result?: Record<string, unknown> | null;
  explain_narrative?: string | null;
  source?: "auditor_manual" | "profile_load" | "transaction_merge";
  created_by?: string | null;
};

export async function saveTaxComputationSnapshot(
  profileId: string,
  payload: TaxComputationSnapshotUpsert,
): Promise<TaxComputationSnapshotDetail> {
  const { data } = await recommendationApi.post<TaxComputationSnapshotDetail>(
    `/profiles/${profileId}/tax-computations`,
    payload,
  );
  return data;
}

export async function listTaxComputationSnapshots(
  profileId: string,
  assessmentYear?: string,
): Promise<TaxComputationSnapshotSummary[]> {
  const { data } = await recommendationApi.get<TaxComputationSnapshotSummary[]>(
    `/profiles/${profileId}/tax-computations`,
    { params: assessmentYear ? { assessment_year: assessmentYear } : undefined },
  );
  return data;
}

export async function getLatestTaxComputationSnapshot(
  profileId: string,
  assessmentYear?: string,
): Promise<TaxComputationSnapshotDetail> {
  const { data } = await recommendationApi.get<TaxComputationSnapshotDetail>(
    `/profiles/${profileId}/tax-computations/latest`,
    { params: assessmentYear ? { assessment_year: assessmentYear } : undefined },
  );
  return data;
}
