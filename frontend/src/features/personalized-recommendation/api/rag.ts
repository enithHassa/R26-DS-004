import { recommendationApi } from "../api";

export interface RagQueryRequest {
  profile_id: string;
  top_k: number;
}

export interface RagDetailedExplanation {
  what_it_means: string;
  why_you_qualify: string;
  what_to_do: string;
  potential_benefit: string;
  risk_level: string;
}

export interface RagResultItem {
  strategy_id: string;
  name: string;
  category: string;
  description: string;
  similarity_score: number;
  ird_reference: string;
  required_docs: string[];
  why_relevant: string;
  detailed_explanation: RagDetailedExplanation;
}

export interface RagQueryResponse {
  profile_id: string;
  query_text: string;
  retrieval_method: string;
  items: RagResultItem[];
}

export async function ragQuery(payload: RagQueryRequest): Promise<RagQueryResponse> {
  const { data } = await recommendationApi.post<RagQueryResponse>("/rag", payload);
  return data;
}
