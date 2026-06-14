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

import type { ImpactSimulationResponse, ProjectionBand, YearlyProjection } from "../types";
import { formatLkr, parseLkr } from "../utils/format-lkr";

type FanRow = {
  year: number;
  p10: number;
  p50: number;
  p90: number;
  bandBase: number;
  bandSpan: number;
  baseline?: number;
  strategy?: number;
};

function bandsToRows(
  bands: ProjectionBand[],
  baseline?: YearlyProjection[],
  strategy?: YearlyProjection[] | null,
): FanRow[] {
  return bands.map((b) => {
    const base = baseline?.find((x) => x.year === b.year);
    const strat = strategy?.find((x) => x.year === b.year);
    const p10 = parseLkr(b.p10);
    const p90 = parseLkr(b.p90);
    return {
      year: b.year,
      p10,
      p50: parseLkr(b.p50),
      p90,
      bandBase: p10,
      bandSpan: Math.max(0, p90 - p10),
      baseline: base ? parseLkr(base.net_worth) : undefined,
      strategy: strat ? parseLkr(strat.net_worth) : undefined,
    };
  });
}

type ChartBlockProps = {
  title: string;
  description: string;
  data: FanRow[];
  showMedianPaths?: boolean;
};

function FanChartBlock({ title, description, data, showMedianPaths }: ChartBlockProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-border/80 bg-card p-5 text-sm text-muted-foreground">
        No projection data.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm">
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      <div className="mt-4 h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
            <XAxis dataKey="year" tick={{ fontSize: 11 }} label={{ value: "Year", position: "insideBottom", offset: -4, fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              width={72}
              tickFormatter={(v: number) =>
                v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : `${(v / 1000).toFixed(0)}k`
              }
            />
            <Tooltip
              formatter={(v: number, name: string) => [formatLkr(v), name]}
              labelFormatter={(y) => `Year ${y}`}
              contentStyle={{ borderRadius: 8, fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area
              type="monotone"
              dataKey="bandBase"
              stackId="uncertainty"
              stroke="none"
              fill="transparent"
              legendType="none"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="bandSpan"
              stackId="uncertainty"
              stroke="none"
              fill="var(--color-primary)"
              fillOpacity={0.15}
              name="P10–P90 band"
              isAnimationActive={false}
            />
            <Line type="monotone" dataKey="p50" stroke="var(--color-primary)" strokeWidth={2.5} dot={false} name="P50 (median)" />
            <Line type="monotone" dataKey="p10" stroke="var(--color-primary)" strokeWidth={1} strokeDasharray="4 4" dot={false} name="P10" />
            <Line type="monotone" dataKey="p90" stroke="var(--color-primary)" strokeWidth={1} strokeDasharray="4 4" dot={false} name="P90" />
            {showMedianPaths && (
              <>
                <Line
                  type="monotone"
                  dataKey="baseline"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  dot={false}
                  name="Baseline (median path)"
                />
                <Line
                  type="monotone"
                  dataKey="strategy"
                  stroke="#059669"
                  strokeWidth={2}
                  dot={false}
                  name="With strategy (median path)"
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

type Props = {
  result: ImpactSimulationResponse;
};

export function ImpactCharts({ result }: Props) {
  const netRows = bandsToRows(
    result.net_worth_bands,
    result.baseline,
    result.strategy_path,
  );
  const taxRows = result.tax_liability_bands.map((b) => {
    const p10 = parseLkr(b.p10);
    const p90 = parseLkr(b.p90);
    return {
      year: b.year,
      p10,
      p50: parseLkr(b.p50),
      p90,
      bandBase: p10,
      bandSpan: Math.max(0, p90 - p10),
    };
  });

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <FanChartBlock
        title="Net worth fan chart"
        description="Monte Carlo P10 / P50 / P90 bands across simulated paths (FR7, FR8)."
        data={netRows}
        showMedianPaths={Boolean(result.strategy_path)}
      />
      <FanChartBlock
        title="Tax liability fan chart"
        description="Uncertainty bands for annual tax liability over the horizon."
        data={taxRows}
      />
    </div>
  );
}
