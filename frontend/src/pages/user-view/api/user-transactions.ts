import { recommendationApi } from "@/features/personalized-recommendation/api";
import type { ProfileTaxableIncomeMonthCoverage } from "@/features/personalized-recommendation/api/profiles";

export interface ProfileTransactionSummary {
  financial_profile_id: string;
  tax_year: string | null;
  assessment_year_label: string | null;
  total_extracted_credits_lkr: string;
  total_taxable_lkr: string;
  total_non_taxable_lkr: string;
  review_count: number;
  visible_transaction_count: number;
  analyzed_transaction_count: number;
  compliance_score_pct: number | null;
  submitted_statement_count: number;
  pending_statement_count: number;
  covered_month_count: number;
  missing_month_count: number;
  month_coverage: ProfileTaxableIncomeMonthCoverage[];
}

export interface UserPortalTransaction {
  extracted_transaction_id: string;
  document_id: string;
  tx_date: string;
  description: string;
  amount_lkr: string;
  direction: string;
  semantic_category: string;
  economic_event: string | null;
  taxability_status: string;
  taxable_amount_lkr: string;
  confidence: number | null;
  certainty_tier: string | null;
  needs_review: boolean;
}

export interface UserPortalTransactionsResponse {
  financial_profile_id: string;
  tax_year: string | null;
  items: UserPortalTransaction[];
  total: number;
  limit: number;
  offset: number;
  include_all: boolean;
}

export interface UserPortalStatement {
  document_id: string;
  filename: string;
  submitted_by: string;
  uploaded_at: string;
  portal_status: "ready" | "pending_review" | "processing" | "under_review" | "failed";
  extracted_row_count: number;
  user_visible: boolean;
}

export interface UserPortalReasoningStep {
  step_key: string;
  title: string;
  detail: string;
  is_decision: boolean;
}

export interface UserPortalNarrativeHit {
  class_key: string;
  score: number;
  description: string;
  default_taxability_status: string;
}

export interface UserPortalTransactionDetail {
  extracted_transaction_id: string;
  document_id: string;
  tx_date: string;
  description: string;
  amount_lkr: string;
  direction: string;
  bank_detected: string | null;
  document_filename: string | null;
  semantic_category: string;
  economic_event: string | null;
  tax_rule_code: string | null;
  rule_reference: string | null;
  explanation: string | null;
  taxability_status: string;
  taxable_amount_lkr: string;
  certainty_tier: string | null;
  confidence: number | null;
  class_source: string | null;
  model_semantic_category: string | null;
  review_reason: string | null;
  evidence_needed: string | null;
  decision_mode: string | null;
  treatment: string | null;
  narrative_hits: UserPortalNarrativeHit[];
  reasoning_steps: UserPortalReasoningStep[];
  taxonomy_version: string | null;
  rulebook_version: string | null;
  model_version: string | null;
  flagged_for_adviser: boolean;
  flag_message: string | null;
}

export interface UserPortalActivityGroup {
  class_key: string;
  label: string;
  transaction_count: number;
  total_amount_lkr: string;
  taxable_amount_lkr: string;
  review_count: number;
}

export interface UserPortalActivityGroupsResponse {
  financial_profile_id: string;
  tax_year: string | null;
  groups: UserPortalActivityGroup[];
}

export interface UserTransactionFlagResponse {
  extracted_transaction_id: string;
  flagged: boolean;
  message: string | null;
  created_at: string;
}

export async function getProfileTransactionSummary(
  profileId: string,
  taxYear?: string | null,
): Promise<ProfileTransactionSummary> {
  const { data } = await recommendationApi.get<ProfileTransactionSummary>(
    `/profiles/${profileId}/transaction-summary`,
    { params: taxYear ? { tax_year: taxYear } : undefined },
  );
  return data;
}

export async function getUserPortalTransactions(
  profileId: string,
  options?: {
    taxYear?: string | null;
    includeAll?: boolean;
    limit?: number;
    offset?: number;
  },
): Promise<UserPortalTransactionsResponse> {
  const { data } = await recommendationApi.get<UserPortalTransactionsResponse>(
    `/profiles/${profileId}/user-transactions`,
    {
      params: {
        ...(options?.taxYear ? { tax_year: options.taxYear } : {}),
        ...(options?.includeAll ? { include_all: true } : {}),
        limit: options?.limit ?? 50,
        offset: options?.offset ?? 0,
      },
    },
  );
  return data;
}

export async function getUserPortalStatements(
  profileId: string,
): Promise<UserPortalStatement[]> {
  const { data } = await recommendationApi.get<UserPortalStatement[]>(
    `/profiles/${profileId}/user-statements`,
  );
  return data;
}

export async function getUserPortalTransactionDetail(
  profileId: string,
  extractedTransactionId: string,
): Promise<UserPortalTransactionDetail> {
  const { data } = await recommendationApi.get<UserPortalTransactionDetail>(
    `/profiles/${profileId}/user-transactions/${extractedTransactionId}`,
  );
  return data;
}

export async function getUserPortalActivityGroups(
  profileId: string,
  taxYear?: string | null,
): Promise<UserPortalActivityGroupsResponse> {
  const { data } = await recommendationApi.get<UserPortalActivityGroupsResponse>(
    `/profiles/${profileId}/transaction-activity-groups`,
    { params: taxYear ? { tax_year: taxYear } : undefined },
  );
  return data;
}

export async function flagUserPortalTransaction(
  profileId: string,
  extractedTransactionId: string,
  message?: string | null,
): Promise<UserTransactionFlagResponse> {
  const { data } = await recommendationApi.post<UserTransactionFlagResponse>(
    `/profiles/${profileId}/user-transactions/${extractedTransactionId}/flag`,
    { message: message ?? null },
  );
  return data;
}
