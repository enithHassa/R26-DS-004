import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, ClipboardList, MessageSquare, Send } from "lucide-react";

import { formatLkr as formatOeLkr } from "@/features/optimization-explainable-engine/format-lkr";
import { useTaxpayerOeScenario } from "@/features/optimization-explainable-engine/user/use-taxpayer-oe-scenario";
import { getBehaviouralAnswers } from "@/features/personalized-recommendation/api/behavioural-answers";
import { getProfile } from "@/features/personalized-recommendation/api/profiles";
import { TaxpayerTopRecommendationsSection } from "@/features/personalized-recommendation/components/taxpayer-top-recommendations-section";
import { useTaxpayerRecommendations } from "@/features/personalized-recommendation/hooks/use-taxpayer-recommendations";
import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import {
  behaviouralCompletionProgress,
  isBehaviouralQuestionnaireComplete,
} from "@/features/personalized-recommendation/utils/behavioural-completion";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import {
  getProfileTransactionSummary,
  getUserPortalTransactions,
} from "@/pages/user-view/api/user-transactions";
import { BehaviouralQuestionsModal } from "@/pages/user-view/components/behavioural-questions-modal";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";
import { TAXWISE_TRANSACTIONS, taxwiseTransactionDetailPath } from "@/pages/user-view/paths";
import {
  complianceSubtext,
  formatTransactionDate,
  transactionStatusClass,
  transactionStatusLabel,
} from "@/pages/user-view/utils/transaction-display";

function formatTaxYear(raw: string | undefined): string {
  if (!raw) return "FY 2026/27";
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
      <p className={`mt-2 text-2xl font-bold tracking-tight ${valueClassName ?? "text-[var(--uv-text)]"}`}>
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--uv-text-muted)]">{subtext}</p>
    </div>
  );
}

