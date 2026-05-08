import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type { TaxOptBSearchStrategiesResponseV1, TaxOptBSearchStrategyRowV1 } from "../types";

const BAR_BASELINE = "var(--color-text-muted)";
const BAR_PRIMARY = "var(--primary)";

type Props = {
  data: TaxOptBSearchStrategiesResponseV1;
  baselineRow: TaxOptBSearchStrategyRowV1;
  bestRow: TaxOptBSearchStrategyRowV1;
};

export function ExplorerCharts({ data, baselineRow, bestRow }: Props) {
  const baselineTax = parseDecimalSafe(baselineRow.total_tax);
  const bestTax = parseDecimalSafe(bestRow.total_tax);

  const compareRows =
    baselineTax != null && bestTax != null
      ? [
          { name: "Baseline", tax: baselineTax },
          { name: "Best in view", tax: bestTax },
        ]
      : [];

  const savings =
    baselineTax != null && bestTax != null ? Math.max(0, baselineTax - bestTax) : null;
  const savingsPct =
    savings != null && baselineTax != null && baselineTax > 0
      ? ((savings / baselineTax) * 100).toFixed(1)
      : null;

  const baseEff = parseDecimalSafe(baselineRow.effective_rate);
  const bestEff = parseDecimalSafe(bestRow.effective_rate);
  const effRows =
    baseEff != null && bestEff != null
      ? [
          { name: "Baseline", pct: baseEff * 100 },
          { name: "Best in view", pct: bestEff * 100 },
        ]
      : [];

  const topN = Math.min(5, data.rows.length);
  const rankRows = data.rows.slice(0, topN).map((r) => ({
    name: r.display_name.length > 24 ? `${r.display_name.slice(0, 22)}…` : r.display_name,
    tax: parseDecimalSafe(r.total_tax) ?? 0,
    isBest: r.rank === 1,
  }));

  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <div className="rounded-xl border border-border/70 bg-card/50 p-5 shadow-sm">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Total tax comparison</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Baseline vs best-ranked strategy in this response (compliance-aware optimization).
        </p>
        {compareRows.length > 0 ? (
          <div className="mt-4 h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={compareRows} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={56} />
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
                  <Cell fill={BAR_PRIMARY} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">Insufficient numeric data for chart.</p>
        )}
        {savings != null && savings > 0 ? (
          <div className="mt-3 rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-xs">
            <span className="text-muted-foreground">Savings vs baseline: </span>
            <span className="font-mono font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
              {formatLkrAmount(savings)}
            </span>
            {savingsPct != null ? (
              <span className="text-muted-foreground"> ({savingsPct}% of baseline tax)</span>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-border/70 bg-card/50 p-5 shadow-sm">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Effective tax rate</h3>
        <p className="mt-1 text-xs text-muted-foreground">Ratio of total tax to gross (shown as percent).</p>
        {effRows.length > 0 ? (
          <div className="mt-4 h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={effRows} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={48} unit="%" />
                <Tooltip
                  formatter={(v: number) => [`${Number(v).toFixed(2)}%`, "Effective rate"]}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--color-border-soft)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="pct" radius={[6, 6, 0, 0]}>
                  <Cell fill={BAR_BASELINE} />
                  <Cell fill={BAR_PRIMARY} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">Effective rate not available for comparison.</p>
        )}
      </div>

      <div className="rounded-xl border border-border/70 bg-card/50 p-5 shadow-sm lg:col-span-2">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Top strategies by total tax</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          First {topN} rows in this table (legal strategy ranking).
        </p>
        {rankRows.length > 0 ? (
          <div className="mt-4 h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rankRows} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: number) => [formatLkrAmount(v), "Tax"]}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--color-border-soft)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="tax" radius={[0, 6, 6, 0]}>
                  {rankRows.map((entry) => (
                    <Cell key={entry.name} fill={entry.isBest ? BAR_PRIMARY : BAR_BASELINE} />
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
