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

const BAR_BASELINE = "#9ca3af";
const BAR_BEST = "#14b8a6";

type Props = {
  data: TaxOptBSearchStrategiesResponseV1;
  baselineRow: TaxOptBSearchStrategyRowV1;
  bestRow: TaxOptBSearchStrategyRowV1;
};

function displayStrategyName(raw: string): string {
  return raw.replace(/\bcap_subset_\d+\b/gi, "").replace(/\s+/g, " ").trim();
}

export function ExplorerCharts({ data, baselineRow, bestRow }: Props) {
  const baselineTax = parseDecimalSafe(baselineRow.total_tax);
  const bestTax = parseDecimalSafe(bestRow.total_tax);

  const compareRows =
    baselineTax != null && bestTax != null
      ? [
          { name: "Baseline", tax: baselineTax },
          { name: "Best strategy", tax: bestTax },
        ]
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
    <div className="grid gap-6 lg:grid-cols-2">
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
    </div>
  );
}
