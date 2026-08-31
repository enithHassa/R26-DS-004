import { optimizationExplainableApi } from "../api";

import {
  actAdminHeaders,
  loadActAdminSession,
  type ActAdminSession,
} from "./session";

export type ActAdminJob = {
  id: string;
  status: string;
  source_doc_id?: string;
  original_filename?: string;
  pdf_sha256?: string;
  error?: string | null;
  extraction_run_id?: string;
  entity_count?: number;
  included_count?: number;
  review_path?: string;
  act_identity?: {
    act_no: string;
    act_year: string;
    label: string;
    source: string;
  } | null;
};

export type UploadResponse = {
  case: string;
  message: string;
  job_id?: string;
  matched_source_doc_id?: string | null;
  suggested_source_doc_id?: string | null;
  act_identity?: UploadResponse["job"] extends infer _J ? ActAdminJob["act_identity"] : never;
  job?: ActAdminJob;
};

export type ReviewEntity = Record<string, unknown>;

export type YearKind = "UPDATE" | "NEW_YEAR";

export type YearContext = {
  live_years?: string[];
  update_assessment_year?: string | null;
  new_assessment_year?: string | null;
  year_kind_suggested?: YearKind | string | null;
};

export type ReviewResponse = {
  source_doc_id: string;
  extraction_run_id?: string;
  job_id?: string | null;
  act_title?: string | null;
  act_no?: string | null;
  act_year?: string | null;
  pdf_file_name?: string | null;
  extracted_at?: string | null;
  extraction_usd?: number | null;
  note?: string | null;
  year_context?: YearContext;
  entities: ReviewEntity[];
  reliefs: ReviewEntity[];
  rates: ReviewEntity[];
  rejected_noise?: ReviewEntity[];
  entity_count: number;
  included_count: number;
  pending_count: number;
  accepted_count: number;
  rejected_count: number;
  blocking_issue_count: number;
  blocking_issues: Array<{ entry_id: string; code: string; message: string }>;
  out_of_scope_count?: number;
  extracted_entity_count?: number;
  activate_allowed: boolean;
  activate_block_reason?: string | null;
  ingest_note?: string | null;
  already_in_system?: boolean;
};

export type ImpactPreviewGroup = {
  compare_group_id: string;
  display_name: string;
  entity_kind: string;
  band_index?: number;
  before: Array<{
    assessment_year: string;
    cap_amount?: string | number | null;
    source_doc_id?: string | null;
    entry_id?: string | null;
    display_name?: string | null;
    rate_percent?: string | number | null;
  }>;
  after: Array<{
    assessment_year: string;
    cap_amount?: string | number | null;
    source_doc_id?: string | null;
    entry_id?: string | null;
    display_name?: string | null;
    rate_percent?: string | number | null;
  }>;
};

export type ImpactPreviewResponse = ReviewResponse & {
  fingerprint: string;
  affected_years: string[];
  changed_group_count?: number;
  groups?: ImpactPreviewGroup[];
  impact: {
    reliefs: Record<string, Array<{ key: string; change: string }>>;
    rates: Record<string, Array<{ key: string | [string, number]; change: string }>>;
  };
};

export type CatalogPreviewResponse = {
  source_doc_id: string;
  live_years: string[];
  preview_years: string[];
  accepted_count: number;
  already_in_system?: boolean;
  assessment_year?: string;
  live_reliefs?: ReviewEntity[];
  live_rates?: ReviewEntity[];
  preview_reliefs?: ReviewEntity[];
  preview_rates?: ReviewEntity[];
  preview_ordinary_rates?: ReviewEntity[];
  preview_terminal_rates?: ReviewEntity[];
  relief_count?: number;
  band_count?: number;
  reliefs_by_year?: Record<string, ReviewEntity[]>;
  rates_by_year?: Record<string, ReviewEntity[]>;
};

