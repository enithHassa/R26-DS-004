import type { YearDiff } from "./catalog-types";
import { yaDisplay } from "./types";

const TONE: Record<YearDiff["kind"], string> = {
  Increased:
    "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100",
  Decreased:
    "border-rose-200 bg-rose-50 text-rose-950 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100",
  Unchanged:
    "border-border bg-muted/40 text-foreground",
  New: "border-sky-200 bg-sky-50 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100",
  "Not available":
    "border-border bg-background text-muted-foreground",
  "Limited verification":
    "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100",
};

export function YearDiffPanel({
  compareYear,
  diff,
}: {
  compareYear: string;
  diff: YearDiff;
}) {
  return (
    <aside
      className={`rounded-md border px-3 py-2 text-sm ${TONE[diff.kind]}`}
      aria-label={`How this differs from YA ${yaDisplay(compareYear)}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide opacity-80">
        How this differs from YA {yaDisplay(compareYear)}
      </p>
      <p className="mt-1 font-medium">{diff.kind}</p>
      <p className="mt-0.5 text-xs opacity-90">{diff.summary}</p>
      {(diff.asOf?.quote || diff.compare?.quote) && (
        <div className="mt-2 space-y-1 border-t border-current/15 pt-2 text-[11px] opacity-90">
          {diff.asOf?.quote ? (
            <p>
              <span className="font-medium">As-of quote:</span> “{diff.asOf.quote}”
              {diff.asOf.section_ref ? ` · ${diff.asOf.section_ref}` : ""}
            </p>
          ) : null}
          {diff.compare?.quote ? (
            <p>
              <span className="font-medium">Compare quote:</span> “{diff.compare.quote}”
              {diff.compare.section_ref ? ` · ${diff.compare.section_ref}` : ""}
            </p>
          ) : null}
        </div>
      )}
    </aside>
  );
}
