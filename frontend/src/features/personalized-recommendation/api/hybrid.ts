import { recommendationApi } from "../api";
import type { RagDetailedExplanation } from "./rag";

export type HybridRulesSource = "default" | "catalog";

export interface HybridQueryRequest {
  profile_id: string;
  top_k: number;
  lambda_weight?: number;
  rules_source?: HybridRulesSource;
  assessment_year?: string;
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
  ird_reference: string;
  required_docs: string[];
  why_relevant: string;
  detailed_explanation: RagDetailedExplanation;
}

export interface HybridQueryResponse {
  profile_id: string;
  query_text: string;
  lambda_weight: number;
  rag_weight: number;
  rules_context: HybridRulesContext;
  items: HybridResultItem[];
}

export async function hybridQuery(payload: HybridQueryRequest): Promise<HybridQueryResponse> {
  const { data } = await recommendationApi.post<HybridQueryResponse>("/hybrid", payload);
  return data;
}
