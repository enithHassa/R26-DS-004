import { useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  CheckCircle2,
  Coins,
  Landmark,
  LogOut,
  Percent,
  PiggyBank,
  Receipt,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  UserRound,
  Wallet,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { generateRecommendations, submitRecommendationFeedback } from "../api/recommendations";
import { simulateImpact } from "../api/impact";
import { getProfile, getProfileFeatures } from "../api/profiles";
import { ImpactCharts } from "../components/impact-charts";
import { ImpactSummaryCards } from "../components/impact-summary-cards";
import { AdoptionChip, RiskChip, SavingsChip } from "../components/metric-chips";
import { recommendationCodeToCatalog, STRATEGY_PLAIN_SUMMARY } from "../constants/strategies";
import { useUserSessionStore } from "../store/user-session-store";
import { formatLkr } from "../utils/format-lkr";

const PORTAL_TABS = [
  { key: "recommendations", label: "Recommendations", icon: Sparkles },
  { key: "impact", label: "Financial Impact", icon: TrendingUp },
  { key: "profile", label: "My Profile", icon: UserRound },
] as const;

type PortalTab = (typeof PORTAL_TABS)[number]["key"];

const DOT_GRID_BG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='white' fill-opacity='0.14'/%3E%3C/svg%3E";

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

function tabFromSearch(value: string | null): PortalTab {
  if (value === "profile" || value === "impact" || value === "recommendations") return value;
  return "recommendations";
}

export function UserPortalPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);
  const [activeTab, setActiveTab] = useState<PortalTab>(() => tabFromSearch(searchParams.get("tab")));

  const selectTab = (key: PortalTab) => {
    setActiveTab(key);
    setSearchParams(key === "recommendations" ? {} : { tab: key }, { replace: true });
  };
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "accepted" | "dismissed">>({});

  const profileQuery = useQuery({
    queryKey: ["portal-profile", profileId],
    queryFn: () => getProfile(profileId!),
    enabled: !!profileId,
  });

  const featuresQuery = useQuery({
    queryKey: ["portal-features", profileId],
    queryFn: () => getProfileFeatures(profileId!),
    enabled: !!profileId && activeTab === "profile",
  });

  const recommendationsQuery = useQuery({
    queryKey: ["portal-recommendations", profileId],
    queryFn: () => generateRecommendations({ profile_id: profileId!, top_k: 5 }),
    enabled: !!profileId,
    // Recommendations are recomputed live from the current profile on every
    // call, so always refetch on mount — otherwise a stale cached result
    // could hide changes an auditor (or this user's own answers) just made.
    refetchOnMount: "always",
  });

  const feedbackMutation = useMutation({
    mutationFn: submitRecommendationFeedback,
    onSuccess: (_, variables) => {
      setFeedbackGiven((prev) => ({
        ...prev,
        [variables.recommendation_item_id]: variables.accepted ? "accepted" : "dismissed",
      }));
    },
  });

  const topStrategyCode = recommendationsQuery.data?.items[0]
    ? recommendationCodeToCatalog(recommendationsQuery.data.items[0].strategy.code)
    : null;

  const impactQuery = useQuery({
    queryKey: ["portal-impact", profileId, topStrategyCode],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId!,
        strategy_code: topStrategyCode,
        horizon_years: 10,
        n_paths: 1000,
        random_seed: 42,
      }),
    enabled: !!profileId && !!topStrategyCode,
  });

  if (!isAuthenticated || !profileId) {
    return <Navigate to="/login" replace />;
  }

  const recommendations = recommendationsQuery.data?.items ?? [];
  const profile = profileQuery.data;

  return (
    <div
      className="relative min-h-screen overflow-hidden"
      style={{
        background:
          "radial-gradient(1100px circle at 10% 0%, color-mix(in srgb, var(--tax-accent) 40%, transparent) 0%, transparent 45%)," +
          "radial-gradient(900px circle at 95% 100%, color-mix(in srgb, var(--primary) 55%, transparent) 0%, transparent 50%)," +
          "linear-gradient(165deg, #241419 0%, #1b1013 60%, #201317 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{ backgroundImage: `url("${DOT_GRID_BG}")`, backgroundSize: "40px 40px" }}
        aria-hidden
      />
      <Landmark className="pointer-events-none absolute -left-10 -top-10 h-64 w-64 text-white/[0.05]" strokeWidth={0.75} />
      <Percent className="pointer-events-none absolute right-16 top-24 h-24 w-24 rotate-12 text-white/[0.06]" strokeWidth={1} />
      <Receipt className="pointer-events-none absolute bottom-16 right-24 h-32 w-32 -rotate-6 text-white/[0.05]" strokeWidth={0.75} />
      <Coins className="pointer-events-none absolute -bottom-10 left-1/3 h-40 w-40 text-white/[0.04]" strokeWidth={0.75} />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-7xl">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-white/10 bg-white/[0.06] p-4 backdrop-blur-md md:flex">
          <div className="mb-8 flex items-center gap-2 px-2 text-white">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
              <Wallet className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-tight">AI Tax Advisory</div>
              <div className="text-[11px] text-white/60">Taxpayer Portal</div>
            </div>
          </div>

          <div className="mb-6 rounded-xl border border-white/10 bg-white/5 p-3">
            <div className="text-[11px] uppercase tracking-wide text-white/50">Signed in as</div>
            <div className="truncate text-sm font-semibold text-white">{fullName ?? profile?.full_name}</div>
          </div>

          <nav className="flex flex-col gap-1">
            {PORTAL_TABS.map((tab) => {
              const Icon = tab.icon;
              const active = tab.key === activeTab;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => selectTab(tab.key)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-white text-foreground shadow-sm"
                      : "text-white/70 hover:bg-white/10 hover:text-white",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={logout}
            className="mt-auto flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </aside>

        <main className="min-w-0 flex-1 p-4 md:p-8">
          <div className="mx-auto max-w-4xl space-y-6 rounded-2xl border border-border/60 bg-background p-4 shadow-xl md:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Link
                  to="/taxwise"
                  className="mb-2 inline-block text-sm text-muted-foreground hover:text-foreground"
                >
                  ← Back to dashboard
                </Link>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {fullName ? `Hi, ${fullName.split(" ")[0]}` : "Your Tax Advisory Summary"}
                </h1>
                <p className="text-muted-foreground">
                  {fullName
                    ? "Here's your Tax Advisory Summary — a simple view of what could save you money and what it means for your future."
                    : "A simple view of what could save you money and what it means for your future."}
                </p>
              </div>
              <button
                type="button"
                onClick={logout}
                className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted/50 md:hidden"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>

            {activeTab === "recommendations" && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5 text-primary" />
                  Recommended for you
                </CardTitle>
                <CardDescription>
                  A few ways to pay less tax, picked for your situation — in plain terms.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {recommendationsQuery.isLoading && (
                  <p className="text-sm text-muted-foreground">Loading your recommendations…</p>
                )}
                {recommendationsQuery.isError && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                    {(recommendationsQuery.error as Error).message}
                  </div>
                )}
                {!recommendationsQuery.isLoading && recommendations.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No recommendations are available for your profile yet.
                  </p>
                )}
                {recommendations.map((item) => (
                  <div key={item.id} className="rounded-lg border bg-card p-4 shadow-sm">
                    <div className="flex flex-wrap items-start gap-2">
                      <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                        {item.rank}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold">{item.strategy.name}</div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {STRATEGY_PLAIN_SUMMARY[recommendationCodeToCatalog(item.strategy.code)] ??
                            item.strategy.description}
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 pl-8">
                      <SavingsChip value={formatLkr(item.estimated_annual_savings)} />
                      <AdoptionChip probability={item.adoption_probability} />
                      <RiskChip score={item.risk_score} />
                    </div>

                    {item.explanation?.narrative && (
                      <div className="mt-3 ml-8 rounded-md border-l-4 border-l-primary/60 bg-muted/40 p-3 text-sm leading-relaxed">
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          What this means for you
                        </div>
                        {item.explanation.narrative}
                      </div>
                    )}

                    <div className="mt-3 ml-8 flex items-center gap-2">
                      {feedbackGiven[item.id] ? (
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                          {feedbackGiven[item.id] === "accepted"
                            ? "Marked as done — thanks, this helps us improve future recommendations."
                            : "Marked as not for you — thanks for the feedback."}
                        </span>
                      ) : (
                        <>
                          <button
                            type="button"
                            disabled={feedbackMutation.isPending}
                            onClick={() =>
                              feedbackMutation.mutate({
                                recommendation_item_id: item.id,
                                accepted: true,
                              })
                            }
                            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800 transition-colors hover:bg-emerald-100 disabled:opacity-50"
                          >
                            <ThumbsUp className="h-3.5 w-3.5" />
                            I've done this
                          </button>
                          <button
                            type="button"
                            disabled={feedbackMutation.isPending}
                            onClick={() =>
                              feedbackMutation.mutate({
                                recommendation_item_id: item.id,
                                accepted: false,
                              })
                            }
                            className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 disabled:opacity-50"
                          >
                            <ThumbsDown className="h-3.5 w-3.5" />
                            Not for me
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
            )}

            {activeTab === "impact" && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="h-5 w-5 text-primary" />
                  What this could mean for you
                </CardTitle>
                <CardDescription>
                  {topStrategyCode
                    ? "A plain-language look at where you could stand in 10 years if you follow our top recommendation."
                    : "A plain-language look at where you could stand in 10 years."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {impactQuery.isLoading && (
                  <p className="text-sm text-muted-foreground">Running your projection…</p>
                )}
                {impactQuery.isError && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                    {(impactQuery.error as Error).message}
                  </div>
                )}
                {impactQuery.data && (
                  <>
                    <ImpactSummaryCards
                      summary={impactQuery.data.summary}
                      hasStrategy={Boolean(impactQuery.data.strategy_path)}
                    />
                    <div className="mt-6">
                      <ImpactCharts result={impactQuery.data} />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
            )}

            {activeTab === "profile" && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <UserRound className="h-5 w-5 text-primary" />
                  My Profile
                </CardTitle>
                <CardDescription>The financial details behind your recommendations.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {profileQuery.isLoading && (
                  <p className="text-sm text-muted-foreground">Loading your profile…</p>
                )}
                {profileQuery.isError && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                    {(profileQuery.error as Error).message}
                  </div>
                )}
                {profile && (
                  <>
                    <div className="flex flex-wrap items-center gap-4 rounded-xl border bg-muted/30 p-4">
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary">
                        {profile.full_name.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-lg font-semibold">{profile.full_name}</div>
                        <div className="text-sm text-muted-foreground">
                          {titleCase(profile.occupation)} · {profile.district} · {ageFromDob(profile.date_of_birth)} yrs ·{" "}
                          {titleCase(profile.marital_status)} · {profile.dependents} dependent
                          {profile.dependents === 1 ? "" : "s"}
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                        <Briefcase className="h-4 w-4 text-muted-foreground" /> Income &amp; expenses (monthly)
                      </div>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        <ProfileTile label="Gross income" value={formatLkr(profile.gross_monthly_income)} accent="green" />
                        <ProfileTile label="Expenses" value={formatLkr(profile.monthly_expenses)} accent="green" />
                        <ProfileTile label="Debt service" value={formatLkr(profile.monthly_debt_service)} accent="green" />
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                        <PiggyBank className="h-4 w-4 text-muted-foreground" /> Assets &amp; liabilities
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
                      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                        <Coins className="h-4 w-4 text-muted-foreground" /> Insurance &amp; reliefs (annual)
                      </div>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        <ProfileTile
                          label="Health insurance"
                          value={profile.health_insurance ? "Covered" : "Not covered"}
                          accent="brown"
                        />
                        <ProfileTile label="Life insurance premium" value={formatLkr(profile.life_insurance_premium_annual)} accent="brown" />
                        <ProfileTile label="Home loan interest" value={formatLkr(profile.home_loan_interest_annual)} accent="brown" />
                        <ProfileTile label="Donations" value={formatLkr(profile.donations_annual)} accent="brown" />
                        <ProfileTile label="Risk tolerance" value={titleCase(profile.risk_tolerance)} accent="brown" />
                        <ProfileTile label="Investment horizon" value={`${profile.investment_horizon_years} yrs`} accent="brown" />
                      </div>
                    </div>

                    {featuresQuery.data && (
                      <div>
                        <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                          <TrendingUp className="h-4 w-4 text-muted-foreground" /> Derived tax position
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
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
