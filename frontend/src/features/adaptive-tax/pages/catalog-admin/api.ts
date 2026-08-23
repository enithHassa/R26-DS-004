import { adaptiveTaxApi } from "../../api";

import {
  catalogAdminHeaders,
  loadCatalogAdminSession,
  type CatalogAdminSession,
} from "./session";

export type CatalogAdminSessionResponse = {
  ok: boolean;
  gate: string;
  step?: number;
  routes?: string[];
};

export type CatalogAdminActIdentity = {
  act_no: string;
  act_year: string;
  label: string;
  source: string;
  parsed_from?: string;
  quote?: string;
};

export type DuplicateCase = "a" | "b" | "b2" | "d" | "none" | "prior_failed";

export type CatalogAdminJob = {
  id: string;
  status: string;
  original_filename?: string;
  source_doc_id?: string | null;
  suggested_source_doc_id?: string | null;
  matched_source_doc_id?: string | null;
  text_sha256?: string;
  tables_sha256?: string;
  pdf_sha256?: string;
  duplicate_case?: string;
  created_at?: string;
  error?: string | null;
  included_count?: number;
  row_count?: number;
  review_path?: string | null;
  proposed_path?: string | null;
  extract_started_at?: string;
  extract_finished_at?: string;
  failed_at?: string;
};

export type DuplicateCheckResponse = {
  case: DuplicateCase;
  message: string;
  match_kind?: string;
  text_sha256?: string;
  tables_sha256?: string;
  pdf_sha256?: string;
  filename?: string;
  act_identity?: CatalogAdminActIdentity | null;
  matched_source_doc_id?: string | null;
  suggested_source_doc_id?: string | null;
  extracted_on?: string | null;
  uploaded_on?: string | null;
  review_path?: string | null;
  job_id?: string | null;
  job_path?: string | null;
  warnings?: string[];
  index_stale?: boolean;
  actions?: string[];
  job?: CatalogAdminJob | null;
};

export type CatalogAdminQueueResponse = {
  proposals: Array<{
    source_doc_id: string;
    extracted_at?: string | null;
    text_sha256?: string;
    act_title?: string | null;
    pdf_file_name?: string | null;
    included_count?: number | null;
    promotion_status?: string | null;
    review_path?: string;
  }>;
  in_flight_jobs?: Array<{
    id: string;
    status: string;
    source_doc_id?: string | null;
    original_filename?: string;
    act_label?: string | null;
    created_at?: string;
    job_path?: string;
  }>;
  failed_jobs: Array<{
    id: string;
    status: string;
    error?: string | null;
    created_at?: string;
    original_filename?: string;
    act_label?: string | null;
    job_path?: string;
  }>;
  note?: string;
};

function headers(includeReviewer: boolean): Record<string, string> {
  return catalogAdminHeaders(loadCatalogAdminSession(), { includeReviewer });
}

export async function verifyCatalogAdminToken(
  session: CatalogAdminSession,
): Promise<CatalogAdminSessionResponse> {
  const { data } = await adaptiveTaxApi.get<CatalogAdminSessionResponse>(
    "/catalog-admin/session",
    { headers: catalogAdminHeaders(session, { includeReviewer: false }) },
  );
  return data;
}

export async function verifyCatalogAdminMutating(
  session: CatalogAdminSession,
): Promise<{ ok: boolean; reviewer: string }> {
  const { data } = await adaptiveTaxApi.post<{ ok: boolean; reviewer: string }>(
    "/catalog-admin/session/check",
    {},
    { headers: catalogAdminHeaders(session, { includeReviewer: true }) },
  );
  return data;
}

export async function getCatalogAdminQueue(): Promise<CatalogAdminQueueResponse> {
  const { data } = await adaptiveTaxApi.get<CatalogAdminQueueResponse>(
    "/catalog-admin/queue",
    { headers: headers(false) },
  );
  return data;
}

