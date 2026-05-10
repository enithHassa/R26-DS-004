import { recommendationApi } from "../api";
import type { RecommendationRequest, RecommendationResponse } from "../types";

export async function generateRecommendations(
  payload: RecommendationRequest,
): Promise<RecommendationResponse> {
  const { data } = await recommendationApi.post<RecommendationResponse>(
    "/recommendations",
    payload,
  );
  return data;
}

