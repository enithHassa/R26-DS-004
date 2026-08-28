import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

import { getBehaviouralAnswers, submitBehaviouralAnswers } from "../api/behavioural-answers";
import { BEHAVIOURAL_QUESTIONS } from "../constants/behavioural-questions";
import {
  behaviouralCompletionProgress,
  isBehaviouralQuestionnaireComplete,
} from "../utils/behavioural-completion";
import { WizardNav } from "./wizard-nav";

type Props = {
  profileId: string;
  theme?: "default" | "user-view";
  /** Shown instead of "Next" on the final question, e.g. to leave a full-screen intake flow. */
  onFinish?: () => void;
  finishLabel?: string;
};

function toSelectedValues(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw.split(",").filter(Boolean);
}

export function BehaviouralQuestionsPanel({
  profileId,
  theme = "default",
  onFinish,
  finishLabel,
}: Props) {
  const isUserView = theme === "user-view";
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const answersQuery = useQuery({
    queryKey: ["portal-behavioural-answers", profileId],
    queryFn: () => getBehaviouralAnswers(profileId),
  });

  const answeredMap = new Map(
    (answersQuery.data ?? []).map((a) => [a.question_key, a.answer_value]),
  );
  const progress = behaviouralCompletionProgress(answersQuery.data);
  const allAnswered = isBehaviouralQuestionnaireComplete(answersQuery.data);

  const answerMutation = useMutation({
    mutationFn: (vars: { questionKey: string; answerValue: string }) =>
      submitBehaviouralAnswers(profileId, [
        { question_key: vars.questionKey, answer_value: vars.answerValue },
      ]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal-behavioural-answers", profileId] });
      queryClient.invalidateQueries({ queryKey: ["portal-recommendations", profileId] });
    },
  });

  const question = BEHAVIOURAL_QUESTIONS[step];
  const isLastStep = step === BEHAVIOURAL_QUESTIONS.length - 1;
  const singleSelected = answeredMap.get(question.key);
  const multiSelected = toSelectedValues(answeredMap.get(question.key));

  const toggleMultiOption = (value: string) => {
    setSubmitError(null);
    const next = multiSelected.includes(value)
      ? multiSelected.filter((v) => v !== value)
      : [...multiSelected, value];
    answerMutation.mutate({ questionKey: question.key, answerValue: next.join(",") });
  };

  const handleFinish = () => {
    if (!allAnswered) {
      setSubmitError(`Please answer all ${progress.total} questions before submitting.`);
      const firstMissing = BEHAVIOURAL_QUESTIONS.findIndex((q) => {
        const value = answeredMap.get(q.key);
        return !value || !value.trim();
      });
      if (firstMissing >= 0) setStep(firstMissing);
      return;
    }
    setSubmitError(null);
    onFinish?.();
  };

  return (
    <div className="space-y-4">
      <div
        className={cn(
          "flex items-center justify-between text-xs",
          isUserView ? "text-[var(--uv-text-muted)]" : "text-muted-foreground",
        )}
      >
        <span>
          {progress.answered} of {progress.total} answered
        </span>
        {allAnswered && (
          <span
            className={cn(
              "inline-flex items-center gap-1",
              isUserView ? "text-emerald-400" : "text-emerald-600",
            )}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Ready to submit
          </span>
        )}
      </div>

      <WizardNav
        steps={BEHAVIOURAL_QUESTIONS.map((_, i) => `Q${i + 1}`)}
        current={step}
        onStepClick={setStep}
        theme={theme}
      />

      <div
        className={cn(
          "rounded-xl border p-4 sm:p-5",
          isUserView
            ? "border-[var(--uv-border)] bg-[var(--uv-bg-elevated)]"
            : "border-border bg-card",
        )}
      >
        <div className={cn("font-medium", isUserView ? "text-[var(--uv-text)]" : undefined)}>
          {question.prompt}
        </div>
        <div className="mt-3 flex flex-col gap-2">
          {question.options.map((option) => {
            const isSelected = question.multiSelect
              ? multiSelected.includes(option.value)
              : singleSelected === option.value;
            const isPending =
              answerMutation.isPending &&
              answerMutation.variables?.questionKey === question.key &&
              (question.multiSelect
                ? true
                : answerMutation.variables?.answerValue === option.value);
            return (
              <button
                key={option.value}
                type="button"
                disabled={answerMutation.isPending}
                onClick={() => {
                  setSubmitError(null);
                  question.multiSelect
                    ? toggleMultiOption(option.value)
                    : answerMutation.mutate({
                        questionKey: question.key,
                        answerValue: option.value,
                      });
                }}
                className={cn(
                  "flex items-center justify-between gap-2 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                  isUserView
                    ? isSelected
                      ? "border-[var(--uv-accent)] bg-[var(--uv-accent)]/15 text-[var(--uv-text)]"
                      : "border-[var(--uv-border)] text-[var(--uv-text-muted)] hover:border-[var(--uv-accent)]/30 hover:bg-white/5 hover:text-[var(--uv-text)]"
                    : isSelected
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border hover:bg-muted/50",
                )}
              >
                {option.label}
                {isPending && <Loader2 className="h-4 w-4 flex-none animate-spin" />}
                {isSelected && !isPending && (
                  <CheckCircle2
                    className={cn(
                      "h-4 w-4 flex-none",
                      isUserView ? "text-[var(--uv-accent)]" : "text-primary",
                    )}
                  />
                )}
              </button>
            );
          })}
        </div>
        {question.multiSelect && (
          <p
            className={cn(
              "mt-3 text-[11px]",
              isUserView ? "text-[var(--uv-text-muted)]" : "text-muted-foreground",
            )}
          >
            Select all that apply.
          </p>
        )}
      </div>

      {submitError && (
        <p className="text-sm text-red-400" role="alert">
          {submitError}
        </p>
      )}

      <div className="flex justify-between pt-1">
        <button
          type="button"
          className={cn(
            "text-sm underline-offset-2 hover:underline disabled:opacity-40",
            isUserView ? "text-[var(--uv-text-muted)]" : "text-muted-foreground",
          )}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          Previous
        </button>
        {isLastStep && onFinish ? (
          <button
            type="button"
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              isUserView
                ? allAnswered
                  ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)] hover:bg-[var(--uv-accent-hover)]"
                  : "bg-white/10 text-[var(--uv-text-muted)]"
                : allAnswered
                  ? "text-primary underline-offset-2 hover:underline"
                  : "text-muted-foreground",
            )}
            onClick={handleFinish}
          >
            {finishLabel ?? "Submit"}
          </button>
        ) : (
          <button
            type="button"
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-40",
              isUserView
                ? "bg-[var(--uv-accent)]/15 text-[var(--uv-accent)] hover:bg-[var(--uv-accent)]/25"
                : "text-primary underline-offset-2 hover:underline",
            )}
            onClick={() => setStep((s) => Math.min(BEHAVIOURAL_QUESTIONS.length - 1, s + 1))}
            disabled={isLastStep}
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
