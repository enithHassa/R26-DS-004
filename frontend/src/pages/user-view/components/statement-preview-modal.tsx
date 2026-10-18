import { useEffect, useState } from "react";
import { FileSpreadsheet, FileText, Loader2, X } from "lucide-react";

import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import {
  getDocumentStatus,
  getExtractedTransactions,
  getStatementTotals,
  type DocumentStatusResponse,
  type ExtractedTransactionItem,
  type StatementTotalItem,
} from "@/features/transaction-semantic/api";
import type { UserPortalStatement } from "@/pages/user-view/api/user-transactions";
import { formatTransactionDate } from "@/pages/user-view/utils/transaction-display";
import { cn } from "@/lib/utils";

interface StatementPreviewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  statement: UserPortalStatement | null;
}

function documentKindLabel(filename: string, contentType?: string | null): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf" || contentType?.includes("pdf")) return "PDF bank statement";
  if (ext === "csv" || contentType?.includes("csv")) return "CSV export";
  if (ext === "xlsx" || ext === "xls") return "Spreadsheet";
  if (ext === "png" || ext === "jpg" || ext === "jpeg") return "Image scan";
  return "Bank statement";
}

function DocumentKindIcon({ kind }: { kind: string }) {
  if (kind.includes("CSV") || kind.includes("Spreadsheet")) {
    return <FileSpreadsheet className="h-5 w-5 text-[var(--uv-accent)]" aria-hidden />;
  }
  return <FileText className="h-5 w-5 text-[var(--uv-accent)]" aria-hidden />;
}

function statusTone(status: UserPortalStatement["portal_status"]): string {
  switch (status) {
    case "ready":
      return "bg-emerald-500/15 text-emerald-300";
    case "failed":
      return "bg-red-500/15 text-red-300";
    case "pending_review":
      return "bg-amber-500/15 text-amber-300";
    default:
      return "bg-white/10 text-[var(--uv-text-muted)]";
  }
}

function formatMoney(value: string | null): string {
  if (value === null) return "—";
  return formatLkr(value);
}

