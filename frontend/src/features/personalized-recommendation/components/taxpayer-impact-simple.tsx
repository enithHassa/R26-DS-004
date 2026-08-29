import { useMemo } from "react";
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

import type { ImpactSimulationResponse } from "../types";
import { formatLkr, parseLkr } from "../utils/format-lkr";
import { buildImpactTableRows } from "./auditor-recommendations/auditor-impact-detail-sections";

type ThemeProps = {
  userView?: boolean;
};

const UV = {
  card: "rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg)]/60 p-4",
  title: "text-sm font-semibold text-[var(--uv-text)]",
  subtitle: "text-xs text-[var(--uv-text-muted)]",
  body: "text-sm leading-relaxed text-[var(--uv-text-muted)]",
};

function chartTooltipStyle(userView?: boolean) {
  return userView
    ? {
        borderRadius: 8,
        fontSize: 12,
        background: "#151c2e",
        border: "1px solid rgba(148,163,184,0.2)",
        color: "#f8fafc",
      }
    : { borderRadius: 8, fontSize: 12 };
}

export function TaxpayerImpactHeadline({
  result,
  strategyName,
  userView = true,
}: ThemeProps & { result: ImpactSimulationResponse; strategyName: string }) {
  const rows = buildImpactTableRows(result);
  const totalSaving = rows.reduce((sum, r) => sum + r.annualSaving, 0);
  const years = result.horizon_years;
  const odds = Math.round(result.summary.probability_of_net_gain * 100);

  const tileClass = userView
    ? "rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4"
    : "rounded-lg border border-border bg-card p-4";

  return (
    <div className="space-y-3">
      <p className={userView ? UV.body : "text-sm text-muted-foreground"}>
        If you follow <strong className={userView ? "text-[var(--uv-accent)]" : ""}>{strategyName}</strong>,
        here is a simple picture of what could change over the next {years} year{years === 1 ? "" : "s"}.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className={tileClass}>
          <p className={userView ? UV.subtitle : "text-xs text-muted-foreground"}>Total tax you might save</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-emerald-400">{formatLkr(totalSaving)}</p>
          <p className={userView ? "mt-1 text-[11px] text-[var(--uv-text-muted)]" : "mt-1 text-[11px] text-muted-foreground"}>
            Compared with doing nothing
          </p>
        </div>
        <div className={tileClass}>
          <p className={userView ? UV.subtitle : "text-xs text-muted-foreground"}>Average per year</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-[var(--uv-accent)]">
            {formatLkr(rows.length ? totalSaving / rows.length : 0)}
          </p>
          <p className={userView ? "mt-1 text-[11px] text-[var(--uv-text-muted)]" : "mt-1 text-[11px] text-muted-foreground"}>
            Rough yearly benefit
          </p>
        </div>
        <div className={tileClass}>
          <p className={userView ? UV.subtitle : "text-xs text-muted-foreground"}>Chance this helps you</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-sky-300">{odds} in 100</p>
          <p className={userView ? "mt-1 text-[11px] text-[var(--uv-text-muted)]" : "mt-1 text-[11px] text-muted-foreground"}>
            Based on many simulated futures
          </p>
        </div>
      </div>
    </div>
  );
}

