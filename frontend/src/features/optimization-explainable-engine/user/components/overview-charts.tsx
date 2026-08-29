import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { cn } from "@/lib/utils";

import type { CalculateResponse, ReliefLine } from "../../api";
import { formatLkr } from "../../format-lkr";
import {
  businessIncomeLkr,
  employmentIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  totalIncomeLkr,
} from "../../income-aggregate";
import type { InterviewIncomeState } from "../../types";
import type { TaxpayerComputeResult } from "../compute-scenario";

const C = {
  teal: "#2dd4bf",
  blue: "#60a5fa",
  purple: "#a78bfa",
  red: "#f87171",
  amber: "#fbbf24",
  muted: "#64748b",
  track: "rgba(148, 163, 184, 0.15)",
  text: "#f8fafc",
  mutedText: "#94a3b8",
  tooltipBg: "#0f172a",
  tooltipBorder: "rgba(148, 163, 184, 0.35)",
};

/** Dark-theme pie tooltip — Recharts default item text is nearly invisible on TaxWise. */
function DarkPieTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{
    name?: string;
    value?: number;
    payload?: { name?: string; value?: number; color?: string };
    color?: string;
  }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]!;
  const name = row.name ?? row.payload?.name ?? "";
  const value = Number(row.value ?? row.payload?.value ?? 0);
  const color = row.payload?.color ?? row.color ?? C.teal;

  return (
    <div
      className="rounded-lg border px-3 py-2 shadow-lg"
      style={{
        background: C.tooltipBg,
        borderColor: C.tooltipBorder,
        color: C.text,
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ background: color }}
          aria-hidden
        />
        <p className="text-xs font-medium" style={{ color: C.text }}>
          {name}
        </p>
      </div>
      <p className="mt-1 text-sm font-semibold tabular-nums" style={{ color: C.text }}>
        {formatLkr(value)}
      </p>
    </div>
  );
}

function formatMetricPercent(percent: number): string {
  const p = Math.max(0, Math.min(100, percent));
  if (p <= 0) return "0";
  // Small savings vs a large tax bill round to 0 with Math.round — keep one decimal.
  if (p < 1) return p.toFixed(1);
  return String(Math.round(p));
}

function MetricBar({
  label,
  percent,
  color,
}: {
  label: string;
  percent: number;
  color: string;
}) {
  const clamped = Math.max(0, Math.min(100, percent));
  // Keep a visible stub when impact is real but under 1% of a large tax bill.
  const barWidth = clamped > 0 && clamped < 2 ? Math.max(clamped, 2) : clamped;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] text-[var(--uv-text-muted)]">
        <span>{label}</span>
        <span>{formatMetricPercent(clamped)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full" style={{ background: C.track }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${barWidth}%`, background: color }}
        />
      </div>
    </div>
  );
}

