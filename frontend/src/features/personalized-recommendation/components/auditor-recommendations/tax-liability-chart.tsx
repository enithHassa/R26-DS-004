import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";

import type { ImpactSimulationResponse, ProjectionBand } from "../../types";
import { formatLkr, parseLkr } from "../../utils/format-lkr";

export type TaxLiabilityChartRow = {
  year: number;
  noStrategy: number;
  withStrategy1: number;
  withStrategy2?: number;
  bandLow?: number;
  bandHigh?: number;
  bandSpan?: number;
};

type Props = {
  rows: TaxLiabilityChartRow[];
  showMonteCarloToggle?: boolean;
  title?: string;
  subtitle?: string;
  compact?: boolean;
  className?: string;
};

function buildRowsFromSimulations(
  primary: ImpactSimulationResponse,
  secondary?: ImpactSimulationResponse | null,
  bands?: ProjectionBand[],
): TaxLiabilityChartRow[] {
  return primary.baseline.slice(0, primary.horizon_years).map((base, i) => {
    const s1 = primary.strategy_path?.[i];
    const s2 = secondary?.strategy_path?.[i];
    const band = bands?.find((b) => b.year === base.year);
    const bandLow = band ? parseLkr(band.p10) : undefined;
    const bandHigh = band ? parseLkr(band.p90) : undefined;
    return {
      year: base.year,
      noStrategy: parseLkr(base.projected_tax_liability),
      withStrategy1: s1 ? parseLkr(s1.projected_tax_liability) : parseLkr(base.projected_tax_liability),
      withStrategy2: s2 ? parseLkr(s2.projected_tax_liability) : undefined,
      bandLow,
      bandHigh,
      bandSpan: bandLow !== undefined && bandHigh !== undefined ? Math.max(0, bandHigh - bandLow) : undefined,
    };
  });
}

export function buildTaxLiabilityChartRows(
  primary: ImpactSimulationResponse,
  secondary?: ImpactSimulationResponse | null,
): TaxLiabilityChartRow[] {
  return buildRowsFromSimulations(primary, secondary, primary.tax_liability_bands);
}

export function AuditorTaxLiabilityChart({
  rows,
  showMonteCarloToggle = true,
  title = "Annual tax liability projection",
  subtitle = "LKR · Monte Carlo confidence bands",
  compact = false,
  className,
}: Props) {
  const [monteCarlo, setMonteCarlo] = useState(true);
  const hasStrategy2 = rows.some((r) => r.withStrategy2 !== undefined);
  const chartHeight = compact ? 220 : 340;

  const chartData = useMemo(
    () =>
      rows.map((r) => ({
        ...r,
        bandBase: monteCarlo ? r.bandLow : undefined,
        bandSpan: monteCarlo ? r.bandSpan : undefined,
      })),
    [rows, monteCarlo],
  );

  return (
    <div
      className={cn(
        "rounded-xl border border-border/70 bg-card shadow-sm",
        compact ? "p-4" : "p-5",
        className,
      )}
    >
      {(title || subtitle) && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && <h3 className="text-sm font-semibold">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          {showMonteCarloToggle && !compact && (
            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
              <span>Monte Carlo Bands</span>
              <button
                type="button"
                role="switch"
                aria-checked={monteCarlo}
                onClick={() => setMonteCarlo((v) => !v)}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  monteCarlo ? "bg-primary" : "bg-muted",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                    monteCarlo ? "translate-x-5" : "translate-x-0.5",
                  )}
                />
              </button>
            </label>
          )}
        </div>
      )}

      <div className={cn("w-full", title || subtitle ? "mt-4" : "")} style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
            <XAxis dataKey="year" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              width={52}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}K` : String(v))}
            />
            <Tooltip
              contentStyle={{ borderRadius: 8, fontSize: 12 }}
              labelFormatter={(y) => `Year ${y}`}
              formatter={(value: number, name: string) => [formatLkr(value), name]}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 12 }} />
            {monteCarlo && !compact && (
              <>
                <Area
                  type="monotone"
                  dataKey="bandBase"
                  stackId="band"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="bandSpan"
                  stackId="band"
                  stroke="none"
                  fill="var(--color-primary)"
                  fillOpacity={0.12}
                  name="Confidence band"
                  isAnimationActive={false}
                />
              </>
            )}
            <Line
              type="monotone"
              dataKey="noStrategy"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ r: 3, fill: "#ef4444" }}
              name="No Strategy"
            />
            <Line
              type="monotone"
              dataKey="withStrategy1"
              stroke="#22c55e"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "#22c55e" }}
              name="With Strategy 1"
            />
            {hasStrategy2 && (
              <Line
                type="monotone"
                dataKey="withStrategy2"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={{ r: 3, fill: "#fbbf24" }}
                name="With Strategy 2"
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
