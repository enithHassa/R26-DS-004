import { recommendationApi } from "../api";
import type { RagDetailedExplanation } from "./rag";

export type HybridRulesSource = "default" | "catalog";

export type RiskToleranceLevel = "low" | "medium" | "high";

export interface HybridQueryRequest {
  profile_id: string;
  top_k: number;
  lambda_weight?: number;
  rules_source?: HybridRulesSource;
  assessment_year?: string;
  /** Auditor override — replaces profile risk tolerance in rank penalties. */
  risk_tolerance_override?: RiskToleranceLevel;
}

export interface HybridRulesContext {
  rules_source: string;
  rules_version: string;
  assessment_year: string | null;
  baseline_tax_lkr: number;
  catalog_promoted_at: string | null;
  catalog_act: string | null;
  mapped_fields: string[];
}

export interface HybridResultItem {
  rank: number;
  strategy_id: string;
  name: string;
  category: string;
  description: string;
  hybrid_score: number;
  retrieval_hybrid_score: number;
  fusion_score: number;
  lambdamart_score: number;
  rag_similarity_score: number;
  adoption_probability: number;
  estimated_annual_savings: number;
  confidence: number;
  risk_score: number;
  /** Catalog audit-risk band for this strategy: low | medium | high */
  strategy_audit_risk: RiskToleranceLevel;
  /** Risk tolerance used when computing penalties (profile or auditor override) */
  risk_tolerance_applied: RiskToleranceLevel;
  ird_reference: string;
  required_docs: string[];
  why_relevant: string;
  detailed_explanation: RagDetailedExplanation;
  /** How well strategy audit-risk matches active risk view (0–1). */
  risk_alignment: number;
}

export interface HybridQueryResponse {
  profile_id: string;
  query_text: string;
  lambda_weight: number;
  rag_weight: number;
  risk_tolerance_applied: RiskToleranceLevel;
  risk_tolerance_override: boolean;
  rules_context: HybridRulesContext;
  items: HybridResultItem[];
}

export async function hybridQuery(payload: HybridQueryRequest): Promise<HybridQueryResponse> {
  const { data } = await recommendationApi.post<HybridQueryResponse>("/hybrid", payload);
  return data;
}
