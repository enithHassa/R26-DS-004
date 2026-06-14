import {
  Bar,
  BarChart,
  CartesianGrid,
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

const COLORS = ["#059669", "#2563eb", "#d97706", "#7c3aed", "#db2777"];

type Props = {
  results: ImpactSimulationResponse[];
  labels: string[];
};

export function CompareCharts({ results, labels }: Props) {
  if (results.length === 0) return null;

  const years = results[0]?.net_worth_bands.map((b) => b.year) ?? [];
  const netWorthRows = years.map((year) => {
    const row: Record<string, number | string> = { year };
    results.forEach((r, i) => {
      const band = r.net_worth_bands.find((b) => b.year === year);
      if (band) row[labels[i] ?? `S${i + 1}`] = parseLkr(band.p50);
    });
    return row;
  });

  const savingsRows = results.map((r, i) => ({
    name: labels[i] ?? `Strategy ${i + 1}`,
    savings: parseLkr(r.summary.expected_total_savings),
    netWorth: parseLkr(r.summary.expected_net_worth),
    probGain: r.summary.probability_of_net_gain * 100,
    fill: COLORS[i % COLORS.length],
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm lg:col-span-2">
        <h3 className="text-base font-semibold">Net worth P50 — side by side</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Median projected net worth across strategies for the same profile and horizon.
        </p>
        <div className="mt-4 h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={netWorthRows}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
              <XAxis dataKey="year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
              <Tooltip formatter={(v: number) => formatLkr(v)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {labels.map((label, i) => (
                <Line
                  key={label}
                  type="monotone"
                  dataKey={label}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold">Expected tax savings</h3>
        <div className="mt-4 h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={savingsRows}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
              <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={56} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
              <Tooltip formatter={(v: number) => formatLkr(v)} />
              <Bar dataKey="savings" name="Tax savings" radius={[6, 6, 0, 0]} fill="#059669" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm">
        <h3 className="text-base font-semibold">Probability of net gain</h3>
        <div className="mt-4 h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={savingsRows}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
              <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={56} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Bar dataKey="probGain" name="P(net gain)" radius={[6, 6, 0, 0]} fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
