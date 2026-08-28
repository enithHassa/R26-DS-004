import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, MessageSquare, Send, Star, UserRound } from "lucide-react";

import { getProfile, getProfileFeatures } from "@/features/personalized-recommendation/api/profiles";
import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";
import { TAXWISE_PROFILE, TAXWISE_RECOMMENDATIONS } from "@/pages/user-view/paths";

/** Placeholder data — wired to real APIs later. */
const PLACEHOLDER_TRANSACTIONS = [
  { date: "Jan 15, 2025", description: "SALARY CREDIT — ABC PVT LTD", amount: 150_000, status: "Taxable" as const },
  { date: "Jan 18, 2025", description: "TRANSFER — UNKNOWN ORIGIN", amount: 45_000, status: "Uncertain" as const },
  { date: "Jan 22, 2025", description: "GIFT RECEIPT — FAMILY", amount: 25_000, status: "Non-Taxable" as const },
  { date: "Jan 28, 2025", description: "FREELANCE — UPWORK PAYOUT", amount: 62_500, status: "Taxable" as const },
  { date: "Feb 02, 2025", description: "RENTAL INCOME — COLOMBO 03", amount: 35_000, status: "Taxable" as const },
];

const PLACEHOLDER_RECOMMENDATIONS = [
  { rank: 1, title: "Maximize Qualifying Payment Deductions", savings: 42_500 },
  { rank: 2, title: "Optimize Investment Income Structuring", savings: 28_000 },
  { rank: 3, title: "Claim APIT Credit Adjustments", savings: 15_000 },
];

const STATUS_STYLES = {
  Taxable: "bg-red-500/15 text-red-400",
  Uncertain: "bg-amber-500/15 text-amber-400",
  "Non-Taxable": "bg-emerald-500/15 text-emerald-400",
} as const;

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
  const profileId = useUserSessionStore((s) => s.profileId);

  const profileQuery = useQuery({
    queryKey: ["user-dashboard-profile", profileId],
    queryFn: () => getProfile(profileId!),
    enabled: !!profileId,
  });

  const featuresQuery = useQuery({
    queryKey: ["user-dashboard-features", profileId],
    queryFn: () => getProfileFeatures(profileId!),
    enabled: !!profileId,
  });

  const profile = profileQuery.data;
  const features = featuresQuery.data;
  const taxYearLabel = formatTaxYear(profile?.tax_year);

  const taxLiability = features
    ? formatLkr(features.baseline_tax_liability_annual)
    : "LKR 285,000";

  const potentialSavings = "LKR 42,500";
  const transactionsCount = "847";
  const complianceScore = "94%";

  return (
    <UserViewShell subtitle={`${taxYearLabel} · Last updated just now`}>
      <div className="mx-auto max-w-6xl space-y-8">
        <Link
          to={TAXWISE_PROFILE}
          className="flex items-center justify-between rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] px-5 py-4 transition-colors hover:border-[var(--uv-accent)]/40"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]">
              <UserRound className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold">Your profile</p>
              <p className="text-xs text-[var(--uv-text-muted)]">
                Income, assets, insurance, and tax position from your auditor
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 text-sm text-[var(--uv-accent)]">
            View details
            <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </Link>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Estimated Tax Liability"
            value={taxLiability}
            subtext={taxYearLabel}
            valueClassName="text-red-400"
          />
          <MetricCard
            label="Potential Savings"
            value={potentialSavings}
            subtext="3 strategies available"
            valueClassName="text-emerald-400"
          />
          <MetricCard
            label="Transactions Analyzed"
            value={transactionsCount}
            subtext="Last 12 months"
            valueClassName="text-sky-300"
          />
          <MetricCard
            label="Compliance Score"
            value={complianceScore}
            subtext="Excellent standing"
            valueClassName="text-emerald-400"
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] lg:col-span-3">
            <div className="flex items-center justify-between border-b border-[var(--uv-border)] px-5 py-4">
              <h2 className="font-semibold">Recent Transactions</h2>
              <button
                type="button"
                disabled
                className="flex items-center gap-1 text-sm text-[var(--uv-accent)] opacity-50"
              >
                View all
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="overflow-x-auto">
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
                  {PLACEHOLDER_TRANSACTIONS.map((row) => (
                    <tr key={row.date + row.description} className="border-b border-[var(--uv-border)]/60 last:border-0">
                      <td className="px-5 py-3.5 text-[var(--uv-text-muted)]">{row.date}</td>
                      <td className="px-5 py-3.5">{row.description}</td>
                      <td className="px-5 py-3.5 text-right tabular-nums">
                        {row.amount.toLocaleString("en-LK")}
                      </td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[row.status]}`}
                        >
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] lg:col-span-2">
            <div className="flex items-center justify-between border-b border-[var(--uv-border)] px-5 py-4">
              <h2 className="font-semibold">Top Recommendations</h2>
              <Link
                to={TAXWISE_RECOMMENDATIONS}
                className="text-sm text-[var(--uv-accent)] hover:underline"
              >
                View all
              </Link>
            </div>
            <ul className="divide-y divide-[var(--uv-border)]/60">
              {PLACEHOLDER_RECOMMENDATIONS.map((item) => (
                <li key={item.rank} className="flex items-start gap-3 px-5 py-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--uv-accent)]/15 text-xs font-semibold text-[var(--uv-accent)]">
                    {item.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-snug">{item.title}</p>
                    <p className="mt-1 flex items-center gap-1 text-sm font-semibold text-emerald-400">
                      <Star className="h-3.5 w-3.5" />
                      {formatLkr(item.savings)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
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