export async function uploadCatalogAdminPdf(file: File): Promise<DuplicateCheckResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await adaptiveTaxApi.post<DuplicateCheckResponse>(
    "/catalog-admin/upload",
    form,
    {
      headers: { ...headers(true), "Content-Type": "multipart/form-data" },
      timeout: 180_000,
    },
  );
  return data;
}

export async function refreshCatalogAdminHashes(): Promise<{
  ok: boolean;
  indexed_at?: string;
  document_count?: number;
  path_errors?: string[];
}> {
  const { data } = await adaptiveTaxApi.post(
    "/catalog-admin/corpus-hashes/refresh",
    {},
    { headers: headers(true), timeout: 300_000 },
  );
  return data;
}

export async function getCatalogAdminJob(jobId: string): Promise<CatalogAdminJob> {
  const { data } = await adaptiveTaxApi.get<CatalogAdminJob>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}`,
    { headers: headers(false) },
  );
  return data;
}

export async function treatCatalogAdminAsNewSource(
  jobId: string,
): Promise<DuplicateCheckResponse> {
  const { data } = await adaptiveTaxApi.post<DuplicateCheckResponse>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}/treat-as-new-source`,
    {},
    { headers: headers(true) },
  );
  return data;
}

export async function discardCatalogAdminJob(jobId: string): Promise<CatalogAdminJob> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminJob>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}/discard`,
    {},
    { headers: headers(true) },
  );
  return data;
}

export async function setCatalogAdminSourceDocId(
  jobId: string,
  sourceDocId: string,
): Promise<CatalogAdminJob> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminJob>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}/source-doc-id`,
    { source_doc_id: sourceDocId },
    { headers: headers(true) },
  );
  return data;
}

export async function startCatalogAdminExtract(jobId: string): Promise<CatalogAdminJob> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminJob>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}/extract`,
    {},
    { headers: headers(true), timeout: 30_000 },
  );
  return data;
}

export async function retryCatalogAdminExtract(jobId: string): Promise<CatalogAdminJob> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminJob>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}/retry`,
    {},
    { headers: headers(true), timeout: 30_000 },
  );
  return data;
}

export async function deleteCatalogAdminJob(jobId: string): Promise<{ id: string; status: string }> {
  const { data } = await adaptiveTaxApi.delete<{ id: string; status: string }>(
    `/catalog-admin/jobs/${encodeURIComponent(jobId)}`,
    { headers: headers(true) },
  );
  return data;
}

export type CatalogAdminKind = "UPDATE" | "NEW_YEAR";

export type CatalogAdminProvision = {
  row_id: string;
  display_name?: string;
  row_kind?: string;
  section_ref?: string;
  row_quote?: string;
  kind_suggested?: CatalogAdminKind | null;
  kind_human?: CatalogAdminKind | null;
  kind_set_by?: string | null;
  kind_set_at?: string | null;
  derived_assessment_year?: string | null;
  effective_from?: string | null;
  operation_date?: string | null;
  commencement_quote?: string | null;
  commencement_parse_kind?: string | null;
  commencement_section_ref?: string | null;
  note?: string | null;
  engine_binding?: { kind?: string | null; component_id?: string | null } | null;
  engine_binding_set_by?: string | null;
  engine_binding_set_at?: string | null;
  provenance?: { reviewed_by?: string | null; reviewed_at?: string | null } | null;
};

export type CatalogAdminEngineBindingKind =
  | "none"
  | "solar_panel_relief"
  | "rent_relief"
  | "senior_citizen_interest_relief"
  | "qualifying_payments"
  | "donations"
  | "filing_line";

