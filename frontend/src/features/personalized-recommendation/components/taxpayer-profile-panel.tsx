import { useQuery } from "@tanstack/react-query";
import { Briefcase, Coins, PiggyBank, TrendingUp, UserRound } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { getProfile, getProfileFeatures } from "../api/profiles";
import { formatLkr } from "../utils/format-lkr";

const TILE_ACCENT = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-900",
  blue: "border-sky-200 bg-sky-50 text-sky-900",
  brown: "border-[#e2d3c1] bg-[#f7f0e8] text-[#6b4a2f]",
  ash: "border-slate-300 bg-slate-100 text-slate-800",
} as const;

function ProfileTile({ label, value, accent }: { label: string; value: string; accent: keyof typeof TILE_ACCENT }) {
  return (
    <div className={cn("rounded-lg border px-3 py-2.5", TILE_ACCENT[accent])}>
      <div className="text-[11px] font-medium uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold">{value}</div>
    </div>
  );
}

function ageFromDob(dob: string): number {
  const d = new Date(dob);
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) age--;
  return age;
}

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

type TaxpayerProfilePanelProps = {
  profileId: string;
  /** When false, skip derived tax-position features (lighter load). Default true. */
  includeFeatures?: boolean;
};

export function TaxpayerProfilePanel({ profileId, includeFeatures = true }: TaxpayerProfilePanelProps) {
  const profileQuery = useQuery({
    queryKey: ["taxpayer-profile", profileId],
    queryFn: () => getProfile(profileId),
    enabled: !!profileId,
  });

  const featuresQuery = useQuery({
    queryKey: ["taxpayer-profile-features", profileId],
    queryFn: () => getProfileFeatures(profileId),
    enabled: !!profileId && includeFeatures,
  });

  const profile = profileQuery.data;

  return (
    <Card className="border-[var(--uv-border)] bg-[var(--uv-bg-card)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <UserRound className="h-5 w-5 text-[var(--uv-accent)]" />
          My Profile
        </CardTitle>
        <CardDescription className="text-[var(--uv-text-muted)]">
          The financial details behind your recommendations.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {profileQuery.isLoading && (
          <p className="text-sm text-[var(--uv-text-muted)]">Loading your profile…</p>
        )}
        {profileQuery.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {(profileQuery.error as Error).message}
          </div>
        )}
        {profile && (
          <>
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg)]/50 p-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[var(--uv-accent)]/15 text-lg font-semibold text-[var(--uv-accent)]">
                {profile.full_name.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="text-lg font-semibold">{profile.full_name}</div>
                <div className="text-sm text-[var(--uv-text-muted)]">
                  {titleCase(profile.occupation)} · {profile.district} · {ageFromDob(profile.date_of_birth)} yrs ·{" "}
                  {titleCase(profile.marital_status)} · {profile.dependents} dependent
                  {profile.dependents === 1 ? "" : "s"}
                </div>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                <Briefcase className="h-4 w-4 text-[var(--uv-text-muted)]" /> Income &amp; expenses (monthly)
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <ProfileTile label="Gross income" value={formatLkr(profile.gross_monthly_income)} accent="green" />
                <ProfileTile label="Expenses" value={formatLkr(profile.monthly_expenses)} accent="green" />
                <ProfileTile label="Debt service" value={formatLkr(profile.monthly_debt_service)} accent="green" />
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                <PiggyBank className="h-4 w-4 text-[var(--uv-text-muted)]" /> Assets &amp; liabilities
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <ProfileTile label="Liquid savings" value={formatLkr(profile.liquid_savings)} accent="blue" />
                <ProfileTile label="Investments" value={formatLkr(profile.existing_investments)} accent="blue" />
                <ProfileTile label="Total debt" value={formatLkr(profile.total_debt)} accent="blue" />
                <ProfileTile label="EPF balance" value={formatLkr(profile.epf_balance)} accent="blue" />
                <ProfileTile label="ETF balance" value={formatLkr(profile.etf_balance)} accent="blue" />
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                <Coins className="h-4 w-4 text-[var(--uv-text-muted)]" /> Insurance &amp; reliefs (annual)
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <ProfileTile
                  label="Health insurance"
                  value={profile.health_insurance ? "Covered" : "Not covered"}
                  accent="brown"
                />
                <ProfileTile
                  label="Life insurance premium"
                  value={formatLkr(profile.life_insurance_premium_annual)}
                  accent="brown"
                />
                <ProfileTile label="Home loan interest" value={formatLkr(profile.home_loan_interest_annual)} accent="brown" />
                <ProfileTile label="Donations" value={formatLkr(profile.donations_annual)} accent="brown" />
                <ProfileTile label="Risk tolerance" value={titleCase(profile.risk_tolerance)} accent="brown" />
                <ProfileTile label="Investment horizon" value={`${profile.investment_horizon_years} yrs`} accent="brown" />
              </div>
            </div>

            {featuresQuery.data && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <TrendingUp className="h-4 w-4 text-[var(--uv-text-muted)]" /> Derived tax position
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <ProfileTile
                    label="Disposable income"
                    value={`${formatLkr(featuresQuery.data.disposable_income_monthly)}/mo`}
                    accent="ash"
                  />
                  <ProfileTile
                    label="Savings rate"
                    value={`${(featuresQuery.data.savings_rate * 100).toFixed(1)}%`}
                    accent="ash"
                  />
                  <ProfileTile
                    label="Baseline tax liability"
                    value={`${formatLkr(featuresQuery.data.baseline_tax_liability_annual)}/yr`}
                    accent="ash"
                  />
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
