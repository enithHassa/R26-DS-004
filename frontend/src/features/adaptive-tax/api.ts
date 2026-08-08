import { createApiClient } from "@/lib/api-client";

/**
 * Adaptive Tax (Component 5) via API gateway.
 *
 * Browser calls `/api/v1/adaptive-tax/...` — Vite proxies to :8005 (or gateway);
 * service routes live under `/api/v1/...`.
 */
export const adaptiveTaxApi = createApiClient("/api/v1/adaptive-tax");

export type AdaptiveTaxHealth = {
  status: string;
  component: string;
  version?: string;
};

export type AmendmentUploadResponse = {
  id: string;
  original_filename: string;
  file_hash: string;
  storage_path: string;
  size_bytes: number;
  status: string;
  duplicate_hash_warning?: string | null;
};

export type RuleSourceItem = {
  id: string;
  amendment_job_id: string;
  extract_run_id?: string | null;
  sort_order: number;
  section: string;
  paragraph?: string | null;
  rule_type: string;
  concept_id?: string | null;
  condition?: string | null;
  formula?: string | null;
  threshold?: number | null;
  maximum?: number | null;
  effective_date?: string | null;
  amends_section?: string | null;
  source_quote: string;
  status: string;
  created_at?: string | null;
};

export type AmendmentJobDetail = {
  id: string;
  original_filename: string;
  content_type?: string | null;
  size_bytes: number;
  file_hash: string;
  storage_path: string;
  status: string;
  extracted_rules?: Record<string, unknown> | unknown[] | null;
  rejection_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  extracted_at?: string | null;
  reviewed_at?: string | null;
  rule_sources: RuleSourceItem[];
};

export type AmendmentExtractResponse = {
  job: AmendmentJobDetail;
  extract_run_id: string;
  mode: string;
  model_name: string;
  rule_count: number;
  warnings: string[];
  amends_section_candidates: string[];
};

export type AmendmentApproveResponse = {
  job: AmendmentJobDetail;
  rule_version_ids: string[];
  merge: {
    merged: boolean;
    reason: string;
    amendment_job_id: string;
    details?: Record<string, unknown> | null;
  };
  param_override?: {
    written: boolean;
    source?: string | null;
    path?: string | null;
    concept_id?: string | null;
    cap_amount?: string | null;
    rule_source_id?: string | null;
    amendment_job_id?: string | null;
  } | null;
};

export type ParamResetResponse = {
  ok: boolean;
  source: "reset_to_pre_amend";
  override_path: string;
  concept_id: string;
  qualifying_payment_cap: string;
  override?: Record<string, unknown> | null;
};

export type AmendmentRejectResponse = {
  job: AmendmentJobDetail;
  status: "rejected";
};

export type CalculateTaxRequest = {
  assessment_year: "2024_25";
  resident_status: "resident" | "non_resident";
  employment_income: string;
  business_income: string;
  investment_income: string;
  qualifying_payments: string;
  donations: string;
  other_reliefs?: Record<string, string>;
  param_set: "current" | "pre_amend_2025";
};

export type CalculationTraceStep = {
  step_id: string;
  description: string;
  formula: string;
  inputs: Record<string, string>;
  output: string;
  concept_ids: string[];
  section_uids: string[];
  rule_source_ids: string[];
};

export type RuleSourceRef = {
  id: string;
  kind: string;
  section_uid?: string | null;
  concept_id?: string | null;
};

export type CalculateTaxResponse = {
  final_tax_lkr: string;
  calculation_trace: CalculationTraceStep[];
  rules_applied: string[];
  rule_source_refs: RuleSourceRef[];
  calc_id: string;
};

export type StoredCalculation = {
  calc_id: string;
  created_at: string;
  request: CalculateTaxRequest;
  response: CalculateTaxResponse;
  param_set_effective: "current" | "pre_amend_2025";
  amendment_context?: Record<string, unknown> | null;
};

export async function getHealth(): Promise<AdaptiveTaxHealth> {
  const { data } = await adaptiveTaxApi.get<AdaptiveTaxHealth>("/health");
  return data;
}

