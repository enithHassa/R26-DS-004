import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { AlertTriangle, Eye, Filter, Upload } from "lucide-react";

import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import { getProfile } from "@/features/personalized-recommendation/api/profiles";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import {
  getProfileTransactionSummary,
  getUserPortalStatements,
  getUserPortalTransactions,
  type UserPortalTransaction,
} from "@/pages/user-view/api/user-transactions";
import { StatementUploadModal } from "@/pages/user-view/components/statement-upload-modal";
import { UserActivityGroupsPanel } from "@/pages/user-view/components/user-activity-groups-panel";
import { UserStatementsTimeline } from "@/pages/user-view/components/user-statements-timeline";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";
import { taxwiseTransactionDetailPath } from "@/pages/user-view/paths";
import {
  categoryLabel,
  formatTransactionDate,
  transactionStatusClass,
  transactionStatusLabel,
} from "@/pages/user-view/utils/transaction-display";
import { cn } from "@/lib/utils";

type TransactionsTab = "curated" | "activity" | "statements";

function formatTaxYear(raw: string | undefined | null): string {
  if (!raw) return "FY —";
  const match = /^(\d{4})_(\d{2})$/.exec(raw);
  if (match) return `FY ${match[1]}/${match[2]}`;
  return raw.replace("_", "/");
}

function MetricCard({
  label,
  value,
  subtext,
  valueClassName,
}: {
  label: string;
  value: string;
  subtext: string;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
      <p className="text-sm text-[var(--uv-text-muted)]">{label}</p>
      <p
        className={cn(
          "mt-2 text-2xl font-bold tracking-tight",
          valueClassName ?? "text-[var(--uv-text)]",
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--uv-text-muted)]">{subtext}</p>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-[var(--uv-text-muted)]">—</span>;
  const pct = Math.round(value * 100);
  const tone =
    pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-400" : "bg-orange-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-white/10">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-[var(--uv-text-muted)]">{pct}%</span>
    </div>
  );
}

