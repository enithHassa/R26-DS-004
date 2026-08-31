import { recommendationApi } from "../api";
import type { ExplainRequest, RecommendationExplanation } from "../types";

export async function explainRecommendation(
  payload: ExplainRequest,
): Promise<RecommendationExplanation> {
  const { data } = await recommendationApi.post<RecommendationExplanation>(
    "/recommendations/explain",
    payload,
  );
  return data;
}
