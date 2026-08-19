import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

import { getBehaviouralAnswers, submitBehaviouralAnswers } from "../api/behavioural-answers";
import { BEHAVIOURAL_QUESTIONS } from "../constants/behavioural-questions";
import { WizardNav } from "./wizard-nav";

type Props = {
  profileId: string;
  /** Shown instead of "Next" on the final question, e.g. to leave a full-screen intake flow. */
  onFinish?: () => void;
  finishLabel?: string;
};

function toSelectedValues(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw.split(",").filter(Boolean);
}

export function BehaviouralQuestionsPanel({ profileId, onFinish, finishLabel }: Props) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);

  const answersQuery = useQuery({
    queryKey: ["portal-behavioural-answers", profileId],
    queryFn: () => getBehaviouralAnswers(profileId),
  });

  const answeredMap = new Map(
    (answersQuery.data ?? []).map((a) => [a.question_key, a.answer_value]),
  );

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
    const next = multiSelected.includes(value)
      ? multiSelected.filter((v) => v !== value)
      : [...multiSelected, value];
    answerMutation.mutate({ questionKey: question.key, answerValue: next.join(",") });
  };

  return (
    <div className="space-y-4">
      <WizardNav
        steps={BEHAVIOURAL_QUESTIONS.map((_, i) => `Q${i + 1}`)}
        current={step}
        onStepClick={setStep}
      />

      <div className="rounded-lg border bg-card p-4">
        <div className="font-medium">{question.prompt}</div>
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
                onClick={() =>
                  question.multiSelect
                    ? toggleMultiOption(option.value)
                    : answerMutation.mutate({
                        questionKey: question.key,
                        answerValue: option.value,
                      })
                }
                className={cn(
                  "flex items-center justify-between gap-2 rounded-md border px-3 py-2.5 text-left text-sm transition-colors",
                  isSelected
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border hover:bg-muted/50",
                )}
              >
                {option.label}
                {isPending && <Loader2 className="h-4 w-4 flex-none animate-spin" />}
                {isSelected && !isPending && (
                  <CheckCircle2 className="h-4 w-4 flex-none text-primary" />
                )}
              </button>
            );
          })}
        </div>
        {question.multiSelect && (
          <p className="mt-3 text-[11px] text-muted-foreground">Select all that apply.</p>
        )}
      </div>

      <div className="flex justify-between">
        <button
          type="button"
          className="text-sm text-muted-foreground underline-offset-2 hover:underline disabled:opacity-40"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          Previous
        </button>
        {isLastStep && onFinish ? (
          <button
            type="button"
            className="text-sm font-medium text-primary underline-offset-2 hover:underline"
            onClick={onFinish}
          >
            {finishLabel ?? "Finish"}
          </button>
        ) : (
          <button
            type="button"
            className="text-sm text-primary underline-offset-2 hover:underline disabled:opacity-40"
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
