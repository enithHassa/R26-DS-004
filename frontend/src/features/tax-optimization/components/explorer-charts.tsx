import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type { TaxOptBSearchStrategiesResponseV1, TaxOptBSearchStrategyRowV1 } from "../types";

const BAR_BASELINE = "#9ca3af";
const BAR_BEST = "#14b8a6";

type Props = {
  data: TaxOptBSearchStrategiesResponseV1;
  baselineRow: TaxOptBSearchStrategyRowV1;
  bestRow: TaxOptBSearchStrategyRowV1;
  mlAssisted?: boolean;
};

function displayStrategyName(raw: string): string {
  return raw.replace(/\bcap_subset_\d+\b/gi, "").replace(/\s+/g, " ").trim();
}

export function ExplorerCharts({ data, baselineRow, bestRow, mlAssisted = false }: Props) {
  const baselineTax = parseDecimalSafe(baselineRow.total_tax);
  const bestTax = parseDecimalSafe(bestRow.total_tax);

  const compareRows =
    baselineTax != null && bestTax != null
      ? [
          { name: "Baseline", tax: baselineTax },
          { name: "Best strategy", tax: bestTax },
        ]
      : [];

  // Pareto scatter: derive savings_norm and liquidity_norm from ml_score
  // utility = 0.7 * savings_norm - 0.3 * liquidity_norm  => liquidity_norm = (0.7 * savings_norm - ml_score) / 0.3
  const paretoPoints = mlAssisted
    ? data.rows
        .filter((r) => r.ml_score != null && r.delta_total_tax_vs_baseline != null)
        .map((r) => {
          const gross = parseDecimalSafe(r.breakdown?.gross_income_lkr) ?? 1;
          const savings = -(parseDecimalSafe(r.delta_total_tax_vs_baseline) ?? 0);
          const savingsNorm = gross > 0 ? savings / gross : 0;
          const mlScore = parseDecimalSafe(r.ml_score) ?? 0;
          const liquidityNorm = Math.max(0, (0.7 * savingsNorm - mlScore) / 0.3);
          return {
            savingsPct: +(savingsNorm * 100).toFixed(2),
            liquidityPct: +(liquidityNorm * 100).toFixed(2),
            isAiTop: r.rank === 1,
            isRuleTop: r.rule_only_rank === 1,
            name: r.display_name,
          };
        })
    : [];

  const topN = Math.min(5, data.rows.length);
  const rankRows = data.rows.slice(0, topN).map((r) => {
    const short = displayStrategyName(r.display_name);
    return {
      name: short.length > 32 ? `${short.slice(0, 30)}…` : short,
      tax: parseDecimalSafe(r.total_tax) ?? 0,
      isBest: r.rank === 1,
    };
  });

  return (
    <div className={`grid gap-6 ${mlAssisted && paretoPoints.length > 0 ? "lg:grid-cols-3" : "lg:grid-cols-2"}`}>
      <div className="min-h-[260px] rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold text-foreground">Baseline vs best</h3>
        <p className="mt-1 text-xs text-muted-foreground">Total tax payable (LKR).</p>
        {compareRows.length > 0 ? (
          <div className="mt-4 h-[240px] w-full min-h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={compareRows} margin={{ top: 12, right: 12, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={52}>
                  <Label value="Tax (LKR)" angle={-90} position="insideLeft" className="fill-muted-foreground text-xs" />
                </YAxis>
                <Tooltip
                  formatter={(v: number) => [formatLkrAmount(v), "Tax"]}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--color-border-soft)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="tax" radius={[6, 6, 0, 0]}>
                  <Cell fill={BAR_BASELINE} />
                  <Cell fill={BAR_BEST} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">Insufficient data for chart.</p>
        )}
      </div>

      <div className="min-h-[260px] rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold text-foreground">Top strategies</h3>
        <p className="mt-1 text-xs text-muted-foreground">Lowest-tax options (top {topN}).</p>
        {rankRows.length > 0 ? (
          <div className="mt-4 h-[240px] w-full min-h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rankRows}
                layout="vertical"
                margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis type="number" tick={{ fontSize: 11 }}>
                  <Label
                    value="Tax (LKR)"
                    position="insideBottom"
                    offset={-4}
                    className="fill-muted-foreground text-xs"
                  />
                </XAxis>
                <YAxis type="category" dataKey="name" width={128} tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: number) => [formatLkrAmount(v), "Tax"]}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--color-border-soft)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="tax" radius={[0, 6, 6, 0]}>
                  {rankRows.map((entry, i) => (
                    <Cell key={`${entry.name}-${i}`} fill={entry.isBest ? BAR_BEST : BAR_BASELINE} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
      </div>

      {mlAssisted && paretoPoints.length > 0 && (
        <div className="min-h-[260px] rounded-xl border border-border/80 bg-card p-5 shadow-sm">
          <h3 className="text-base font-semibold text-foreground">Savings vs. Liquidity Cost</h3>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span>Pareto trade-off (% of income)</span>
            <span className="flex items-center gap-1">
              <svg width="10" height="10"><circle cx="5" cy="5" r="5" fill="#16a34a" /></svg>
              AI top-1
            </span>
            <span className="flex items-center gap-1">
              <svg width="10" height="10"><circle cx="5" cy="5" r="5" fill="#ea580c" /></svg>
              Rule top-1
            </span>
          </div>
          <div className="mt-4 h-[240px] w-full min-h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 12, right: 16, left: 8, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis
                  type="number"
                  dataKey="liquidityPct"
                  name="Liquidity cost"
                  tick={{ fontSize: 10 }}
                  label={{ value: "Liquidity cost (% income)", position: "insideBottom", offset: -12, fontSize: 10 }}
                />
                <YAxis
                  type="number"
                  dataKey="savingsPct"
                  name="Tax savings"
                  tick={{ fontSize: 10 }}
                  width={44}
                  label={{ value: "Savings (%)", angle: -90, position: "insideLeft", fontSize: 10 }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  formatter={(v: number, name: string) => [`${v.toFixed(2)}%`, name]}
                  contentStyle={{ borderRadius: 8, fontSize: 11 }}
                />
                {/* grey background dots first */}
                <Scatter
                  data={paretoPoints.filter((p) => !p.isAiTop && !p.isRuleTop)}
                  shape={(props: { cx?: number; cy?: number }) => (
                    <circle cx={props.cx ?? 0} cy={props.cy ?? 0} r={4} fill="#9ca3af" fillOpacity={0.5} />
                  )}
                />
                {/* orange rule top-1 on top */}
                <Scatter
                  data={paretoPoints.filter((p) => p.isRuleTop && !p.isAiTop)}
                  shape={(props: { cx?: number; cy?: number }) => (
                    <circle cx={props.cx ?? 0} cy={props.cy ?? 0} r={8} fill="#ea580c" fillOpacity={0.9} />
                  )}
                />
                {/* green AI top-1 on top of everything */}
                <Scatter
                  data={paretoPoints.filter((p) => p.isAiTop)}
                  shape={(props: { cx?: number; cy?: number }) => (
                    <circle cx={props.cx ?? 0} cy={props.cy ?? 0} r={8} fill="#16a34a" fillOpacity={0.9} />
                  )}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
