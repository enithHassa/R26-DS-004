import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ImpactSimulationResponse } from "../types";
import { formatLkr, parseLkr } from "../utils/format-lkr";

type Props = {
  result: ImpactSimulationResponse;
};

export function ImpactExtraCharts({ result }: Props) {
  const liabilityRows = result.baseline.map((b, i) => {
    const strat = result.strategy_path?.[i];
    return {
      year: b.year,
      baseline: parseLkr(b.projected_tax_liability),
      strategy: strat ? parseLkr(strat.projected_tax_liability) : undefined,
    };
  });

  const lastBand = result.net_worth_bands[result.net_worth_bands.length - 1];
  const histogramRows = lastBand
    ? [
        { bucket: "P10 (downside)", value: parseLkr(lastBand.p10), fill: "#f43f5e" },
        { bucket: "P50 (median)", value: parseLkr(lastBand.p50), fill: "var(--color-primary)" },
        { bucket: "P90 (upside)", value: parseLkr(lastBand.p90), fill: "#10b981" },
      ]
    : [];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold">Tax liability over time</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Median projected annual tax — baseline vs with strategy.
        </p>
        <div className="mt-4 h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={liabilityRows}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
              <XAxis dataKey="year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
              <Tooltip formatter={(v: number) => formatLkr(v)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="baseline" stroke="#94a3b8" strokeWidth={2} name="Baseline" dot={false} />
              {result.strategy_path && (
                <Line
                  type="monotone"
                  dataKey="strategy"
                  stroke="#059669"
                  strokeWidth={2}
                  name="With strategy"
                  dot={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold">Net worth at horizon (distribution)</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          P10 / P50 / P90 across simulated paths at year {lastBand?.year ?? "—"}.
        </p>
        <div className="mt-4 h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={histogramRows}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
              <XAxis dataKey="bucket" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
              <Tooltip formatter={(v: number) => formatLkr(v)} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {histogramRows.map((entry) => (
                  <Cell key={entry.bucket} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
