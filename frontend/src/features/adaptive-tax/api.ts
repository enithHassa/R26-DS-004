import { createApiClient } from "@/lib/api-client";

/**
 * Adaptive Tax (Component 5) via API gateway.
 *
 * Browser calls `/api/v1/adaptive-tax/...` — Vite proxies to :8005 (or gateway);
 * service routes live under `/api/v1/...`.
 */
/** Field explain loads Chroma + Postgres evidence; first call can exceed 30s. */
export const adaptiveTaxApi = createApiClient("/api/v1/adaptive-tax", {
  timeoutMs: 90_000,
});

export type AdaptiveTaxHealth = {
  status: string;
  component: string;
  version?: string;
  kg_reachable?: boolean;
  kg_source?: string | null;
  required_concepts?: Record<string, boolean>;
  required_concepts_missing?: string[];
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

export type ExtractRunItem = {
  id: string;
  amendment_job_id: string;
  model_name: string;
  prompt_version?: string | null;
  status: string;
  mode?: string | null;
  warnings?: string[] | Record<string, unknown> | null;
  metrics?: Record<string, unknown> | null;
  audit_payload?: Record<string, unknown> | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
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
  latest_extract_run?: ExtractRunItem | null;
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
  personal_relief_cap: string;
  override?: Record<string, unknown> | null;
};

export type AmendmentRejectResponse = {
  job: AmendmentJobDetail;
  status: "rejected";
};

export type CalculateTaxRequest = {
  assessment_year: "2024_25" | "2025_26";
  resident_status: "resident" | "non_resident";
  employment_income: string;
  employment_final_withholding?: string;
  business_income: string;
  business_gross?: string;
  business_deductions?: string;
  capital_allowances?: string;
  investment_income: string;
  investment_final_withholding?: string;
  other_income?: string;
  other_final_withholding?: string;
  qualifying_payments: string;
  donations: string;
  apit_already_paid?: string;
  other_reliefs?: Record<string, string>;
  solar_panel_relief?: string;
  rent_relief?: string;
  senior_citizen_interest_relief?: string;
  param_set: "current" | "pre_amend_2025";
  filing_lines?: FilingLine[];
};

export type FilingLine = {
  component_id: string;
  amount: string;
  treatment?: "include" | "exempt" | "final_withholding";
  label_override?: string;
};

export type KnowledgeVersions = {
  act_version?: string;
  act_version_label?: string;
  catalog_version?: string;
  rule_pack_version?: string;
  knowledge_graph_version?: string;
  extraction_version?: string;
};

export type ComponentTraceItem = {
  component_id: string;
  display_name: string;
  amount: string;
  treatment_applied: string;
  section?: string | null;
  paragraph?: string | null;
  reason_short?: string | null;
  rule_source_ids?: string[];
  included_in_assessable?: boolean;
  legal_confidence?: string | null;
  card_id?: string | null;
};

export type FilingCatalogField = {
  component_id: string;
  display_name: string;
  sort_order: number;
  input_kind: string;
  default_treatment: string;
  user_overridable: boolean;
  section?: string | null;
  paragraph?: string | null;
  legal_confidence: string;
  confidence_basis?: string | null;
  confidence_reason?: string | null;
  reason_short?: string | null;
  source_doc_id?: string | null;
  engine_support?: string;
  status?: string;
  ui_group?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  applicable_assessment_years?: Array<"2024_25" | "2025_26">;
  rule_source_id?: string | null;
  engine_handler?: string | null;
  sec52_4_carry_forward?: boolean;
  statutory_scope?: string | null;
};

export type FilingCatalogCard = {
  card_id: string;
  display_name: string;
  sort_order: number;
  section?: string | null;
  section_uid?: string | null;
  fields: FilingCatalogField[];
};

export type FilingCatalogResponse = {
  catalog_version: string;
  act_version?: string | null;
  act_version_label?: string | null;
  extraction_version?: string | null;
  knowledge_graph_version?: string | null;
  assessment_year: "2024_25" | "2025_26";
  cards: FilingCatalogCard[];
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
  provenance?: string | null;
};

export type RuleSourceRef = {
  id: string;
  kind: string;
  section_uid?: string | null;
  concept_id?: string | null;
  section?: string | null;
  source_quote?: string | null;
  source_doc_id?: string | null;
  status?: string | null;
};

export type QualifyingPaymentCategoryResult = {
  component_id: string;
  display_name: string;
  claimed: string;
  allowable: string;
  disallowed: string;
  status: string;
  legal_reference: string;
  section?: string | null;
  paragraph?: string | null;
  reason?: string | null;
  formula?: string | null;
  legal_confidence?: string | null;
  rule_source_ids?: string[];
  claimed_amount?: string | null;
  allowable_amount?: string | null;
  deducted_this_year?: string;
  undeducted_amount?: string;
  sec52_4_eligible?: boolean;
  carry_forward_amount?: string;
  carry_forward_basis?: string | null;
};

export type QualifyingPaymentSummary = {
  total_claimed: string;
  total_allowable_before_sec52: string;
  section_52_cap?: string | null;
  final_allowable_deduction: string;
  unused_after_sec52?: string | null;
  carry_forward_out?: string | null;
  carry_forward_not_eligible?: string | null;
  sec52_4_applicable?: boolean;
  total_needs_review?: string;
};

export type FieldKgNode = {
  node_type: string;
  node_id: string;
};

export type FieldEvidenceChunk = {
  chunk_id: string;
  text: string;
  section_ref?: string | null;
  source_doc_id?: string | null;
  page?: number | null;
  score?: number | null;
};

export type FilingCatalogExplain = {
  component_id: string;
  display_name: string;
  treatment: string;
  section?: string | null;
  paragraph?: string | null;
  section_uid?: string | null;
  concept_id?: string | null;
  reason_short?: string | null;
  source_quote?: string | null;
  source_doc_id?: string | null;
  rule_source_id?: string | null;
  engine_handler?: string | null;
  legal_confidence: string;
  confidence_basis?: string | null;
  confidence_reason?: string | null;
  act_version_label?: string | null;
  assessment_year?: "2024_25" | "2025_26" | null;
  applicable_assessment_years?: Array<"2024_25" | "2025_26">;
  sec52_4_status?: string | null;
  source_label?: string | null;
  statutory_scope?: string | null;
  sec52_4_carry_forward?: boolean;
  effective_from?: string | null;
  effective_to?: string | null;
  kg_nodes?: FieldKgNode[];
  evidence_chunks?: FieldEvidenceChunk[];
  evidence_warnings?: string[];
};

export type CalculateTaxResponse = {
  final_tax_lkr: string;
  tax_payable_lkr?: string;
  tax_credits_applied_lkr?: string;
  calculation_trace: CalculationTraceStep[];
  rules_applied: string[];
  rule_source_refs: RuleSourceRef[];
  calc_id: string;
  provenance_complete?: boolean;
  knowledge_versions?: KnowledgeVersions | null;
  head_subtotals?: Record<string, string>;
  component_trace?: ComponentTraceItem[];
  qualifying_payment_categories?: QualifyingPaymentCategoryResult[];
  qualifying_payment_summary?: QualifyingPaymentSummary | null;
  qualifying_payment_carry_forward_out?: string | null;
  normalize_warnings?: string[];
  unresolved_claims?: UnresolvedClaim[];
};

export type UnresolvedClaim = {
  concept_id: string;
  component_id?: string | null;
  claimed_lkr: string;
  reason: "concept_missing_in_kg" | "no_deducted_from_edge";
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

export async function getFilingCatalog(
  assessmentYear: "2024_25" | "2025_26" = "2024_25",
): Promise<FilingCatalogResponse> {
  const { data } = await adaptiveTaxApi.get<FilingCatalogResponse>("/filing-catalog", {
    params: { assessment_year: assessmentYear },
  });
  return data;
}

export async function getFilingCatalogExplain(
  componentId: string,
  assessmentYear: "2024_25" | "2025_26" = "2024_25",
): Promise<FilingCatalogExplain> {
  const { data } = await adaptiveTaxApi.get<FilingCatalogExplain>(
    `/filing-catalog/${encodeURIComponent(componentId)}/explain`,
    { params: { assessment_year: assessmentYear } },
  );
  return data;
}

export type ReliefInterviewApprovedYear = {
  spec_version?: string;
  assessment_year: string;
  phase1_empty_skeleton?: boolean;
  notes?: string | null;
  entries: Array<Record<string, unknown>>;
  entry_count: number;
  catalog_path?: string;
};

export type ReliefInterviewApprovedAll = {
  assessment_years: string[];
  years: Array<{
    assessment_year: string;
    phase1_empty_skeleton?: boolean;
    entries: Array<Record<string, unknown>>;
    entry_count: number;
    missing?: boolean;
  }>;
};

export async function getReliefInterviewApproved(
  assessmentYear: string,
): Promise<ReliefInterviewApprovedYear> {
  const { data } = await adaptiveTaxApi.get<ReliefInterviewApprovedYear>(
    `/relief-interview/approved/${encodeURIComponent(assessmentYear)}`,
  );
  return data;
}

export async function getReliefInterviewApprovedAll(): Promise<ReliefInterviewApprovedAll> {
  const { data } = await adaptiveTaxApi.get<ReliefInterviewApprovedAll>(
    "/relief-interview/approved",
  );
  return data;
}

export type ReliefInterviewRatesYear = {
  spec_version?: string;
  assessment_year: string;
  currency?: string;
  needs_manual_verification?: boolean;
  bands?: Array<Record<string, unknown>>;
  surcharges?: Array<Record<string, unknown>>;
  special_formulas?: Array<{
    rule_id?: string;
    rule_kind?: string;
    description?: string;
    value?: string;
    effective_from?: string;
    act_name?: string;
    section_ref?: string;
    quote?: string;
    source_doc_id?: string;
  }>;
  notes?: string | null;
  catalog_path?: string;
};

export async function getReliefInterviewRates(
  assessmentYear: string,
): Promise<ReliefInterviewRatesYear> {
  const { data } = await adaptiveTaxApi.get<ReliefInterviewRatesYear>(
    `/relief-interview/rates/${encodeURIComponent(assessmentYear)}`,
  );
  return data;
}

export type CatalogEngineReceipt = {
  kind: string;
  label: string;
  amount_lkr: string;
  act_name: string;
  section_ref: string;
  quote: string;
  source_doc_id: string;
};

export type CatalogEngineResponse = {
  spec_version?: string;
  engine: string;
  assessment_year: string;
  currency?: string;
  needs_manual_verification: boolean;
  verification_badge: {
    show: boolean;
    label: string;
    needs_manual_verification: boolean;
    cleared: boolean;
  };
  gross_income_lkr: string;
  personal_relief_lkr: string;
  solar_panel_relief_lkr?: string;
  rent_relief_lkr?: string;
  senior_citizen_interest_relief_lkr?: string;
  taxable_income_lkr: string;
  final_tax_lkr: string;
  tax_payable_lkr: string;
  reliefs_applied?: Array<{
    compare_group_id?: string;
    display_name?: string;
    amount_lkr?: string;
    [key: string]: unknown;
  }>;
  band_slices?: Array<{
    band_label?: string;
    taxable_in_slice_lkr?: string;
    tax_slice_lkr?: string;
    rate_percent?: number;
    [key: string]: unknown;
  }>;
  receipts: CatalogEngineReceipt[];
  notes?: string;
};

export type CatalogEngineClaim = {
  compare_group_id: string;
  amount: string;
};

export type CatalogEngineRequest = {
  assessment_year: string;
  employment_income: string;
  business_income: string;
  investment_income: string;
  other_income: string;
  solar_panel_relief: string;
  rent_relief: string;
  senior_citizen_interest_relief: string;
  claims?: CatalogEngineClaim[];
};

export async function calculateCatalogTax(
  body: CatalogEngineRequest,
): Promise<CatalogEngineResponse> {
  const { data } = await adaptiveTaxApi.post<CatalogEngineResponse>(
    "/catalog-engine/calculate",
    body,
  );
  return data;
}

export type CoverageComponentRow = {
  component_id: string;
  display_name: string;
  section: string | null;
  status: string;
  engine_support: string;
  approved: boolean;
  engine_wired: boolean;
  provenance_complete: boolean;
  covered: boolean;
};

export type SectionCoverageRow = {
  section_key: string;
  label: string;
  n_planned: number;
  n_covered: number;
  coverage: number;
  coverage_pct: number;
  checklist_area_id: string | null;
  checklist_covered: boolean | null;
  components: CoverageComponentRow[];
};

export type LegalCoverageResponse = {
  spec_version: string;
  catalog_version: string;
  act_version_label: string;
  assessment_years: string[];
  area_summary: {
    n_planned: number;
    n_covered: number;
    coverage: number;
    coverage_pct: number;
    covered_area_ids: string[];
    pending_area_ids: string[];
    areas: Array<{
      area_id: string;
      meaning: string;
      covered: boolean;
      harvested: boolean;
      approved: boolean;
      engine_wired: boolean;
      provenance_complete: boolean;
      optional: boolean;
    }>;
  };
  sections: SectionCoverageRow[];
  definition: string;
};

export async function getLegalCoverage(
  includeOptional = false,
): Promise<LegalCoverageResponse> {
  const { data } = await adaptiveTaxApi.get<LegalCoverageResponse>(
    "/knowledge/legal-coverage",
    { params: { include_optional: includeOptional } },
  );
  return data;
}

export type UnsupportedCatalogItem = {
  component_id: string;
  display_name: string;
  section: string | null;
  paragraph: string | null;
  engine_handler: string | null;
  engine_support: string;
  status: string;
  source_doc_id: string | null;
  source_quote: string | null;
  action_required: string;
  approve_blocked_reason: string;
};

export type UnsupportedCatalogResponse = {
  count: number;
  items: UnsupportedCatalogItem[];
};

export async function getUnsupportedCatalogRules(): Promise<UnsupportedCatalogResponse> {
  const { data } = await adaptiveTaxApi.get<UnsupportedCatalogResponse>(
    "/filing-catalog/unsupported",
  );
  return data;
}

export type ReasoningGraphNode = {
  node_id: string;
  label: string;
  amount: string | null;
  step_ids: string[];
  section_uids: string[];
  rule_source_ids: string[];
  component_ids: string[];
  kg_node_ids: string[];
  legal_confidence: string | null;
  source_quote: string | null;
  section: string | null;
  present: boolean;
};

export type ReasoningGraphEdge = {
  from_node: string;
  to_node: string;
  label: string | null;
};

export type ReasoningGraphResponse = {
  calc_id: string;
  assessment_year: string;
  nodes: ReasoningGraphNode[];
  edges: ReasoningGraphEdge[];
  display_order: string[];
};

export async function getReasoningGraph(calcId: string): Promise<ReasoningGraphResponse> {
  const { data } = await adaptiveTaxApi.get<ReasoningGraphResponse>(
    `/calculations/${encodeURIComponent(calcId)}/reasoning-graph`,
  );
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
    // gpt-5-mini structured extract can take several minutes on Act PDFs.
    { timeout: 300_000 },
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
    null,
    // First approve can load Neo4j + Chroma SentenceTransformer (often >30s).
    { timeout: 120_000 },
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
