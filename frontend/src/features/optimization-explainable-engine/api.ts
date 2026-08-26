import { createApiClient } from "@/lib/api-client";

import type { ReliefEntry } from "./types";
import type { CompareResponse } from "./compare-types";

/**
 * Optimization and Explainable Engine via API gateway / Vite proxy.
 *
 * Browser calls `/api/v1/optimization-explainable-engine/...`;
 * the service routes live under `/api/v1/...`.
 */
export const optimizationExplainableApi = createApiClient(
  "/api/v1/optimization-explainable-engine",
);

export type OptimizationExplainableHealth = {
  status: string;
  component: string;
  version?: string;
  phase?: string;
};

export type YearSummary = {
  assessment_year: string;
  rule_count?: number;
  rate_count?: number;
};

export type YearsResponse = {
  assessment_years: string[];
  years: YearSummary[];
  year_count: number;
};

export type ReliefsResponse = {
  assessment_year: string;
  exclude_source_doc_id?: string | null;
  entries: ReliefEntry[];
  entry_count: number;
};

export type ActSummary = {
  source_doc_id: string;
  title: string;
  relief_count: number;
  rate_band_count?: number;
};

export type ActsResponse = {
  assessment_year: string;
  acts: ActSummary[];
  act_count: number;
};

export type CalculateIncome = {
  employment: number;
  business: number;
  investment: number;
  other: number;
  interest: number;
  rents: number;
};

export type CalculateComponentClaim = {
  component_id: string;
  amount: number;
};

export type CalculateClaim = {
  entry_id: string;
  amount: number;
  affirmed?: boolean | null;
  skipped?: boolean;
  components?: CalculateComponentClaim[];
};

export type CalculateRequest = {
  assessment_year: string;
  income: CalculateIncome;
  claims: CalculateClaim[];
  exclude_source_doc_id?: string | null;
  wht_already_paid?: number;
};

export type ReliefLine = {
  entry_id: string;
  compare_group_id: string;
  display_name: string;
  binder: string;
  engine_binding_kind?: string;
  cap: number | null;
  base: number;
  claim: number;
  applied: number;
  formula: string;
  quote: string;
  source_doc_id: string;
  act_name: string;
  section_ref: string;
  unit?: string;
};

export type SlabLine = {
  band_index: number;
  lower: number;
  upper: number | null;
  rate_percent: number;
  slice: number;
  tax: number;
  band_label: string;
  quote: string;
  source_doc_id: string;
  act_name?: string;
  section_ref?: string;
};

export type CalculateResponse = {
  assessment_year: string;
  gross_income: number;
  total_reliefs: number;
  taxable_income: number;
  tax_payable: number;
  wht_already_paid?: number;
  wht_credit?: number;
  balance_payable?: number;
  tax_refund?: number;
  exclude_source_doc_id?: string | null;
  relief_lines: ReliefLine[];
  slab_lines: SlabLine[];
};

export async function getHealth(): Promise<OptimizationExplainableHealth> {
  const { data } =
    await optimizationExplainableApi.get<OptimizationExplainableHealth>("/health");
  return data;
}

export async function getYears(): Promise<YearsResponse> {
  const { data } = await optimizationExplainableApi.get<YearsResponse>("/years");
  return data;
}

export async function getReliefs(
  assessmentYear: string,
  excludeSourceDocId?: string | null,
): Promise<ReliefsResponse> {
  const { data } = await optimizationExplainableApi.get<ReliefsResponse>(
    `/reliefs/${encodeURIComponent(assessmentYear)}`,
    {
      params: excludeSourceDocId
        ? { exclude_source_doc_id: excludeSourceDocId }
        : undefined,
    },
  );
  return data;
}

export async function getActs(assessmentYear: string): Promise<ActsResponse> {
  const { data } = await optimizationExplainableApi.get<ActsResponse>(
    `/acts/${encodeURIComponent(assessmentYear)}`,
  );
  return data;
}

export async function getCompare(
  excludeSourceDocId?: string | null,
  compareGroupId?: string | null,
): Promise<CompareResponse> {
  const params: Record<string, string> = {};
  if (excludeSourceDocId) params.exclude_source_doc_id = excludeSourceDocId;
  if (compareGroupId) params.compare_group_id = compareGroupId;
  const { data } = await optimizationExplainableApi.get<CompareResponse>("/compare", {
    params: Object.keys(params).length ? params : undefined,
  });
  return data;
}

export type ExplainCitation = {
  act_name: string;
  section_ref: string;
  source_doc_id: string;
  quote: string;
};

export type ExplainHit = {
  chunk_id: string;
  source_doc_id: string;
  channel?: string;
  page?: number;
  section_ref?: string | null;
  score?: number;
  text: string;
};

