import { recommendationApi } from "../api";
import type { BehaviouralAnswer, BehaviouralAnswerCreate } from "../types";

export async function submitBehaviouralAnswers(
  profileId: string,
  answers: BehaviouralAnswerCreate[],
): Promise<BehaviouralAnswer[]> {
  const { data } = await recommendationApi.post<BehaviouralAnswer[]>(
    `/profiles/${profileId}/behavioural-answers`,
    { answers },
  );
  return data;
}

export async function getBehaviouralAnswers(profileId: string): Promise<BehaviouralAnswer[]> {
  const { data } = await recommendationApi.get<BehaviouralAnswer[]>(
    `/profiles/${profileId}/behavioural-answers`,
  );
  return data;
}