export type CatalogAdminReviewRow = {
  entry_id: string;
  ledger_row_id?: string;
  row_kind?: string;
  display_name?: string | null;
  description?: string | null;
  value?: string | number | null;
  cap_amount?: string | number | null;
  rate_percent?: string | number | null;
  lower?: string | number | null;
  upper?: string | number | null;
  effective_from?: string | null;
  section_ref?: string | null;
    compare_group_id?: string | null;
    extract_compare_group_id?: string | null;
    catalog_compare_group_id?: string | null;
    compare_group_mapped?: boolean;
    compare_group_map_reason?: string | null;
  quote?: string | null;
  quote_ok_full_doc?: boolean;
  pass2_verbatim?: boolean;
  included?: boolean;
  gate_ok?: boolean;
  classification?: CatalogAdminProvision | null;
  engine_binding?: { kind?: string | null; component_id?: string | null } | null;
  engine_binding_set_by?: string | null;
  engine_binding_set_at?: string | null;
  tax_effect?: string | null;
  decision_status?: string | null;
  reviewed_by?: string | null;
  can_approve?: boolean;
  approve_blocked_reason?: string | null;
  approve_label?: string;
  sole_check?: boolean;
  panel?: "relief" | "rate" | "other";
};

export type CatalogAdminTaxInertRow = {
  entry_id: string;
  display_name?: string | null;
  note?: string;
};

export type CatalogAdminProposalReview = {
  source_doc_id: string;
  proposal: {
    act_title?: string;
    extracted_at?: string;
    text_sha256?: string;
    tables_sha256?: string;
    pdf_sha256?: string;
    job_id?: string;
    row_count?: number;
    included_count?: number;
    act_identity?: CatalogAdminActIdentity | null;
    duplicate_check?: {
      outcome?: string;
      corpus_hit?: string | null;
      proposed_hit?: string | null;
    };
    proposed_for_assessment_year?: string | null;
    proposed_year_set_by?: string | null;
    proposed_year_set_at?: string | null;
    classification?: {
      status?: string;
      pages_scanned?: number;
      harvest_notes?: string[];
      harvest_record_count?: number;
      live_confirmed_yas?: string[];
      max_in_scope_ya?: string;
      corpus_harvest_written?: boolean;
      provisions?: CatalogAdminProvision[];
    };
  };
  classification_complete: boolean;
  bindings_complete?: boolean;
  unset_row_ids: string[];
  tax_inert_rows?: CatalogAdminTaxInertRow[];
  relief_rows?: CatalogAdminReviewRow[];
  rate_rows?: CatalogAdminReviewRow[];
  other_rows?: CatalogAdminReviewRow[];
  rate_panel?: {
    sole_check?: boolean;
    banner?: string | null;
    derived_assessment_years?: string[];
    ontology_diffs?: Array<{ assessment_year: string; match?: boolean; diffs?: string[] }>;
    ontology_blocks?: boolean;
  } | null;
  engine_binding_kinds?: CatalogAdminEngineBindingKind[];
  promote_enabled: boolean;
  promote_blocked_reason?: string | null;
  preview_ready?: boolean;
  has_update_rows?: boolean;
  has_new_year_rows?: boolean;
  suggested_new_year?: string | null;
  new_year_confirm_message?: string | null;
  new_year_confirmed?: boolean;
  new_year_promote_enabled?: boolean;
  new_year_promote_blocked_reason?: string | null;
  promotion_status?: string | null;
};

export type CatalogAdminPreviewGroup = {
  compare_group_id: string;
  extract_compare_group_ids?: string[];
  compare_group_mapped?: boolean;
  before: Array<{
    assessment_year: string;
    source_doc_id?: string | null;
    cap_amount?: string | number | null;
    row_id?: string | null;
  }>;
  after: Array<{
    assessment_year: string;
    source_doc_id?: string | null;
    cap_amount?: string | number | null;
    row_id?: string | null;
  }>;
  known_table?: boolean;
  known_table_ok?: boolean;
  gap_banner?: string | null;
  needs_gap_ack?: boolean;
};