export type ExplainResponse = {
  assessment_year: string;
  gross_income: number;
  total_reliefs: number;
  taxable_income: number;
  tax_payable: number;
  wht_credit?: number;
  balance_payable?: number;
  tax_refund?: number;
  exclude_source_doc_id?: string | null;
  mode?: string;
  status: string;
  narrative?: string;
  hits?: ExplainHit[];
  hit_count?: number;
  retrieve_query?: string;
  disclaimer?: string;
  detail?: string | null;
  insufficient_evidence?: boolean;
  citations?: ExplainCitation[];
};

export async function postCalculate(
  body: CalculateRequest,
): Promise<CalculateResponse> {
  const { data } = await optimizationExplainableApi.post<CalculateResponse>(
    "/calculate",
    body,
  );
  return data;
}

export async function postExplain(body: CalculateRequest): Promise<ExplainResponse> {
  const { data } = await optimizationExplainableApi.post<ExplainResponse>(
    "/explain",
    body,
    { timeout: 60_000 },
  );
  return data;
}

export type CorpusDocument = {
  source_doc_id: string;
  file_name: string;
  title: string;
  tier: string;
  chunk_count: number;
  page_count?: number;
};

export type ExtractFixtureRow = {
  file_name: string;
  source_doc_id: string;
  tier: string;
  extraction_run_id: string;
  terminus: string;
  entity_count: number;
};

export type ReviewResponse = {
  source_doc_id: string;
  tier: string;
  terminus: string;
  extraction_run_id: string;
  promote_allowed: boolean;
  entities: Record<string, unknown>[];
  entity_count: number;
};

export type MismatchFlag = {
  id: number;
  compare_group_id: string;
  year: string;
  value_consolidated: string;
  value_act: string | null;
  status: string;
  consolidated_source_doc_id: string;
  note?: string | null;
};

export type GuideNote = {
  source_label: string;
  source_doc_id: string;
  compare_group_id: string;
  display_name?: string;
  help?: string;
  quote?: string;
  required_evidence?: string[];
  review_status?: string;
};

export async function getDocuments(): Promise<{
  documents: CorpusDocument[];
  document_count: number;
  chunk_count: number;
}> {
  const { data } = await optimizationExplainableApi.get("/documents");
  return data;
}

export async function getExtractFixtures(): Promise<{
  fixtures: ExtractFixtureRow[];
  fixture_count: number;
}> {
  const { data } = await optimizationExplainableApi.get("/extract-fixtures");
  return data;
}

export async function getReview(
  sourceDocId: string,
  extractionRunId?: string | null,
): Promise<ReviewResponse> {
  const { data } = await optimizationExplainableApi.get<ReviewResponse>(
    `/review/${encodeURIComponent(sourceDocId)}`,
    {
      params: extractionRunId ? { extraction_run_id: extractionRunId } : undefined,
    },
  );
  return data;
}

export async function postPromote(sourceDocId: string, extractionRunId?: string | null) {
  const { data } = await optimizationExplainableApi.post("/promote", {
    source_doc_id: sourceDocId,
    extraction_run_id: extractionRunId ?? undefined,
  });
  return data as Record<string, unknown>;
}

export async function postFixtureApply(fileName: string) {
  const { data } = await optimizationExplainableApi.post("/fixtures/apply", {
    file_name: fileName,
  });
  return data as Record<string, unknown>;
}

export async function getMismatches(): Promise<{ flags: MismatchFlag[]; flag_count: number }> {
  const { data } = await optimizationExplainableApi.get("/mismatches");
  return data;
}

export async function patchMismatchStatus(flagId: number, status: string) {
  const { data } = await optimizationExplainableApi.patch(`/mismatches/${flagId}`, { status });
  return data;
}

export async function getGuideNotes(compareGroupId?: string | null): Promise<{
  notes: GuideNote[];
  note_count: number;
  source_label: string;
}> {
  const { data } = await optimizationExplainableApi.get("/guide-notes", {
    params: compareGroupId ? { compare_group_id: compareGroupId } : undefined,
  });
  return data;
}

export async function postGuideDisplayUpdate(sourceDocId: string) {
  const { data } = await optimizationExplainableApi.post("/guide-display/update", {
    source_doc_id: sourceDocId,
  });
  return data as { review_status: string; source_doc_id: string };
}

export async function postIngestExisting(sourceDocId: string) {
  const { data } = await optimizationExplainableApi.post(
    `/ingest/${encodeURIComponent(sourceDocId)}`,
  );
  return data as { status: string; embedding_usd: number; detail?: string };
}