export function StatementPreviewModal({
  open,
  onOpenChange,
  statement,
}: StatementPreviewModalProps) {
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [transactions, setTransactions] = useState<ExtractedTransactionItem[]>([]);
  const [totals, setTotals] = useState<StatementTotalItem[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !statement?.document_id) {
      setStatus(null);
      setTransactions([]);
      setTotals([]);
      setTotalRows(0);
      setError(null);
      return;
    }

    const documentId = statement.document_id;
    let cancelled = false;
    async function load(): Promise<void> {
      setIsLoading(true);
      setError(null);
      try {
        const [statusRes, txRes, totalsRes] = await Promise.all([
          getDocumentStatus(documentId),
          getExtractedTransactions(documentId, 25, 0),
          getStatementTotals(documentId),
        ]);
        if (cancelled) return;
        setStatus(statusRes);
        setTransactions(txRes.transactions);
        setTotalRows(txRes.total);
        setTotals(totalsRes.totals);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load statement preview.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [open, statement]);

  if (!open || !statement) return null;

  const kind = documentKindLabel(statement.filename, status?.content_type);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="statement-preview-title"
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--uv-border)] p-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <DocumentKindIcon kind={kind} />
              <h2
                id="statement-preview-title"
                className="truncate text-lg font-semibold text-[var(--uv-text)]"
              >
                {statement.filename}
              </h2>
            </div>
            <p className="mt-1 text-sm text-[var(--uv-text-muted)]">{kind}</p>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg p-1.5 text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-text)]"
            aria-label="Close preview"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", statusTone(statement.portal_status))}>
              {statement.portal_status.replace("_", " ")}
            </span>
            <span className="text-xs text-[var(--uv-text-muted)]">
              {statement.submitted_by === "taxpayer" ? "You uploaded" : "Adviser uploaded"} ·{" "}
              {formatTransactionDate(statement.uploaded_at)}
            </span>
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-[var(--uv-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading statement details…
            </div>
          ) : null}

          {error ? <p className="text-sm text-red-400">{error}</p> : null}

          {status && !isLoading ? (
            <dl className="grid gap-3 rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--uv-text-muted)]">Bank detected</dt>
                <dd className="mt-0.5 font-medium text-[var(--uv-text)]">
                  {status.bank_detected ?? "Not detected yet"}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--uv-text-muted)]">Extracted rows</dt>
                <dd className="mt-0.5 font-medium text-[var(--uv-text)]">
                  {status.extracted_row_count}
                </dd>
              </div>
              {status.selected_parser ? (
                <div className="sm:col-span-2">
                  <dt className="text-[var(--uv-text-muted)]">Parser</dt>
                  <dd className="mt-0.5 font-mono text-xs text-[var(--uv-text)]">
                    {status.selected_parser}
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          {statement.portal_status === "pending_review" && !isLoading ? (
            <p className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-200/90">
              Your tax adviser is reviewing this statement. Extracted transactions will appear here
              once processing is complete and released to your profile.
            </p>
          ) : null}

          {status?.extraction_error ? (
            <p className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
              Extraction issue: {status.extraction_error}
            </p>
          ) : null}

          {totals.length > 0 ? (
            <section>
              <h3 className="text-sm font-semibold text-[var(--uv-text)]">Statement summary</h3>
              <div className="mt-2 space-y-2">
                {totals.map((row) => (
                  <div
                    key={row.id}
                    className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/30 px-4 py-3 text-sm"
                  >
                    <p className="text-[var(--uv-text-muted)]">
                      {row.period_start && row.period_end
                        ? `${formatTransactionDate(row.period_start)} – ${formatTransactionDate(row.period_end)}`
                        : "Statement period"}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-4 text-[var(--uv-text)]">
                      {row.total_credit != null ? (
                        <span>Credits: {formatMoney(row.total_credit)}</span>
                      ) : null}
                      {row.total_debit != null ? (
                        <span>Debits: {formatMoney(row.total_debit)}</span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {transactions.length > 0 ? (
            <section>
              <h3 className="text-sm font-semibold text-[var(--uv-text)]">
                Transaction preview
                {totalRows > transactions.length ? (
                  <span className="ml-2 font-normal text-[var(--uv-text-muted)]">
                    (showing {transactions.length} of {totalRows})
                  </span>
                ) : null}
              </h3>
              <div className="mt-2 overflow-x-auto rounded-lg border border-[var(--uv-border)]">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-[var(--uv-bg)]/60 text-xs uppercase tracking-wide text-[var(--uv-text-muted)]">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Description</th>
                      <th className="px-3 py-2">Amount</th>
                      <th className="px-3 py-2">Dir</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((row) => (
                      <tr key={row.id} className="border-t border-[var(--uv-border)]/70">
                        <td className="whitespace-nowrap px-3 py-2 text-[var(--uv-text-muted)]">
                          {formatTransactionDate(row.tx_date)}
                        </td>
                        <td className="max-w-xs px-3 py-2 text-[var(--uv-text)]">
                          <span className="line-clamp-2">{row.description}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 font-medium text-[var(--uv-text)]">
                          {formatMoney(row.amount_lkr)}
                        </td>
                        <td className="px-3 py-2 text-[var(--uv-text-muted)]">{row.direction}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {statement.portal_status === "ready" ? (
                <p className="mt-2 text-xs text-[var(--uv-text-muted)]">
                  Full classified transactions are available in the Curated view tab.
                </p>
              ) : null}
            </section>
          ) : null}

          {!isLoading && !error && transactions.length === 0 && statement.portal_status !== "pending_review" ? (
            <p className="text-sm text-[var(--uv-text-muted)]">
              No extracted transactions are available for this document yet.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
