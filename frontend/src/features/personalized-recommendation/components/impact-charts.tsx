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
      <p className="mt-1.5 text-xs text-muted-foreground">{description}</p>
      <p className="mt-3 rounded-md bg-muted/50 p-2.5 text-[11px] leading-relaxed text-muted-foreground">
        The shaded band shows the range of realistic outcomes. The solid line is the
        most likely path; the dashed lines are the pessimistic and optimistic edges.
      </p>
      <div className="mt-4 h-[340px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 8, bottom: 28 }}>
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
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 16, lineHeight: 1.8 }}
              verticalAlign="bottom"
              align="center"
            />
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
              name="Realistic range"
              isAnimationActive={false}
            />
            <Line type="monotone" dataKey="p50" stroke="var(--color-primary)" strokeWidth={3} dot={false} name="Most likely" />
            <Line type="monotone" dataKey="p10" stroke="#dc2626" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="If things go badly" />
            <Line type="monotone" dataKey="p90" stroke="#0891b2" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="If things go well" />
            {showMedianPaths && (
              <>
                <Line
                  type="monotone"
                  dataKey="baseline"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  strokeDasharray="2 2"
                  dot={false}
                  name="If you do nothing"
                />
                <Line
                  type="monotone"
                  dataKey="strategy"
                  stroke="#059669"
                  strokeWidth={2.5}
                  dot={false}
                  name="If you follow this plan"
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
    <div className="grid gap-6">
      <FanChartBlock
        title="How your savings could grow"
        description="Thousands of possible futures were simulated — this shows the spread of likely outcomes."
        data={netRows}
        showMedianPaths={Boolean(result.strategy_path)}
      />
      <FanChartBlock
        title="How much tax you might pay each year"
        description="Tax bills vary with income and life changes — this shows the realistic range year by year."
        data={taxRows}
      />
    </div>
  );
}
