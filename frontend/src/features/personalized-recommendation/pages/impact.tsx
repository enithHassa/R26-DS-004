import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { simulateImpact } from "../api/impact";
import { generateRecommendations } from "../api/recommendations";
import { ExplainPanel } from "../components/explain-panel";
import { ImpactCharts } from "../components/impact-charts";
import { ImpactExtraCharts } from "../components/impact-extra-charts";
import { ImpactScenarioPanel } from "../components/impact-scenario-panel";
import { ImpactSummaryCards } from "../components/impact-summary-cards";
import { ProfilePicker } from "../components/profile-picker";
import { CATALOG_STRATEGIES, recommendationCodeToCatalog } from "../constants/strategies";
import { useDashboardStore } from "../store/dashboard-store";
import { formatLkr } from "../utils/format-lkr";

export function ImpactPage() {
  const { strategyId: routeStrategy } = useParams();
  const [searchParams] = useSearchParams();

  const activeProfileId = useDashboardStore((s) => s.activeProfileId);
  const impactScenario = useDashboardStore((s) => s.impactScenario);
  const toImpactScenarioPayload = useDashboardStore((s) => s.toImpactScenarioPayload);

  const [profileId, setProfileId] = useState(searchParams.get("profile") ?? activeProfileId ?? "");
  const [strategyCode, setStrategyCode] = useState("");

  useEffect(() => {
    if (activeProfileId && !profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  useEffect(() => {
    const fromRoute = routeStrategy && routeStrategy !== "new" ? routeStrategy : "";
    const fromQuery = searchParams.get("strategy") ?? "";
    const code = fromRoute || fromQuery;
    if (code) setStrategyCode(recommendationCodeToCatalog(code));
  }, [routeStrategy, searchParams]);

  const recsQuery = useQuery({
    queryKey: ["recommendations", "impact-strategies", profileId],
    queryFn: () => generateRecommendations({ profile_id: profileId, top_k: 10 }),
    enabled: profileId.length > 0,
  });

  const strategyOptions = useMemo(() => {
    const fromRecs =
      recsQuery.data?.items.map((item) => ({
        code: recommendationCodeToCatalog(item.strategy.code),
        label: item.strategy.name,
      })) ?? [];
    if (fromRecs.length > 0) return fromRecs;
    return CATALOG_STRATEGIES.map((s) => ({ code: s.code, label: s.label }));
  }, [recsQuery.data]);

  const simulateMutation = useMutation({
    mutationFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: strategyCode || null,
        horizon_years: impactScenario.horizonYears,
        n_paths: impactScenario.nPaths,
        random_seed: 42,
        scenario: strategyCode ? toImpactScenarioPayload(true) : toImpactScenarioPayload(false),
      }),
  });

  const result = simulateMutation.data;
  const canRun = profileId.length > 0 && !simulateMutation.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Predictive impact</h1>
        <p className="text-muted-foreground">
          Monte Carlo fan charts, tax liability curves, and scenario toggles (FR7, FR8).
        </p>
      </div>

      <Card className="max-w-4xl">
        <CardHeader>
          <CardTitle>Simulation setup</CardTitle>
          <CardDescription>
            Profile, optional strategy, and stochastic scenario parameters (persisted in session).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <ProfilePicker value={profileId} onChange={setProfileId} />
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Strategy (optional)</Label>
              <Select
                value={strategyCode}
                onChange={(e) => setStrategyCode(e.target.value)}
                disabled={!profileId}
              >
                <option value="">Baseline only (no strategy)</option>
                {strategyOptions.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.label}
                  </option>
                ))}
              </Select>
              {!profileId && (
                <p className="text-xs text-muted-foreground">
                  <Link to="/profile" className="underline">
                    Create a profile
                  </Link>{" "}
                  first.
                </p>
              )}
            </div>
          </div>

          <div>
            <h3 className="mb-3 text-sm font-semibold">Scenario toggles</h3>
            <ImpactScenarioPanel />
          </div>

          {simulateMutation.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {(simulateMutation.error as Error).message}
            </div>
          )}

          <Button onClick={() => simulateMutation.mutate()} disabled={!canRun}>
            {simulateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Simulating…
              </>
            ) : (
              <>
                <BarChart3 className="h-4 w-4" />
                Run Monte Carlo simulation
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <>
          <ImpactSummaryCards summary={result.summary} hasStrategy={Boolean(result.strategy_path)} />
          <ImpactCharts result={result} />
          <ImpactExtraCharts result={result} />
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Year-by-year liability & wealth (median path)</CardTitle>
              <CardDescription>
                P50 projections from {result.n_paths.toLocaleString()} paths over {result.horizon_years} years.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Year</th>
                    <th className="pb-2 pr-4">Salary</th>
                    <th className="pb-2 pr-4">Tax</th>
                    <th className="pb-2 pr-4">Savings</th>
                    <th className="pb-2">Net worth</th>
                  </tr>
                </thead>
                <tbody>
                  {result.baseline.map((row, i) => {
                    const strat = result.strategy_path?.[i];
                    return (
                      <tr key={row.year} className="border-b border-border/50">
                        <td className="py-2 pr-4 font-medium">{row.year}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatLkr(row.projected_salary)}</td>
                        <td className="py-2 pr-4 tabular-nums">
                          {formatLkr(row.projected_tax_liability)}
                          {strat && (
                            <span className="ml-1 text-xs text-emerald-700">
                              → {formatLkr(strat.projected_tax_liability)}
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-4 tabular-nums">{formatLkr(row.projected_savings)}</td>
                        <td className="py-2 tabular-nums">
                          {formatLkr(row.net_worth)}
                          {strat && (
                            <span className="ml-1 text-xs text-emerald-700">
                              → {formatLkr(strat.net_worth)}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}

      {profileId && strategyCode && (
        <ExplainPanel
          profileId={profileId}
          strategyCode={strategyCode}
          strategyLabel={strategyOptions.find((s) => s.code === strategyCode)?.label}
        />
      )}
    </div>
  );
}
