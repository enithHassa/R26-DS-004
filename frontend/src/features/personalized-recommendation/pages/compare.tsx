import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { GitCompare, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { compareImpactStrategies } from "../api/impact";
import { CompareCharts } from "../components/compare-charts";
import { PageHeader } from "../components/page-header";
import { ProfilePicker } from "../components/profile-picker";
import { CATALOG_STRATEGIES } from "../constants/strategies";
import { useDashboardStore, useActiveProfileId } from "../store/dashboard-store";
import type { ImpactSimulationResponse } from "../types";
import { formatLkr } from "../utils/format-lkr";

export function ComparePage() {
  const [searchParams] = useSearchParams();
  const activeProfileId = useActiveProfileId();
  const impactScenario = useDashboardStore((s) => s.impactScenario);

  const [profileId, setProfileId] = useState(searchParams.get("profile") ?? activeProfileId ?? "");
  const [selected, setSelected] = useState<string[]>([
    "S001_health_life_premium_optimisation",
    "S003_charity_optimisation",
  ]);

  useEffect(() => {
    if (activeProfileId && !profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  const compareMutation = useMutation({
    mutationFn: () =>
      compareImpactStrategies({
        profile_id: profileId,
        strategy_codes: selected,
        horizon_years: impactScenario.horizonYears,
      }),
  });

  const results = compareMutation.data ?? [];
  const canCompare = profileId && selected.length >= 1 && !compareMutation.isPending;

  const labels = selected.map(
    (code) => CATALOG_STRATEGIES.find((s) => s.code === code)?.label ?? code,
  );

  function toggleStrategy(code: string) {
    setSelected((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : prev.length < 5 ? [...prev, code] : prev,
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader icon={GitCompare} title="Compare strategies" />

      <Card className="max-w-4xl border-t-4 border-t-primary/70">
        <CardHeader>
          <CardTitle>Select strategies</CardTitle>
          <CardDescription>Up to 5 strategies · horizon from scenario settings ({impactScenario.horizonYears}y).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ProfilePicker value={profileId} onChange={setProfileId} />

          <div className="flex flex-wrap gap-2">
            {CATALOG_STRATEGIES.map((s) => {
              const on = selected.includes(s.code);
              return (
                <button
                  key={s.code}
                  type="button"
                  onClick={() => toggleStrategy(s.code)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-all ${
                    on
                      ? "border-primary bg-primary text-primary-foreground shadow-sm"
                      : "border-border bg-muted/30 text-muted-foreground hover:border-primary/40 hover:bg-muted/50"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>

          {compareMutation.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {(compareMutation.error as Error).message}
            </div>
          )}

          <Button onClick={() => compareMutation.mutate()} disabled={!canCompare}>
            {compareMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Comparing…
              </>
            ) : (
              <>
                <GitCompare className="h-4 w-4" />
                Compare {selected.length} strategies
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {results.length > 0 && (
        <>
          <ComparisonTable results={results} labels={labels} />
          <CompareCharts results={results} labels={labels} />
          <div className="grid gap-6 lg:grid-cols-2">
            {results.map((r, idx) => {
              const code = selected[idx] ?? "";
              const label = labels[idx] ?? code;
              return (
                <Card key={r.run_id}>
                  <CardHeader>
                    <CardTitle className="text-base">{label}</CardTitle>
                    <CardDescription>
                      Expected savings {formatLkr(r.summary.expected_total_savings)} · P(gain){" "}
                      {(r.summary.probability_of_net_gain * 100).toFixed(0)}%
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="text-sm text-muted-foreground">
                    Net worth P50 at horizon: {formatLkr(r.net_worth_bands.at(-1)?.p50 ?? "0")}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function ComparisonTable({
  results,
  labels,
}: {
  results: ImpactSimulationResponse[];
  labels: string[];
}) {
  const rows = results.map((r, i) => ({
    key: r.run_id,
    label: labels[i] ?? `Strategy ${i + 1}`,
    savings: formatLkr(r.summary.expected_total_savings),
    netWorth: formatLkr(r.summary.expected_net_worth),
    probGain: `${(r.summary.probability_of_net_gain * 100).toFixed(1)}%`,
    var: formatLkr(r.summary.value_at_risk_p10),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Summary table</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4">Strategy</th>
              <th className="pb-2 pr-4">Expected tax savings</th>
              <th className="pb-2 pr-4">Expected net worth</th>
              <th className="pb-2 pr-4">P(net gain)</th>
              <th className="pb-2">VaR P10</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b border-border/50">
                <td className="py-2 pr-4 font-medium">{row.label}</td>
                <td className="py-2 pr-4 tabular-nums">{row.savings}</td>
                <td className="py-2 pr-4 tabular-nums">{row.netWorth}</td>
                <td className="py-2 pr-4">{row.probGain}</td>
                <td className="py-2 tabular-nums">{row.var}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