export type CatalogAdminPromotePreview = {
  source_doc_id: string;
  groups: CatalogAdminPreviewGroup[];
  tax_inert_rows: CatalogAdminTaxInertRow[];
  year_files_that_would_be_written: string[];
  year_files_frozen: string[];
  engine_year_note?: string | null;
  engine_year_notes?: Array<{ assessment_year: string; message: string }>;
  blocks_promote?: boolean;
  preview_fingerprint: string;
  rate_panel?: CatalogAdminProposalReview["rate_panel"];
  needs_gap_ack_group_ids?: string[];
};

export async function getCatalogAdminProposal(
  sourceDocId: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.get<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}`,
    { headers: headers(false) },
  );
  return data;
}

export async function setCatalogAdminClassification(
  sourceDocId: string,
  rowId: string,
  kindHuman: CatalogAdminKind,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/classification`,
    { row_id: rowId, kind_human: kindHuman },
    { headers: headers(true) },
  );
  return data;
}

export async function runCatalogAdminHarvest(
  sourceDocId: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/classify`,
    {},
    { headers: headers(true), timeout: 120_000 },
  );
  return data;
}

export async function setCatalogAdminEngineBinding(
  sourceDocId: string,
  rowId: string,
  kind: CatalogAdminEngineBindingKind,
  componentId?: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/engine-binding`,
    { row_id: rowId, kind, component_id: componentId || undefined },
    { headers: headers(true) },
  );
  return data;
}

export async function approveCatalogAdminRow(
  sourceDocId: string,
  rowId: string,
  opts?: { soleCheck?: boolean },
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/rows/${encodeURIComponent(rowId)}/approve`,
    { sole_check: Boolean(opts?.soleCheck) },
    { headers: headers(true) },
  );
  return data;
}

export async function rejectCatalogAdminRow(
  sourceDocId: string,
  rowId: string,
  reason?: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/rows/${encodeURIComponent(rowId)}/reject`,
    { reason: reason || undefined },
    { headers: headers(true) },
  );
  return data;
}

export async function flagCatalogAdminRow(
  sourceDocId: string,
  rowId: string,
  reason?: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/rows/${encodeURIComponent(rowId)}/flag`,
    { reason: reason || undefined },
    { headers: headers(true) },
  );
  return data;
}

export async function previewCatalogAdminPromote(
  sourceDocId: string,
): Promise<CatalogAdminPromotePreview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminPromotePreview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/promote-preview`,
    {},
    { headers: headers(true), timeout: 120_000 },
  );
  return data;
}

export type CatalogAdminPromoteResult = CatalogAdminProposalReview & {
  promotion?: {
    status?: string;
    run_id?: string;
    written?: string[];
    year_files_frozen?: string[];
    engine_year_notes?: Array<{ assessment_year: string; message: string }>;
    engine_year_note?: string | null;
    corpus_manifest_updated?: boolean;
    tax_inert_rows?: CatalogAdminTaxInertRow[];
  };
};

export async function promoteCatalogAdminUpdate(
  sourceDocId: string,
  previewFingerprint: string,
  acknowledgedGroupIds: string[],
): Promise<CatalogAdminPromoteResult> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminPromoteResult>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/promote`,
    {
      preview_fingerprint: previewFingerprint,
      acknowledged_group_ids: acknowledgedGroupIds,
    },
    { headers: headers(true), timeout: 180_000 },
  );
  return data;
}

export async function confirmCatalogAdminNewYear(
  sourceDocId: string,
  assessmentYear: string,
): Promise<CatalogAdminProposalReview> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminProposalReview>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/confirm-new-year`,
    { assessment_year: assessmentYear, confirmed: true },
    { headers: headers(true) },
  );
  return data;
}

export async function promoteCatalogAdminNewYear(
  sourceDocId: string,
): Promise<CatalogAdminPromoteResult> {
  const { data } = await adaptiveTaxApi.post<CatalogAdminPromoteResult>(
    `/catalog-admin/proposed/${encodeURIComponent(sourceDocId)}/promote-new-year`,
    {},
    { headers: headers(true), timeout: 180_000 },
  );
  return data;
}