/** Four income heads (session) + auditor-aligned calculation totals (from /calculate). */
export function IncomeSummaryStrip({
  income,
  result,
}: {
  income: InterviewIncomeState;
  result: CalculateResponse;
}) {
  const employment = employmentIncomeLkr(income);
  const investment = investmentIncomeLkr(income);
  const business = businessIncomeLkr(income);
  const other = otherIncomeLkr(income);
  const headsSum = totalIncomeLkr(income);
  const terminalExtra = Math.max(0, (result.gross_income ?? 0) - headsSum);

  const incomeHeads = [
    { label: "Employment Income", value: employment, color: C.blue },
    { label: "Investment Income", value: investment, color: C.purple },
    { label: "Business Income", value: business, color: C.amber },
    { label: "Other Income", value: other, color: C.teal },
  ];

  // Same story as auditor Result page tiles.
  const calcTiles = [
    { label: "Assessable (gross)", value: result.gross_income, color: C.text },
    { label: "Reliefs applied", value: result.total_reliefs, color: C.teal },
    { label: "Taxable income", value: result.taxable_income, color: C.purple },
    { label: "Tax payable", value: result.tax_payable, color: C.red },
    { label: "APIT credit", value: result.apit_credit ?? 0, color: C.amber },
    { label: "WHT credit", value: result.wht_credit ?? 0, color: C.blue },
    {
      label: (result.tax_refund ?? 0) > 0 ? "Refund" : "Balance payable",
      value:
        (result.tax_refund ?? 0) > 0
          ? (result.tax_refund ?? 0)
          : (result.balance_payable ?? result.tax_payable),
      color: C.teal,
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid gap-3 rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4 sm:grid-cols-2 lg:grid-cols-4">
        {incomeHeads.map((cell) => (
          <div key={cell.label} className="min-w-0">
            <p className="text-xs text-[var(--uv-text-muted)]">{cell.label}</p>
            <p
              className="mt-1 text-lg font-semibold tracking-tight tabular-nums"
              style={{ color: cell.color }}
            >
              {formatLkr(cell.value)}
            </p>
          </div>
        ))}
      </div>

      {terminalExtra > 0 ? (
        <p className="text-xs text-[var(--uv-text-muted)]">
          Assessable gross includes {formatLkr(terminalExtra)} beyond the four income heads
          {(result.terminal_benefit_amount ?? 0) > 0
            ? ` (terminal benefits ${formatLkr(result.terminal_benefit_amount ?? 0)})`
            : ""}
          — same as the auditor Result.
        </p>
      ) : null}

      <div className="grid gap-3 rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4 sm:grid-cols-2 lg:grid-cols-3">
        {calcTiles.map((cell) => (
          <div key={cell.label} className="min-w-0">
            <p className="text-xs text-[var(--uv-text-muted)]">{cell.label}</p>
            <p
              className="mt-1 text-lg font-semibold tracking-tight tabular-nums"
              style={{ color: cell.color }}
            >
              {formatLkr(cell.value)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function compositionSlices(result: CalculateResponse) {
  const reliefs = Math.max(0, result.total_reliefs ?? 0);
  const tax = Math.max(0, result.tax_payable ?? 0);
  const taxable = Math.max(0, result.taxable_income ?? 0);
  // Visual story: income sheltered by reliefs vs tax vs remaining taxable after tax framing
  const kept = Math.max(0, taxable - tax);
  return [
    { name: "Reliefs", value: reliefs, color: C.teal },
    { name: "Tax payable", value: tax, color: C.red },
    { name: "After-tax income", value: kept, color: C.blue },
  ].filter((s) => s.value > 0);
}

function MiniDonut({
  title,
  result,
}: {
  title: string;
  result: CalculateResponse;
}) {
  const data = compositionSlices(result);
  if (data.length === 0) {
    return (
      <div className="flex h-[88px] items-center justify-center text-xs text-[var(--uv-text-muted)]">
        No data
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center">
      <p className="mb-0.5 text-[11px] font-medium text-[var(--uv-text-muted)]">{title}</p>
      <div className="h-[88px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={24}
              outerRadius={38}
              paddingAngle={2}
              stroke="none"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<DarkPieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs font-semibold tabular-nums text-[var(--uv-text)]">
        Tax {formatLkr(result.tax_payable)}
      </p>
    </div>
  );
}

/** Before / after donuts + total savings — Figma Tax Breakdown panel. */
export function TaxBreakdownPanel({
  explore,
  official,
}: {
  explore?: TaxpayerComputeResult | null;
  official?: CalculateResponse | null;
}) {
  const before = explore?.baseline ?? null;
  const after = explore?.optimized ?? official ?? null;
  const savings =
    explore?.savings ??
    (before && after ? Math.max(0, before.tax_payable - after.tax_payable) : 0);

  if (!after && !before) return null;

  return (
    <div className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3">
      <h3 className="text-sm font-semibold text-[var(--uv-text)]">Tax breakdown</h3>
      <p className="mt-0.5 text-[11px] text-[var(--uv-text-muted)]">
        Reliefs vs tax vs what you keep — before and after your claims.
      </p>
      <div className="mt-2 grid grid-cols-2 gap-1">
        {before ? <MiniDonut title="Before" result={before} /> : <div />}
        {after ? (
          <MiniDonut title={before ? "After" : "Your result"} result={after} />
        ) : null}
      </div>
      {savings > 0 ? (
        <div className="mt-2 border-t border-[var(--uv-border)] pt-2 text-center">
          <p className="text-[11px] text-[var(--uv-text-muted)]">Total savings potential</p>
          <p className="mt-0.5 text-xl font-bold tracking-tight text-[var(--uv-accent)]">
            {formatLkr(savings)}
          </p>
        </div>
      ) : null}
      <ul className="mt-2 flex flex-wrap justify-center gap-3 text-[10px] text-[var(--uv-text-muted)]">
        <li className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full" style={{ background: C.teal }} /> Reliefs
        </li>
        <li className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full" style={{ background: C.red }} /> Tax
        </li>
        <li className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full" style={{ background: C.blue }} /> After-tax
        </li>
      </ul>
    </div>
  );
}

/** Strategy-style cards: tax saved by each relief + how much of its cap was used. */
export function OpportunityCards({
  opportunities,
  fillHeight = false,
}: {
  opportunities: Array<
    ReliefLine & { tax_saved?: number; tax_before?: number }
  >;
  /** Stretch cards so the column matches the charts column height. */
  fillHeight?: boolean;
}) {
  if (opportunities.length === 0) return null;

  const top = opportunities.slice(0, 3);

  return (
    <div className={cn("flex flex-col gap-2", fillHeight && "min-h-0 flex-1")}>
      <div className="flex shrink-0 items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-[var(--uv-text)]">Best for you</h3>
        <p className="text-[11px] text-[var(--uv-text-muted)]">Top {top.length} reliefs</p>
      </div>
      <ul
        className={cn(
          "flex flex-col gap-2",
          fillHeight ? "min-h-0 flex-1" : "space-y-0",
        )}
      >
        {top.map((line, index) => {
          const taxSaved = Math.max(0, line.tax_saved ?? 0);
          const taxBefore = Math.max(0, line.tax_before ?? 0);
          const taxImpact =
            taxBefore > 0
              ? Math.min(100, Math.max(0, (taxSaved / taxBefore) * 100))
              : 0;

          const reliefLimitUsed =
            line.cap != null && line.cap > 0
              ? Math.min(100, Math.max(0, (line.applied / line.cap) * 100))
              : 0;

          return (
            <li
              key={line.entry_id}
              className={cn(
                "rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] px-3",
                fillHeight
                  ? "flex min-h-[7.5rem] flex-1 flex-col justify-center py-3.5 lg:min-h-0"
                  : "py-2.5",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--uv-accent)]/15 text-[10px] font-semibold text-[var(--uv-accent)]">
                    {index + 1}
                  </span>
                  <p className="min-w-0 truncate text-sm font-medium leading-snug">
                    {line.display_name}
                  </p>
                  <span className="hidden shrink-0 rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300 sm:inline-flex">
                    Compliant
                  </span>
                </div>
                <p className="shrink-0 text-sm font-semibold tabular-nums text-[var(--uv-accent)]">
                  {formatLkr(line.applied)}
                </p>
              </div>
              <div className={cn("space-y-1.5", fillHeight ? "mt-3" : "mt-2")}>
                <MetricBar label="Tax Impact" percent={taxImpact} color={C.teal} />
                <MetricBar label="Relief Limit Used" percent={reliefLimitUsed} color={C.red} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Income mix donut for the session income heads. */
export function IncomeMixChart({ income }: { income: InterviewIncomeState }) {
  const data = [
    { name: "Employment", value: employmentIncomeLkr(income), color: C.blue },
    { name: "Business", value: businessIncomeLkr(income), color: C.amber },
    { name: "Investment", value: investmentIncomeLkr(income), color: C.purple },
    { name: "Other", value: otherIncomeLkr(income), color: C.teal },
  ].filter((d) => d.value > 0);

  if (data.length === 0) return null;

  return (
    <div className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3">
      <h3 className="text-sm font-semibold">Income mix</h3>
      <p className="mt-0.5 text-[11px] text-[var(--uv-text-muted)]">
        Where your assessable income comes from.
      </p>
      <div className="mt-1 h-[112px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={28}
              outerRadius={44}
              paddingAngle={2}
              stroke="none"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<DarkPieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-3 text-[10px] text-[var(--uv-text-muted)]">
        {data.map((d) => (
          <li key={d.name} className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
            {d.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