export function UserTransactionsPage() {
  const profileId = useUserSessionStore((s) => s.profileId);
  const queryClient = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [includeAll, setIncludeAll] = useState(false);
  const [activeTab, setActiveTab] = useState<TransactionsTab>("curated");

  const profileQuery = useQuery({
    queryKey: ["user-transactions-profile", profileId],
    queryFn: () => getProfile(profileId!),
    enabled: !!profileId,
  });

  const taxYear = profileQuery.data?.tax_year ?? null;

  const summaryQuery = useQuery({
    queryKey: ["user-transaction-summary", profileId, taxYear],
    queryFn: () => getProfileTransactionSummary(profileId!, taxYear),
    enabled: !!profileId,
  });

  const transactionsQuery = useQuery({
    queryKey: ["user-transactions", profileId, taxYear, includeAll],
    queryFn: () =>
      getUserPortalTransactions(profileId!, {
        taxYear,
        includeAll,
        limit: 100,
      }),
    enabled: !!profileId,
  });

  const statementsQuery = useQuery({
    queryKey: ["user-statements", profileId],
    queryFn: () => getUserPortalStatements(profileId!),
    enabled: !!profileId,
  });

  const reviewItems = useMemo(
    () => (transactionsQuery.data?.items ?? []).filter((row) => row.needs_review),
    [transactionsQuery.data?.items],
  );

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  const summary = summaryQuery.data;
  const fyLabel = formatTaxYear(summary?.tax_year ?? taxYear);
  const isLoading = summaryQuery.isLoading || transactionsQuery.isLoading;

  function refreshAll(): void {
    void queryClient.invalidateQueries({ queryKey: ["user-transaction-summary", profileId] });
    void queryClient.invalidateQueries({ queryKey: ["user-transactions", profileId] });
    void queryClient.invalidateQueries({ queryKey: ["user-statements", profileId] });
    void queryClient.invalidateQueries({ queryKey: ["user-activity-groups", profileId] });
  }

  return (
    <UserViewShell
      title="Transaction Analysis"
      subtitle={`${summary?.visible_transaction_count ?? 0} transactions · ${fyLabel}`}
      actions={
        <button
          type="button"
          onClick={() => setUploadOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)] transition hover:opacity-90"
        >
          <Upload className="h-4 w-4" />
          Upload Statement
        </button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Extracted credits"
              value={formatLkr(summary?.total_extracted_credits_lkr ?? "0")}
              subtext="From adviser-approved statements"
            />
            <MetricCard
              label="Identified taxable"
              value={formatLkr(summary?.total_taxable_lkr ?? "0")}
              subtext="Counts toward your return"
              valueClassName="text-red-300"
            />
            <MetricCard
              label="Non-taxable / exempt"
              value={formatLkr(summary?.total_non_taxable_lkr ?? "0")}
              subtext="Excluded from assessable income"
              valueClassName="text-emerald-300"
            />
            <MetricCard
              label="Needs review"
              value={String(summary?.review_count ?? 0)}
              subtext="Uncertain classifications"
              valueClassName="text-amber-300"
            />
          </div>

          {summary?.month_coverage?.length ? (
            <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--uv-text)]">Year coverage</h2>
                  <p className="text-xs text-[var(--uv-text-muted)]">
                    {summary.covered_month_count} of 12 months covered from released statements
                  </p>
                </div>
                {summary.missing_month_count > 0 ? (
                  <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs text-amber-300">
                    Upload missing months
                  </span>
                ) : null}
              </div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-12">
                {summary.month_coverage.map((month) => {
                  const covered = month.status === "covered";
                  return (
                    <div
                      key={month.calendar_month}
                      title={
                        covered
                          ? `${month.extracted_transaction_count} extracted row(s)`
                          : "No released statement activity"
                      }
                      className={cn(
                        "rounded-lg border px-2 py-2 text-center text-xs",
                        covered
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                          : "border-amber-500/30 bg-amber-500/10 text-amber-200",
                      )}
                    >
                      <div className="font-medium">{month.month_label.split(" ")[0]}</div>
                      <div className="mt-0.5 text-[10px] opacity-80">
                        {month.month_label.split(" ")[1]?.slice(-2)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}

          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--uv-border)] px-5 py-4">
              <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-1">
                {(
                  [
                    ["curated", "Curated view"],
                    ["activity", "By income type"],
                    ["statements", "Statements"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    className={cn(
                      "rounded-md px-3 py-1.5 text-xs font-medium transition",
                      activeTab === key
                        ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]"
                        : "text-[var(--uv-text-muted)] hover:text-[var(--uv-text)]",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {activeTab === "curated" ? (
                <button
                  type="button"
                  onClick={() => setIncludeAll((value) => !value)}
                  className="inline-flex items-center gap-2 rounded-lg border border-[var(--uv-border)] px-3 py-1.5 text-xs text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-text)]"
                >
                  <Filter className="h-3.5 w-3.5" />
                  {includeAll ? "Curated view" : "Show all credits"}
                </button>
              ) : null}
            </div>

            {activeTab === "curated" ? (
              <>
                <div className="border-b border-[var(--uv-border)] px-5 py-3">
                  <p className="text-xs text-[var(--uv-text-muted)]">
                    Taxable credits, uncertain items, and large non-taxable credits
                  </p>
                </div>

                {isLoading ? (
                  <p className="px-5 py-8 text-sm text-[var(--uv-text-muted)]">Loading transactions…</p>
                ) : null}

                {!isLoading && !(transactionsQuery.data?.items.length ?? 0) ? (
                  <div className="px-5 py-10 text-center">
                    <p className="text-sm text-[var(--uv-text-muted)]">
                      No adviser-approved transactions yet. Upload a statement and your tax adviser
                      will extract, classify, and release it to your profile.
                    </p>
                  </div>
                ) : null}

                {(transactionsQuery.data?.items.length ?? 0) > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead className="bg-white/[0.03] text-left text-xs uppercase tracking-wide text-[var(--uv-text-muted)]">
                        <tr>
                          <th className="px-4 py-3 font-medium">Date</th>
                          <th className="px-4 py-3 font-medium">Description</th>
                          <th className="px-4 py-3 font-medium">Amount</th>
                          <th className="px-4 py-3 font-medium">Category</th>
                          <th className="px-4 py-3 font-medium">Status</th>
                          <th className="px-4 py-3 font-medium">Conf.</th>
                          <th className="px-4 py-3 font-medium">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {transactionsQuery.data?.items.map((row: UserPortalTransaction) => (
                          <tr
                            key={row.extracted_transaction_id}
                            className="border-t border-[var(--uv-border)]/70 hover:bg-white/[0.02]"
                          >
                            <td className="whitespace-nowrap px-4 py-3 text-[var(--uv-text-muted)]">
                              {formatTransactionDate(row.tx_date)}
                            </td>
                            <td className="max-w-xs px-4 py-3 text-[var(--uv-text)]">
                              <div className="flex items-start gap-2">
                                {row.needs_review ? (
                                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
                                ) : null}
                                <span className="line-clamp-2">{row.description}</span>
                              </div>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--uv-text)]">
                              {formatLkr(row.amount_lkr)}
                            </td>
                            <td className="px-4 py-3 text-[var(--uv-text-muted)]">
                              {categoryLabel(row.semantic_category)}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-xs font-medium",
                                  transactionStatusClass(row.taxability_status, row.needs_review),
                                )}
                              >
                                {transactionStatusLabel(row.taxability_status, row.needs_review)}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <ConfidenceBar value={row.confidence} />
                            </td>
                            <td className="px-4 py-3">
                              <Link
                                to={taxwiseTransactionDetailPath(row.extracted_transaction_id)}
                                className="inline-flex rounded-lg p-1.5 text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-accent)]"
                                aria-label={`View reasoning for ${row.description}`}
                              >
                                <Eye className="h-4 w-4" />
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </>
            ) : null}

            {activeTab === "activity" ? (
              <UserActivityGroupsPanel profileId={profileId} taxYear={taxYear} />
            ) : null}

            {activeTab === "statements" ? (
              <UserStatementsTimeline statements={statementsQuery.data ?? []} />
            ) : null}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
            <h2 className="text-sm font-semibold text-[var(--uv-text)]">Review queue</h2>
            <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
              {reviewItems.length} uncertain transaction{reviewItems.length === 1 ? "" : "s"}
            </p>
            <div className="mt-4 space-y-3">
              {reviewItems.slice(0, 5).map((row) => (
                <div
                  key={row.extracted_transaction_id}
                  className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-amber-300">
                      {Math.round((row.confidence ?? 0) * 100)}% confidence
                    </span>
                    <Link
                      to={taxwiseTransactionDetailPath(row.extracted_transaction_id)}
                      className="text-[var(--uv-text-muted)] hover:text-[var(--uv-accent)]"
                      aria-label="Review reasoning"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-[var(--uv-text)]">
                    {row.description}
                  </p>
                  <p className="mt-1 text-sm font-medium text-[var(--uv-text)]">
                    {formatLkr(row.amount_lkr)}
                  </p>
                  <Link
                    to={taxwiseTransactionDetailPath(row.extracted_transaction_id)}
                    className="mt-3 inline-flex w-full items-center justify-center rounded-lg bg-[var(--uv-accent)] px-3 py-1.5 text-xs font-medium text-[var(--uv-accent-foreground)] transition hover:opacity-90"
                  >
                    Review
                  </Link>
                </div>
              ))}
              {!reviewItems.length ? (
                <p className="text-xs text-[var(--uv-text-muted)]">
                  No uncertain items in your released transactions.
                </p>
              ) : null}
            </div>
          </section>
        </aside>
      </div>

      <StatementUploadModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        profileId={profileId}
        taxYear={taxYear}
        onSubmitted={refreshAll}
      />
    </UserViewShell>
  );
}
