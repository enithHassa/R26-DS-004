import type { UserPortalStatement } from "@/pages/user-view/api/user-transactions";
import { formatTransactionDate } from "@/pages/user-view/utils/transaction-display";
import { cn } from "@/lib/utils";

function statementStatusLabel(status: UserPortalStatement["portal_status"]): string {
  switch (status) {
    case "ready":
      return "Ready";
    case "pending_review":
      return "Pending review";
    case "processing":
      return "Processing";
    case "under_review":
      return "Under review";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

function statementStatusClass(status: UserPortalStatement["portal_status"]): string {
  switch (status) {
    case "ready":
      return "bg-emerald-500/15 text-emerald-300";
    case "pending_review":
      return "bg-amber-500/15 text-amber-300";
    case "failed":
      return "bg-red-500/15 text-red-300";
    default:
      return "bg-white/10 text-[var(--uv-text-muted)]";
  }
}

interface UserStatementsTimelineProps {
  statements: UserPortalStatement[];
}

export function UserStatementsTimeline({ statements }: UserStatementsTimelineProps) {
  if (!statements.length) {
    return (
      <p className="px-5 py-10 text-center text-sm text-[var(--uv-text-muted)]">
        No statements uploaded yet. Use Upload Statement to send documents to your adviser.
      </p>
    );
  }

  return (
    <div className="space-y-0 px-5 py-4">
      {statements.map((statement, index) => (
        <div key={statement.document_id} className="relative flex gap-4 pb-6 last:pb-0">
          {index < statements.length - 1 ? (
            <span
              className="absolute left-[11px] top-6 h-[calc(100%-8px)] w-px bg-[var(--uv-border)]"
              aria-hidden
            />
          ) : null}
          <span
            className={cn(
              "relative z-10 mt-1 h-6 w-6 shrink-0 rounded-full border",
              statement.portal_status === "ready"
                ? "border-emerald-500/40 bg-emerald-500/10"
                : "border-[var(--uv-border)] bg-[var(--uv-bg)]",
            )}
          />
          <div className="min-w-0 flex-1 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-medium text-[var(--uv-text)]">{statement.filename}</p>
                <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
                  {statement.submitted_by === "taxpayer" ? "You sent" : "Adviser uploaded"}{" "}
                  {formatTransactionDate(statement.uploaded_at)}
                  {statement.extracted_row_count
                    ? ` · ${statement.extracted_row_count} rows`
                    : ""}
                </p>
              </div>
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-medium",
                  statementStatusClass(statement.portal_status),
                )}
              >
                {statementStatusLabel(statement.portal_status)}
              </span>
            </div>
            {statement.portal_status === "ready" ? (
              <p className="mt-2 text-xs text-emerald-300/90">
                Released to your profile — transactions are visible in the curated view.
              </p>
            ) : null}
            {statement.portal_status === "pending_review" ? (
              <p className="mt-2 text-xs text-amber-200/90">
                Waiting for your tax adviser to extract and classify this statement.
              </p>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
