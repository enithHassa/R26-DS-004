import { useEffect } from "react";
import { ClipboardList, X } from "lucide-react";

import { BehaviouralQuestionsPanel } from "@/features/personalized-recommendation/components/behavioural-questions-panel";
import {
  behaviouralCompletionProgress,
  isBehaviouralQuestionnaireComplete,
} from "@/features/personalized-recommendation/utils/behavioural-completion";
import type { BehaviouralAnswer } from "@/features/personalized-recommendation/types";

type Props = {
  open: boolean;
  profileId: string;
  answers: BehaviouralAnswer[] | undefined;
  onClose: () => void;
  onComplete: () => void;
};

export function BehaviouralQuestionsModal({
  open,
  profileId,
  answers,
  onClose,
  onComplete,
}: Props) {
  const progress = behaviouralCompletionProgress(answers);
  const complete = isBehaviouralQuestionnaireComplete(answers);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="behavioural-modal-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/65 backdrop-blur-sm"
        aria-label="Close questionnaire"
        onClick={onClose}
      />

      <div className="relative flex max-h-[min(90vh,820px)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] shadow-2xl shadow-black/40">
        <div className="border-b border-[var(--uv-border)] bg-[var(--uv-bg-elevated)] px-5 py-4 sm:px-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--uv-accent)]/20 text-[var(--uv-accent)]">
                <ClipboardList className="h-5 w-5" />
              </span>
              <div>
                <h2 id="behavioural-modal-title" className="text-base font-semibold text-[var(--uv-text)]">
                  About your financial habits
                </h2>
                <p className="mt-1 text-sm text-[var(--uv-text-muted)]">
                  {complete
                    ? "All set — submit to update your recommendations."
                    : `${progress.answered} of ${progress.total} answered · powers personalized tax strategies`}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-[var(--uv-text-muted)] transition-colors hover:bg-white/10 hover:text-[var(--uv-text)]"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          <BehaviouralQuestionsPanel
            profileId={profileId}
            theme="user-view"
            finishLabel="Submit answers"
            onFinish={onComplete}
          />
        </div>
      </div>
    </div>
  );
}
