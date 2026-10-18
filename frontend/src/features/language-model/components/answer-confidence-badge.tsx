interface AnswerConfidenceBadgeProps {
  score?: number | null;
  label?: string | null;
  className?: string;
}

/**
 * Blue "answer score" badge for supervisors / demos.
 * Source relevance meters stay green; this score is for the whole answer.
 */
export function AnswerConfidenceBadge({
  score,
  label,
  className,
}: AnswerConfidenceBadgeProps) {
  if (score == null || Number.isNaN(score)) return null;
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const text = label?.trim() || "Confidence";

  return (
    <div
      className={
        className ??
        "inline-flex flex-col gap-1 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 dark:border-sky-800 dark:bg-sky-950/40"
      }
      title="Grounding score from retrieval strength, number of law sources, and Think Twice validation"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-sky-800 dark:text-sky-200">{text}</span>
        <span className="text-sm font-bold tabular-nums text-sky-700 dark:text-sky-300">
          {clamped}%
        </span>
      </div>
      <div className="h-1.5 w-full min-w-[8rem] overflow-hidden rounded-full bg-sky-100 dark:bg-sky-900/60">
        <div
          className="h-full rounded-full bg-sky-500 transition-all"
          style={{ width: `${Math.max(clamped, 4)}%` }}
        />
      </div>
      <p className="text-[10px] text-sky-700/80 dark:text-sky-300/80">
        Answer grounding score (not a source match %)
      </p>
    </div>
  );
}
