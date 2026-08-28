import { recommendationApi } from "../api";
import type { RagDetailedExplanation } from "./rag";

export interface HybridQueryRequest {
  profile_id: string;
  top_k: number;
  lambda_weight?: number;
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
  items: HybridResultItem[];
}

export async function hybridQuery(payload: HybridQueryRequest): Promise<HybridQueryResponse> {
  const { data } = await recommendationApi.post<HybridQueryResponse>("/hybrid", payload);
  return data;
}