export type ActAdminQueueResponse = {
  proposals: Array<{
    source_doc_id: string;
    extracted_at?: string | null;
    act_title?: string | null;
    pdf_file_name?: string | null;
    included_count?: number | null;
    entity_count?: number | null;
    promotion_status?: string | null;
    review_path?: string;
    job_id?: string;
  }>;
  in_flight_jobs: Array<{
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
  job_count: number;
  note?: string;
};

function headers(includeReviewer: boolean): Record<string, string> {
  return actAdminHeaders(loadActAdminSession(), { includeReviewer });
}

export async function verifyActAdminToken(session: ActAdminSession): Promise<{ ok: boolean }> {
  const { data } = await optimizationExplainableApi.get<{ ok: boolean }>("/act-admin/session", {
    headers: actAdminHeaders(session, { includeReviewer: false }),
  });
  return data;
}

export async function getActAdminQueue(): Promise<ActAdminQueueResponse> {
  const { data } = await optimizationExplainableApi.get<ActAdminQueueResponse>("/act-admin/queue", {
    headers: headers(false),
  });
  return data;
}

export async function uploadActAdminPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await optimizationExplainableApi.post<UploadResponse>(
    "/act-admin/upload",
    form,
    { headers: { ...headers(true), "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function startActAdminExtract(jobId: string): Promise<ActAdminJob> {
  const { data } = await optimizationExplainableApi.post<ActAdminJob>(
    `/act-admin/jobs/${jobId}/extract`,
    {},
    { headers: headers(true) },
  );
  return data;
}

export async function getActAdminJob(jobId: string): Promise<ActAdminJob> {
  const { data } = await optimizationExplainableApi.get<ActAdminJob>(`/act-admin/jobs/${jobId}`, {
    headers: headers(false),
  });
  return data;
}

export async function retryActAdminJob(jobId: string): Promise<ActAdminJob> {
  const { data } = await optimizationExplainableApi.post<ActAdminJob>(
    `/act-admin/jobs/${jobId}/retry`,
    {},
    { headers: headers(true) },
  );
  return data;
}

export function actAdminPdfUrl(jobId: string): string {
  const session = loadActAdminSession();
  const token = session?.token ?? "";
  return `/api/v1/optimization-explainable-engine/act-admin/jobs/${jobId}/pdf?token=${encodeURIComponent(token)}`;
}

export async function getActAdminReview(sourceDocId: string): Promise<ReviewResponse> {
  const { data } = await optimizationExplainableApi.get<ReviewResponse>(
    `/act-admin/review/${sourceDocId}`,
    { headers: headers(false) },
  );
  return data;
}

export async function patchActAdminRow(
  sourceDocId: string,
  entryId: string,
  patch: Record<string, unknown>,
): Promise<ReviewResponse> {
  const { data } = await optimizationExplainableApi.patch<ReviewResponse>(
    `/act-admin/review/${sourceDocId}/rows/${entryId}`,
    patch,
    { headers: headers(true) },
  );
  return data;
}

export async function setActAdminYearKindAll(
  sourceDocId: string,
  yearKind: YearKind,
): Promise<ReviewResponse> {
  const { data } = await optimizationExplainableApi.post<ReviewResponse>(
    `/act-admin/review/${sourceDocId}/year-kind`,
    { year_kind: yearKind },
    { headers: headers(true) },
  );
  return data;
}

export async function postActAdminImpactPreview(sourceDocId: string): Promise<ImpactPreviewResponse> {
  const { data } = await optimizationExplainableApi.post<ImpactPreviewResponse>(
    `/act-admin/review/${sourceDocId}/impact-preview`,
    {},
    { headers: headers(false) },
  );
  return data;
}

export async function getActAdminCatalogPreview(
  sourceDocId: string,
  assessmentYear?: string,
): Promise<CatalogPreviewResponse> {
  const { data } = await optimizationExplainableApi.get<CatalogPreviewResponse>(
    `/act-admin/review/${sourceDocId}/catalog-preview`,
    {
      headers: headers(false),
      params: assessmentYear ? { assessment_year: assessmentYear } : undefined,
    },
  );
  return data;
}

export async function activateActAdminDraft(
  sourceDocId: string,
  fingerprint: string,
): Promise<Record<string, unknown>> {
  const { data } = await optimizationExplainableApi.post<Record<string, unknown>>(
    `/act-admin/review/${sourceDocId}/activate`,
    { fingerprint },
    { headers: headers(true), timeout: 120_000 },
  );
  return data;
}

export type HideFromViewersResponse = {
  source_doc_id: string;
  hidden: boolean;
  removed_entities?: number;
  removed_run?: boolean;
  years?: string[];
  year_2027_28_present?: boolean;
  message?: string;
};

export const DEMO_HIDE_SOURCE_DOC_ID = "oee-act-100-2026";

export async function hideActAdminFromViewers(
  sourceDocId: string,
): Promise<HideFromViewersResponse> {
  const { data } = await optimizationExplainableApi.post<HideFromViewersResponse>(
    `/act-admin/review/${sourceDocId}/hide-from-viewers`,
    {},
    { headers: headers(true), timeout: 120_000 },
  );
  return data;
}

export async function deleteActAdminJob(jobId: string): Promise<Record<string, unknown>> {
  const { data } = await optimizationExplainableApi.delete<Record<string, unknown>>(
    `/act-admin/jobs/${jobId}`,
    { headers: headers(true) },
  );
  return data;
}

export async function removeActAdminDraft(sourceDocId: string): Promise<Record<string, unknown>> {
  const { data } = await optimizationExplainableApi.delete<Record<string, unknown>>(
    `/act-admin/review/${sourceDocId}`,
    { headers: headers(true) },
  );
  return data;
}
