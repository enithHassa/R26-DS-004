import { BEHAVIOURAL_QUESTIONS } from "../constants/behavioural-questions";
import type { BehaviouralAnswer } from "../types";

export function behaviouralAnswerMap(
  answers: BehaviouralAnswer[] | undefined,
): Map<string, string> {
  return new Map((answers ?? []).map((a) => [a.question_key, a.answer_value]));
}

export function isBehaviouralQuestionnaireComplete(
  answers: BehaviouralAnswer[] | undefined,
): boolean {
  const map = behaviouralAnswerMap(answers);
  return BEHAVIOURAL_QUESTIONS.every((q) => {
    const value = map.get(q.key);
    return typeof value === "string" && value.trim().length > 0;
  });
}

export function behaviouralCompletionProgress(answers: BehaviouralAnswer[] | undefined): {
  answered: number;
  total: number;
} {
  const map = behaviouralAnswerMap(answers);
  const answered = BEHAVIOURAL_QUESTIONS.filter((q) => {
    const value = map.get(q.key);
    return typeof value === "string" && value.trim().length > 0;
  }).length;
  return { answered, total: BEHAVIOURAL_QUESTIONS.length };
}
