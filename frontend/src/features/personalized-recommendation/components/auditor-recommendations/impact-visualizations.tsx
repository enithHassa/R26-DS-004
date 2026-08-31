import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ImpactSimulationResponse } from "../../types";
import { formatLkr, parseLkr } from "../../utils/format-lkr";
import { AUDITOR_IMPACT_HORIZON_YEARS } from "../../constants/auditor-impact";

type Props = {
  result: ImpactSimulationResponse;
  strategyName?: string;
};

const PIE_BEFORE = ["#ef4444", "#94a3b8"];
const PIE_AFTER = ["#22c55e", "#94a3b8"];

function aggregateTaxSlices(result: ImpactSimulationResponse) {
  const horizon = Math.min(AUDITOR_IMPACT_HORIZON_YEARS, result.baseline.length);
  let baselineTax = 0;
  let strategyTax = 0;
  let baselineTakeHome = 0;
  let strategyTakeHome = 0;

  for (let i = 0; i < horizon; i++) {
    const base = result.baseline[i];
    const strat = result.strategy_path?.[i];
    if (!base || !strat) continue;
    const baseTax = parseLkr(base.projected_tax_liability);
    const stratTaxVal = parseLkr(strat.projected_tax_liability);
    const salary = parseLkr(base.projected_salary);
    baselineTax += baseTax;
    strategyTax += stratTaxVal;
    baselineTakeHome += Math.max(0, salary - baseTax);
    strategyTakeHome += Math.max(0, salary - stratTaxVal);
  }

  const taxSaved = baselineTax - strategyTax;

  return {
    beforePie: [
      { name: "Tax liability", value: baselineTax },
      { name: "Take-home after tax", value: baselineTakeHome },
    ],
    afterPie: [
      { name: "Tax with strategy", value: strategyTax },
      { name: "Take-home after tax", value: strategyTakeHome },
    ],
    baselineTax,
    strategyTax,
    taxSaved,
  };
}

export function AuditorImpactVisualizations({ result, strategyName = "With strategy" }: Props) {
  const { beforePie, afterPie, taxSaved } = aggregateTaxSlices(result);

  const takeHomeRows = result.baseline.slice(0, result.horizon_years).map((base, i) => {
    const strat = result.strategy_path?.[i];
    const baseTax = parseLkr(base.projected_tax_liability);
    const stratTax = strat ? parseLkr(strat.projected_tax_liability) : baseTax;
    const salary = parseLkr(base.projected_salary);
    const stratSalary = strat ? parseLkr(strat.projected_salary) : salary;
    return {
      year: String(base.year),
      noStrategy: Math.max(0, salary - baseTax),
      withStrategy: Math.max(0, stratSalary - stratTax),
    };
  });

  const netWorthBand = result.net_worth_bands[result.net_worth_bands.length - 1];
  const distributionRows = netWorthBand
    ? [
        { bucket: "P10 downside", value: parseLkr(netWorthBand.p10), fill: "#f43f5e" },
        { bucket: "P50 median", value: parseLkr(netWorthBand.p50), fill: "var(--color-primary)" },
        { bucket: "P90 upside", value: parseLkr(netWorthBand.p90), fill: "#10b981" },
      ]
    : [];

  const wealthRows = result.baseline.slice(0, result.horizon_years).map((base, i) => {
    const strat = result.strategy_path?.[i];
    return {
      year: base.year,
      baseline: parseLkr(base.net_worth),
      strategy: strat ? parseLkr(strat.net_worth) : undefined,
    };
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-border/70 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Before recommendation</CardTitle>
            <p className="text-xs text-muted-foreground">
              Where your money goes without any strategy — tax vs take-home pay (2 years total)
            </p>
          </CardHeader>
          <CardContent>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={beforePie}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={88}
                    paddingAngle={2}
                  >
                    {beforePie.map((_, i) => (
                      <Cell key={i} fill={PIE_BEFORE[i % PIE_BEFORE.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatLkr(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">After recommendation</CardTitle>
            <p className="text-xs text-muted-foreground">
              With &ldquo;{strategyName}&rdquo; — same split as before: tax vs take-home (
              {taxSaved >= 0 ? "saved" : "extra cost"}{" "}
              {formatLkr(Math.abs(taxSaved))})
            </p>
          </CardHeader>
          <CardContent>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={afterPie}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={88}
                    paddingAngle={2}
                  >
                    {afterPie.map((_, i) => (
                      <Cell key={i} fill={PIE_AFTER[i % PIE_AFTER.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatLkr(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-border/70 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Take-home pay by year</CardTitle>
            <p className="text-xs text-muted-foreground">
              Salary after tax — no strategy vs &ldquo;{strategyName}&rdquo; (taller bar = more money you keep)
            </p>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={takeHomeRows}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}K` : String(v))}
                  />
                  <Tooltip formatter={(v: number) => formatLkr(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="noStrategy" fill="#94a3b8" name="No strategy" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="withStrategy" fill="#059669" name={strategyName} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Net worth at horizon (Monte Carlo)</CardTitle>
            <p className="text-xs text-muted-foreground">
              Final-year wealth after {result.n_paths.toLocaleString()} random futures — bad / typical / good case
            </p>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distributionRows}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 10 }} interval={0} angle={-8} textAnchor="end" height={48} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}K`} />
                  <Tooltip formatter={(v: number) => formatLkr(v)} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {distributionRows.map((entry) => (
                      <Cell key={entry.bucket} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/70 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Net worth trajectory</CardTitle>
          <p className="text-xs text-muted-foreground">
            Typical (median) total wealth each year — no strategy vs with &ldquo;{strategyName}&rdquo;
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={wealthRows}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}K`} />
                <Tooltip formatter={(v: number) => formatLkr(v)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="baseline" fill="#94a3b8" name="No strategy" radius={[4, 4, 0, 0]} />
                <Bar dataKey="strategy" fill="#059669" name={strategyName} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
