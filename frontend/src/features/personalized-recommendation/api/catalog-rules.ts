import { recommendationApi } from "../api";

export interface RulesFieldDiff {
  field: string;
  default_value: string;
  catalog_value: string;
  act_reference?: string | null;
  section_ref?: string | null;
}

export interface CatalogActReference {
  label: string;
  act_name: string;
  section_ref?: string | null;
  source_doc_id?: string | null;
  effective_from?: string | null;
  quote_excerpt?: string | null;
}

export interface CatalogPreviewMetadata {
  assessment_year: string;
  assessment_period: string;
  promoted_at?: string | null;
  promotion_source?: string | null;
  promotion_run?: string | null;
  carried_forward_from?: string | null;
  watcher_source_doc_id?: string | null;
  catalog_notes?: string | null;
  default_rules_version: string;
  default_rules_label: string;
  relief_entries_count: number;
  rate_bands_count: number;
  mapped_fields: string[];
  fallback_fields: string[];
  legal_references: CatalogActReference[];
}

export interface CatalogStatusResponse {
  default_rules_version: string;
  default_rules_path: string;
  catalog_source: string;
  catalog_approved_dir: string;
  available_assessment_years: string[];
  synced_years: Array<{
    assessment_year: string;
    synced_at: string;
    promoted_at: string | null;
    personal_relief_act: string | null;
    mapped_fields: string[];
  }>;
}

export interface CatalogPreviewResponse {
  assessment_year: string;
  metadata: CatalogPreviewMetadata;
  diffs: RulesFieldDiff[];
  already_synced: boolean;
}

export interface CatalogSyncResponse {
  assessment_year: string;
  synced_at: string;
  promoted_at: string | null;
  personal_relief_act: string | null;
  mapped_fields: string[];
  fallback_fields: string[];
  metadata: CatalogPreviewMetadata;
  diffs: RulesFieldDiff[];
}

export async function getCatalogRulesStatus(): Promise<CatalogStatusResponse> {
  const { data } = await recommendationApi.get<CatalogStatusResponse>("/admin/catalog-rules/status");
  return data;
}

export async function previewCatalogRules(assessmentYear: string): Promise<CatalogPreviewResponse> {
  const { data } = await recommendationApi.get<CatalogPreviewResponse>(
    "/admin/catalog-rules/preview",
    { params: { assessment_year: assessmentYear } },
  );
  return data;
}

export async function syncCatalogRules(assessmentYear: string): Promise<CatalogSyncResponse> {
  const { data } = await recommendationApi.post<CatalogSyncResponse>("/admin/catalog-rules/sync", {
    assessment_year: assessmentYear,
  });
  return data;
}

export async function clearCatalogRulesCache(): Promise<{ status: "cleared" }> {
  const { data } = await recommendationApi.post<{ status: "cleared" }>(
    "/admin/catalog-rules/clear",
  );
  return data;
}
