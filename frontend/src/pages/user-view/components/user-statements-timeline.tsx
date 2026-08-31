import type { UserPortalStatement } from "@/pages/user-view/api/user-transactions";
import { formatTransactionDate } from "@/pages/user-view/utils/transaction-display";
import { cn } from "@/lib/utils";
import { ChevronRight, FileSpreadsheet, FileText } from "lucide-react";

function documentKindShort(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "PDF";
  if (ext === "csv") return "CSV";
  if (ext === "xlsx" || ext === "xls") return "Excel";
  if (ext === "png" || ext === "jpg" || ext === "jpeg") return "Image";
  return ext?.toUpperCase() ?? "File";
}

function DocumentKindIcon({ filename }: { filename: string }) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv" || ext === "xlsx" || ext === "xls") {
    return <FileSpreadsheet className="h-4 w-4 shrink-0 text-[var(--uv-accent)]" aria-hidden />;
  }
  return <FileText className="h-4 w-4 shrink-0 text-[var(--uv-accent)]" aria-hidden />;
}

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
  onSelect?: (statement: UserPortalStatement) => void;
}

export function UserStatementsTimeline({ statements, onSelect }: UserStatementsTimelineProps) {
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
            <button
              type="button"
              className={cn(
                "w-full text-left transition",
                onSelect ? "cursor-pointer hover:opacity-95" : "cursor-default",
              )}
              onClick={() => onSelect?.(statement)}
              disabled={!onSelect}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <DocumentKindIcon filename={statement.filename} />
                    <p className="font-medium text-[var(--uv-text)]">{statement.filename}</p>
                  </div>
                  <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
                    {documentKindShort(statement.filename)} ·{" "}
                    {statement.submitted_by === "taxpayer" ? "You sent" : "Adviser uploaded"}{" "}
                    {formatTransactionDate(statement.uploaded_at)}
                    {statement.extracted_row_count
                      ? ` · ${statement.extracted_row_count} rows`
                      : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-1 text-xs font-medium",
                      statementStatusClass(statement.portal_status),
                    )}
                  >
                    {statementStatusLabel(statement.portal_status)}
                  </span>
                  {onSelect ? (
                    <ChevronRight className="h-4 w-4 text-[var(--uv-text-muted)]" aria-hidden />
                  ) : null}
                </div>
              </div>
              {statement.portal_status === "ready" ? (
                <p className="mt-2 text-xs text-emerald-300/90">
                  Released to your profile — tap to preview or see transactions in the curated view.
                </p>
              ) : null}
              {statement.portal_status === "pending_review" ? (
                <p className="mt-2 text-xs text-amber-200/90">
                  Waiting for your tax adviser to extract and classify this statement. Tap to view
                  details.
                </p>
              ) : null}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