export function UserDashboardPage() {
  const profileId = useUserSessionStore((s) => s.profileId)!;
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [habitsModalOpen, setHabitsModalOpen] = useState(false);
  const autoOpenedRef = useRef(false);

  const profileQuery = useQuery({
    queryKey: ["user-dashboard-profile", profileId],
    queryFn: () => getProfile(profileId),
    enabled: !!profileId,
  });

  const oeScenario = useTaxpayerOeScenario(profileId);

  const behaviouralQuery = useQuery({
    queryKey: ["portal-behavioural-answers", profileId],
    queryFn: () => getBehaviouralAnswers(profileId),
    enabled: !!profileId,
  });

  const recommendationsQuery = useTaxpayerRecommendations(profileId);

  const taxYear = profileQuery.data?.tax_year ?? null;

  const transactionSummaryQuery = useQuery({
    queryKey: ["user-dashboard-transaction-summary", profileId, taxYear],
    queryFn: () => getProfileTransactionSummary(profileId, taxYear),
    enabled: !!profileId,
  });

  const recentTransactionsQuery = useQuery({
    queryKey: ["user-dashboard-recent-transactions", profileId, taxYear],
    queryFn: () =>
      getUserPortalTransactions(profileId, {
        taxYear,
        limit: 5,
      }),
    enabled: !!profileId,
  });

  const profile = profileQuery.data;
  const taxYearLabel = formatTaxYear(profile?.tax_year);
  const oeYearLabel = formatTaxYear(oeScenario.assessmentYear ?? profile?.tax_year);
  const oeResult = oeScenario.explore?.optimized;
  const behaviouralComplete = isBehaviouralQuestionnaireComplete(behaviouralQuery.data);
  const behaviouralProgress = behaviouralCompletionProgress(behaviouralQuery.data);

  const openHabitsModal = () => setHabitsModalOpen(true);
  const closeHabitsModal = () => {
    setHabitsModalOpen(false);
    if (searchParams.has("habits")) {
      searchParams.delete("habits");
      setSearchParams(searchParams, { replace: true });
    }
  };

  const handleHabitsComplete = () => {
    queryClient.invalidateQueries({ queryKey: ["portal-behavioural-answers", profileId] });
    closeHabitsModal();
  };

  useEffect(() => {
    if (behaviouralQuery.isLoading || behaviouralComplete) return;

    const wantsOpen = searchParams.get("habits") === "open";
    if (wantsOpen || !autoOpenedRef.current) {
      setHabitsModalOpen(true);
      autoOpenedRef.current = true;
    }
  }, [behaviouralQuery.isLoading, behaviouralComplete, searchParams]);

  const oeLoading = oeScenario.isLoading || oeScenario.exploreLoading;
  const taxPayable = oeResult
    ? formatOeLkr(oeResult.tax_payable)
    : oeLoading
      ? "…"
      : "—";
  const reliefsApplied = oeResult
    ? formatOeLkr(oeResult.total_reliefs)
    : oeLoading
      ? "…"
      : "—";
  const oeSubtext = oeResult
    ? oeYearLabel
    : oeLoading
      ? "Loading Optimization and Explainable…"
      : "Open Optimization and Explainable (engine on port 8009)";

  const transactionsCount = transactionSummaryQuery.data?.analyzed_transaction_count ?? 0;
  const complianceScore =
    transactionSummaryQuery.data?.compliance_score_pct != null
      ? `${transactionSummaryQuery.data.compliance_score_pct}%`
      : "—";
  const complianceSub = complianceSubtext(transactionSummaryQuery.data?.compliance_score_pct);
  const recentTransactions = recentTransactionsQuery.data?.items ?? [];

  return (
    <UserViewShell subtitle={`${taxYearLabel} · Last updated just now`}>
      <BehaviouralQuestionsModal
        open={habitsModalOpen && !behaviouralComplete}
        profileId={profileId}
        answers={behaviouralQuery.data}
        onClose={closeHabitsModal}
        onComplete={handleHabitsComplete}
      />

      <div className="mx-auto max-w-6xl space-y-8">
        {!behaviouralComplete && (
          <button
            type="button"
            onClick={openHabitsModal}
            className="group flex w-full items-center justify-between rounded-xl border border-[var(--uv-accent)]/35 bg-gradient-to-r from-[var(--uv-accent)]/15 to-transparent px-5 py-4 text-left transition-colors hover:border-[var(--uv-accent)]/55"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--uv-accent)]/20 text-[var(--uv-accent)]">
                <ClipboardList className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--uv-text)]">
                  Tell us about your financial habits
                </p>
                <p className="text-xs text-[var(--uv-text-muted)]">
                  {behaviouralProgress.answered} of {behaviouralProgress.total} answered — powers your
                  personalized recommendations
                </p>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-sm font-medium text-[var(--uv-accent)]">
              {behaviouralProgress.answered === 0 ? "Get started" : "Continue"}
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </span>
          </button>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Tax payable"
            value={taxPayable}
            subtext={oeSubtext}
            valueClassName="text-red-400"
          />
          <MetricCard
            label="Reliefs applied"
            value={reliefsApplied}
            subtext={oeSubtext}
            valueClassName="text-emerald-400"
          />
          <MetricCard
            label="Transactions Analyzed"
            value={String(transactionsCount)}
            subtext="Released credits this year"
            valueClassName="text-sky-300"
          />
          <MetricCard
            label="Compliance Score"
            value={complianceScore}
            subtext={complianceSub}
            valueClassName="text-emerald-400"
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] lg:col-span-3">
            <div className="flex items-center justify-between border-b border-[var(--uv-border)] px-5 py-4">
              <h2 className="font-semibold">Recent Transactions</h2>
              <Link
                to={TAXWISE_TRANSACTIONS}
                className="flex items-center gap-1 text-sm text-[var(--uv-accent)] transition hover:opacity-90"
              >
                View all
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="overflow-x-auto">
              {recentTransactionsQuery.isLoading ? (
                <p className="px-5 py-8 text-sm text-[var(--uv-text-muted)]">Loading transactions…</p>
              ) : null}
              {!recentTransactionsQuery.isLoading && !recentTransactions.length ? (
                <p className="px-5 py-8 text-sm text-[var(--uv-text-muted)]">
                  No adviser-approved transactions yet. Upload a statement or check back after your
                  adviser releases classified data.
                </p>
              ) : null}
              {recentTransactions.length > 0 ? (
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-[var(--uv-border)] text-left text-[var(--uv-text-muted)]">
                    <th className="px-5 py-3 font-medium">Date</th>
                    <th className="px-5 py-3 font-medium">Description</th>
                    <th className="px-5 py-3 font-medium text-right">Amount (LKR)</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTransactions.map((row) => (
                    <tr
                      key={row.extracted_transaction_id}
                      className="border-b border-[var(--uv-border)]/60 last:border-0"
                    >
                      <td className="px-5 py-3.5 text-[var(--uv-text-muted)]">
                        {formatTransactionDate(row.tx_date)}
                      </td>
                      <td className="px-5 py-3.5">
                        <Link
                          to={taxwiseTransactionDetailPath(row.extracted_transaction_id)}
                          className="line-clamp-1 hover:text-[var(--uv-accent)]"
                        >
                          {row.description}
                        </Link>
                      </td>
                      <td className="px-5 py-3.5 text-right tabular-nums">
                        {formatLkr(row.amount_lkr)}
                      </td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${transactionStatusClass(row.taxability_status, row.needs_review)}`}
                        >
                          {transactionStatusLabel(row.taxability_status, row.needs_review)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              ) : null}
            </div>
          </section>

          <TaxpayerTopRecommendationsSection profileId={profileId} limit={3} />
        </div>

        <div className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3">
          <div className="flex items-center gap-3">
            <MessageSquare className="h-5 w-5 shrink-0 text-[var(--uv-text-muted)]" />
            <input
              type="text"
              disabled
              placeholder="Ask TaxWise AI…"
              className="min-w-0 flex-1 bg-transparent text-sm text-[var(--uv-text-muted)] outline-none placeholder:text-[var(--uv-text-muted)]/70"
            />
            <button
              type="button"
              disabled
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--uv-accent)]/40 text-[var(--uv-accent-foreground)] opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </UserViewShell>
  );
}
