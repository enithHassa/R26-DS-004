import { useMemo } from "react";
import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { HybridResultItem } from "../../api/hybrid";
import {
  AUDITOR_IMPACT_HORIZON_YEARS,
} from "../../constants/auditor-impact";
import type { ImpactSimulationResponse } from "../../types";
import { formatLkr, parseLkr } from "../../utils/format-lkr";
import { AuditorImpactVisualizations } from "./impact-visualizations";
import { AuditorTaxLiabilityChart, buildTaxLiabilityChartRows } from "./tax-liability-chart";

export function riskLabel(score: number): string {
  if (score >= 0.15) return "High";
  if (score >= 0.08) return "Medium";
  return "Low";
}

export function riskTone(score: number): string {
  if (score >= 0.15) return "text-rose-600";
  if (score >= 0.08) return "text-amber-600";
  return "text-emerald-600";
}

export function buildImpactTableRows(sim: ImpactSimulationResponse) {
  if (!sim.strategy_path) return [];

  let cumulative = 0;
  return sim.baseline.slice(0, sim.horizon_years).map((base, i) => {
    const strat = sim.strategy_path![i];
    const baseTax = parseLkr(base.projected_tax_liability);
    const stratTax = parseLkr(strat.projected_tax_liability);
    const annualSaving = baseTax - stratTax;
    cumulative += annualSaving;
    return {
      year: base.year,
      taxNoStrategy: baseTax,
      taxWithStrategy: stratTax,
      annualSaving,
      cumulativeSaving: cumulative,
    };
  });
}

type Props = {
  primaryResult?: ImpactSimulationResponse;
  selectedItem?: HybridResultItem;
  strategyName: string;
  rank?: number;
  isLoading?: boolean;
  error?: string | null;
  compactChart?: boolean;
};

export function AuditorImpactDetailSections({
  primaryResult,
  selectedItem,
  strategyName,
  rank,
  isLoading,
  error,
  compactChart = false,
}: Props) {
  const adoptionPct = selectedItem
    ? Math.round(selectedItem.adoption_probability * 100)
    : null;
  const riskScore = selectedItem?.risk_score ?? 0;
  const compliancePct = selectedItem ? Math.round(selectedItem.confidence * 100) : null;
  const displayRank = rank ?? selectedItem?.rank ?? 1;

  const chartRows = useMemo(
    () => (primaryResult ? buildTaxLiabilityChartRows(primaryResult) : []),
    [primaryResult],
  );

  const rows = primaryResult ? buildImpactTableRows(primaryResult) : [];
  const totalSaving = rows.reduce((sum, r) => sum + r.annualSaving, 0);
  const totalBaselineTax = rows.reduce((sum, r) => sum + r.taxNoStrategy, 0);
  const projectedRoi =
    totalBaselineTax > 0 ? ((totalSaving / totalBaselineTax) * 100).toFixed(1) : "—";

  const startYear = rows[0]?.year ?? new Date().getFullYear();
  const endYear = rows[rows.length - 1]?.year ?? startYear + AUDITOR_IMPACT_HORIZON_YEARS - 1;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Running {AUDITOR_IMPACT_HORIZON_YEARS}-year Monte Carlo projection…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!primaryResult || chartRows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Select a recommendation to run the impact projection.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-border/70 shadow-sm">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Strategy #{displayRank}
            </p>
            <p className="font-semibold">{strategyName}</p>
            <p className="text-xs text-muted-foreground">
              {startYear}–{endYear} · {AUDITOR_IMPACT_HORIZON_YEARS}-year horizon
            </p>
          </div>
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Adoption Probability
              </p>
              <p className="font-bold text-sky-700">
                {adoptionPct != null ? `${adoptionPct}%` : "—"}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Risk Level</p>
              <p className={`font-bold ${riskTone(riskScore)}`}>{riskLabel(riskScore)}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Compliance</p>
              <p className="font-bold text-emerald-700">
                {compliancePct != null ? `${compliancePct}%` : "—"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <AuditorTaxLiabilityChart
        rows={chartRows}
        strategyLabel={strategyName}
        title={`${AUDITOR_IMPACT_HORIZON_YEARS}-Year Tax Liability Projection`}
        subtitle="Red = no strategy · Green = with this strategy · Shaded area = uncertainty range"
        compact={compactChart}
        showMonteCarloToggle={!compactChart}
      />

      <AuditorImpactVisualizations result={primaryResult} strategyName={strategyName} />

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card className="overflow-hidden border-border/70 shadow-sm">
            <CardHeader className="border-b py-3">
              <CardTitle className="text-sm">Detailed Impact</CardTitle>
              <p className="text-xs text-muted-foreground">
                Year-by-year tax: baseline vs this strategy, plus savings (negative = extra tax)
              </p>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="px-4 py-3 font-medium">Year</th>
                      <th className="px-4 py-3 font-medium">Tax (No Strategy)</th>
                      <th className="px-4 py-3 font-medium">Tax (With Strategy)</th>
                      <th className="px-4 py-3 font-medium">Annual Saving</th>
                      <th className="px-4 py-3 font-medium">Cumulative Saving</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.year} className="border-b border-border/50">
                        <td className="px-4 py-3 font-medium">{row.year}</td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {formatLkr(row.taxNoStrategy)}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-emerald-700">
                          {formatLkr(row.taxWithStrategy)}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-amber-700">
                          {formatLkr(row.annualSaving)}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{formatLkr(row.cumulativeSaving)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4 lg:col-span-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Key Stats
          </p>
          <Card className="border-emerald-200 bg-emerald-50/50 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">
                Total {AUDITOR_IMPACT_HORIZON_YEARS}-Year Saving
              </p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-700">
                {formatLkr(totalSaving)}
              </p>
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Adoption Probability</p>
              <p className="mt-1 text-xl font-bold text-sky-700">
                {adoptionPct != null ? `${adoptionPct}%` : "—"}
              </p>
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Risk Level</p>
              <p className={`mt-1 text-xl font-bold ${riskTone(riskScore)}`}>
                {riskLabel(riskScore)}
              </p>
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Projected ROI</p>
              <p className="mt-1 text-xl font-bold text-amber-700">{projectedRoi}%</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
