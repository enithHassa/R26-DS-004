import { recommendationApi } from "../api";
import type { FeedbackCreate, RecommendationRequest, RecommendationResponse } from "../types";

export async function generateRecommendations(
  payload: RecommendationRequest,
): Promise<RecommendationResponse> {
  const { data } = await recommendationApi.post<RecommendationResponse>(
    "/recommendations",
    payload,
  );
  return data;
}

export async function submitRecommendationFeedback(payload: FeedbackCreate): Promise<void> {
  await recommendationApi.post("/recommendations/feedback", payload);
}

