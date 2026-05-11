import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type { TaxOptBSearchStrategiesResponseV1, TaxOptBSearchStrategyRowV1 } from "../types";

// Maroon primary color matching the app theme
const BAR_BEST = "#7c2d3e";
const BAR_OTHER = "#c4a8ae";
const BAR_BASELINE = "#d1d5db";

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
          { name: "Without\nclaims", tax: baselineTax },
          { name: "Best\nstrategy", tax: bestTax },
        ]
      : [];

  const topN = Math.min(5, data.rows.length);
  const rankRows = data.rows.slice(0, topN).map((r) => {
    const short = displayStrategyName(r.display_name);
    const savings = -(parseDecimalSafe(r.delta_total_tax_vs_baseline) ?? 0);
    return {
      name: short.length > 28 ? `${short.slice(0, 26)}…` : short,
      savings: Math.max(0, savings),
      isBest: r.rank === 1,
      isBaseline: r.candidate_id === data.baseline_candidate_id,
    };
  });

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Chart 1 — Baseline vs Best */}
      <div className="min-h-[280px] rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold text-foreground">Before vs. after claiming reliefs</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          How much tax you pay with and without the best strategy.
        </p>
        {compareRows.length > 0 ? (
          <div className="mt-4 h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={compareRows} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} width={60}>
                  <Label
                    value="Tax (LKR)"
                    angle={-90}
                    position="insideLeft"
                    className="fill-muted-foreground text-xs"
                  />
                </YAxis>
                <Tooltip
                  formatter={(v: number) => [formatLkrAmount(v), "Tax payable"]}
                  contentStyle={{ borderRadius: 8, fontSize: 12 }}
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

      {/* Chart 2 — How much each strategy saves */}
      <div className="min-h-[280px] rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold text-foreground">How much each strategy saves you</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Tax saving vs. claiming nothing — darker bar is the AI recommended strategy.
        </p>
        {rankRows.length > 0 ? (
          <div className="mt-4 h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rankRows}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis type="number" tick={{ fontSize: 11 }}>
                  <Label
                    value="You save (LKR)"
                    position="insideBottom"
                    offset={-4}
                    className="fill-muted-foreground text-xs"
                  />
                </XAxis>
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: number) => [formatLkrAmount(v), "Tax saved"]}
                  contentStyle={{ borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="savings" radius={[0, 6, 6, 0]}>
                  {rankRows.map((entry, i) => (
                    <Cell
                      key={`${entry.name}-${i}`}
                      fill={entry.isBaseline ? BAR_BASELINE : entry.isBest ? BAR_BEST : BAR_OTHER}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
      </div>
    </div>
  );
}