export function TaxpayerTaxCompareChart({
  result,
  userView = true,
}: ThemeProps & { result: ImpactSimulationResponse }) {
  const data = useMemo(() => {
    return buildImpactTableRows(result).map((r) => ({
      year: `Year ${r.year}`,
      without: r.taxNoStrategy,
      with: r.taxWithStrategy,
    }));
  }, [result]);

  if (data.length === 0) return null;

  const wrap = userView ? UV.card : "rounded-xl border border-border bg-card p-4";

  return (
    <div className={wrap}>
      <h3 className={userView ? UV.title : "text-sm font-semibold"}>Your tax bill — with vs without this plan</h3>
      <p className={userView ? `mt-1 ${UV.subtitle}` : "mt-1 text-xs text-muted-foreground"}>
        Lower green bars mean you keep more of your income.
      </p>
      <div className="mt-4 h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
            <XAxis dataKey="year" tick={{ fill: userView ? "#94a3b8" : undefined, fontSize: 11 }} />
            <YAxis
              tick={{ fill: userView ? "#94a3b8" : undefined, fontSize: 11 }}
              tickFormatter={(v) => `${Math.round(Number(v) / 1000)}K`}
            />
            <Tooltip formatter={(v: number) => formatLkr(v)} contentStyle={chartTooltipStyle(userView)} />
            <Legend wrapperStyle={{ fontSize: 11, color: userView ? "#94a3b8" : undefined }} />
            <Bar dataKey="without" name="If you do nothing" fill="#f87171" radius={[4, 4, 0, 0]} />
            <Bar dataKey="with" name="If you follow this plan" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function TaxpayerSavingsChart({
  result,
  userView = true,
}: ThemeProps & { result: ImpactSimulationResponse }) {
  const data = useMemo(() => {
    return buildImpactTableRows(result).map((r) => ({
      year: `Year ${r.year}`,
      thisYear: r.annualSaving,
      totalSoFar: r.cumulativeSaving,
    }));
  }, [result]);

  if (data.length === 0) return null;

  const wrap = userView ? UV.card : "rounded-xl border border-border bg-card p-4";

  return (
    <div className={wrap}>
      <h3 className={userView ? UV.title : "text-sm font-semibold"}>How savings add up</h3>
      <p className={userView ? `mt-1 ${UV.subtitle}` : "mt-1 text-xs text-muted-foreground"}>
        Yellow = saved that year · Teal = running total kept in your pocket.
      </p>
      <div className="mt-4 h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
            <XAxis dataKey="year" tick={{ fill: userView ? "#94a3b8" : undefined, fontSize: 11 }} />
            <YAxis
              tick={{ fill: userView ? "#94a3b8" : undefined, fontSize: 11 }}
              tickFormatter={(v) => `${Math.round(Number(v) / 1000)}K`}
            />
            <Tooltip formatter={(v: number) => formatLkr(v)} contentStyle={chartTooltipStyle(userView)} />
            <Legend wrapperStyle={{ fontSize: 11, color: userView ? "#94a3b8" : undefined }} />
            <Bar dataKey="thisYear" name="Saved this year" fill="#fbbf24" radius={[4, 4, 0, 0]} />
            <Bar dataKey="totalSoFar" name="Total saved so far" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function TaxpayerKeepVsTaxPies({
  result,
  userView = true,
}: ThemeProps & { result: ImpactSimulationResponse }) {
  const { before, after } = useMemo(() => {
    const rows = buildImpactTableRows(result);
    const taxBefore = rows.reduce((s, r) => s + r.taxNoStrategy, 0);
    const taxAfter = rows.reduce((s, r) => s + r.taxWithStrategy, 0);
    let grossBefore = 0;
    let grossAfter = 0;
    for (let i = 0; i < result.horizon_years; i++) {
      const base = result.baseline[i];
      const strat = result.strategy_path?.[i];
      if (base) grossBefore += parseLkr(base.projected_salary);
      if (strat) grossAfter += parseLkr(strat.projected_salary);
    }
    if (grossBefore <= 0) grossBefore = taxBefore * 3;
    if (grossAfter <= 0) grossAfter = grossBefore;
    const keepBefore = Math.max(0, grossBefore - taxBefore);
    const keepAfter = Math.max(0, grossAfter - taxAfter);
    return {
      before: [
        { name: "Goes to tax", value: taxBefore, fill: "#f87171" },
        { name: "You keep", value: keepBefore, fill: "#64748b" },
      ],
      after: [
        { name: "Goes to tax", value: taxAfter, fill: "#f87171" },
        { name: "You keep", value: keepAfter, fill: "#2dd4bf" },
      ],
    };
  }, [result]);

  const wrap = userView ? UV.card : "rounded-xl border border-border bg-card p-4";

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className={wrap}>
        <h3 className={userView ? UV.title : "text-sm font-semibold"}>Before — doing nothing</h3>
        <p className={userView ? `mt-1 ${UV.subtitle}` : "mt-1 text-xs text-muted-foreground"}>
          How your money is split between tax and take-home pay.
        </p>
        <div className="mt-2 h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={before} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2}>
                {before.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatLkr(v)} contentStyle={chartTooltipStyle(userView)} />
              <Legend wrapperStyle={{ fontSize: 11, color: userView ? "#94a3b8" : undefined }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className={wrap}>
        <h3 className={userView ? UV.title : "text-sm font-semibold"}>After — with this plan</h3>
        <p className={userView ? `mt-1 ${UV.subtitle}` : "mt-1 text-xs text-muted-foreground"}>
          More stays with you when tax is lower.
        </p>
        <div className="mt-2 h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={after} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2}>
                {after.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatLkr(v)} contentStyle={chartTooltipStyle(userView)} />
              <Legend wrapperStyle={{ fontSize: 11, color: userView ? "#94a3b8" : undefined }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export function TaxpayerImpactSimpleView({
  result,
  strategyName,
  userView = true,
}: ThemeProps & { result: ImpactSimulationResponse; strategyName: string }) {
  return (
    <div className="space-y-5">
      <TaxpayerImpactHeadline result={result} strategyName={strategyName} userView={userView} />
      <TaxpayerTaxCompareChart result={result} userView={userView} />
      <TaxpayerSavingsChart result={result} userView={userView} />
      <TaxpayerKeepVsTaxPies result={result} userView={userView} />
    </div>
  );
}
