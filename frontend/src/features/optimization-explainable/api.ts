import { createApiClient } from "@/lib/api-client";

import type { ReliefEntry } from "./types";
import type { CompareResponse } from "./compare-types";

/**
 * Optimization and Explainable via API gateway / Vite proxy.
 *
 * Browser calls `/api/v1/optimization-explainable/...`;
 * the service routes live under `/api/v1/...`.
 */
export const optimizationExplainableApi = createApiClient(
  "/api/v1/optimization-explainable",
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

export type CalculateClaim = {
  entry_id: string;
  amount: number;
  affirmed?: boolean | null;
  skipped?: boolean;
};

export type CalculateRequest = {
  assessment_year: string;
  income: CalculateIncome;
  claims: CalculateClaim[];
  exclude_source_doc_id?: string | null;
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

export type ExplainResponse = {
  assessment_year: string;
  gross_income: number;
  total_reliefs: number;
  taxable_income: number;
  tax_payable: number;
  exclude_source_doc_id?: string | null;
  insufficient_evidence: boolean;
  status: string;
  narrative: string;
  cited_sections?: string[];
  citations: ExplainCitation[];
  model?: string;
  disclaimer?: string;
  detail?: string | null;
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