export async function calculateTax(
  body: CalculateTaxRequest,
): Promise<CalculateTaxResponse> {
  const { data } = await adaptiveTaxApi.post<CalculateTaxResponse>("/calculate", body);
  return data;
}

export async function getCalculation(calcId: string): Promise<StoredCalculation> {
  const { data } = await adaptiveTaxApi.get<StoredCalculation>(`/calculations/${calcId}`);
  return data;
}

export type ExplainStep = {
  step_id: string;
  narrative: string;
  evidence_chunk_ids: string[];
  rule_source_id?: string | null;
};

export type EvidenceChunk = {
  chunk_id: string;
  text: string;
  section_ref?: string | null;
  source_doc_id?: string | null;
  page?: number | null;
  score?: number | null;
};

export type EvidenceSourceQuote = {
  rule_source_id: string;
  section: string;
  amends_section?: string | null;
  source_quote: string;
  concept_id?: string | null;
  maximum?: number | null;
  status: string;
  amendment_job_id?: string | null;
};

export type GraphModifiesEdge = {
  amendment_source_doc_id: string;
  section_uid: string;
  section_label?: string | null;
  source_note?: string | null;
  effective_from?: string | null;
};

export type EvidenceBundle = {
  chunks: EvidenceChunk[];
  source_quotes: EvidenceSourceQuote[];
  sections_retrieved: string[];
  sections_queried: string[];
  graph_modifies: GraphModifiesEdge[];
  warnings?: string[];
};

export type ExplainTaxResponse = {
  summary: string;
  sections_cited: string[];
  steps_explained: ExplainStep[];
  final_tax_lkr: string;
  disclaimer: string;
  insufficient_evidence: boolean;
  sections_retrieved: string[];
  calc_id: string;
  evidence?: EvidenceBundle | null;
};

export type ExplainTaxRequest = {
  calc_id?: string;
  calculation?: CalculateTaxResponse;
  request?: CalculateTaxRequest;
};

export async function explainCalculation(
  body: ExplainTaxRequest,
): Promise<ExplainTaxResponse> {
  const { data } = await adaptiveTaxApi.post<ExplainTaxResponse>("/explain", body, {
    timeout: 120_000,
  });
  return data;
}

/** Convenience wrapper: explain by persisted calc_id. */
export async function explainByCalcId(calcId: string): Promise<ExplainTaxResponse> {
  return explainCalculation({ calc_id: calcId });
}

export async function uploadAmendment(file: File): Promise<AmendmentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await adaptiveTaxApi.post<AmendmentUploadResponse>(
    "/admin/amendments/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function extractAmendment(jobId: string): Promise<AmendmentExtractResponse> {
  const { data } = await adaptiveTaxApi.post<AmendmentExtractResponse>(
    `/admin/amendments/${jobId}/extract`,
    null,
    // GPT extraction can exceed the default 30s client timeout.
    { timeout: 120_000 },
  );
  return data;
}

export async function getAmendment(jobId: string): Promise<AmendmentJobDetail> {
  const { data } = await adaptiveTaxApi.get<AmendmentJobDetail>(
    `/admin/amendments/${jobId}`,
  );
  return data;
}

export async function approveAmendment(jobId: string): Promise<AmendmentApproveResponse> {
  const { data } = await adaptiveTaxApi.post<AmendmentApproveResponse>(
    `/admin/amendments/${jobId}/approve`,
  );
  return data;
}

export async function resetParamsToPreAmend(): Promise<ParamResetResponse> {
  const { data } = await adaptiveTaxApi.post<ParamResetResponse>(
    "/admin/params/reset-to-pre-amend",
  );
  return data;
}

export async function rejectAmendment(
  jobId: string,
  reason: string,
): Promise<AmendmentRejectResponse> {
  const { data } = await adaptiveTaxApi.post<AmendmentRejectResponse>(
    `/admin/amendments/${jobId}/reject`,
    { reason },
  );
  return data;
}
