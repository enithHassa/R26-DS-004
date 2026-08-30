import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Banknote,
  Check,
  Gauge,
  PiggyBank,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { AdoptionEvidence, Signal } from "../utils/adoption-evidence";
import { formatLkr } from "../utils/format-lkr";

const VERDICT_STYLES: Record<
  AdoptionEvidence["verdict"],
  { label: string; badge: string; ring: string; gradient: string }
> = {
  strong: {
    label: "Likely to adopt",
    badge: "border-emerald-300 bg-emerald-50 text-emerald-800",
    ring: "ring-emerald-200",
    gradient: "from-emerald-500/90 to-emerald-600",
  },
  moderate: {
    label: "Possibly adopts",
    badge: "border-amber-300 bg-amber-50 text-amber-900",
    ring: "ring-amber-200",
    gradient: "from-amber-500/90 to-amber-600",
  },
  weak: {
    label: "Unlikely to adopt",
    badge: "border-rose-300 bg-rose-50 text-rose-800",
    ring: "ring-rose-200",
    gradient: "from-rose-500/90 to-rose-600",
  },
};

const INDEXED_SERIES: { key: "income" | "debt" | "liquidSavings" | "investments"; name: string; color: string }[] = [
  { key: "income", name: "Income", color: "var(--color-primary)" },
  { key: "debt", name: "Debt", color: "#e11d48" },
  { key: "liquidSavings", name: "Liquid savings", color: "#0ea5e9" },
  { key: "investments", name: "Investments", color: "#059669" },
];

function StatTile({
  icon: Icon,
  label,
  value,
  positive,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  positive: boolean;
}) {
  return (
    <div className="rounded-xl border bg-white p-3 shadow-sm">
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={cn("mt-1 text-lg font-semibold", positive ? "text-emerald-700" : "text-rose-700")}>
        {value}
      </div>
    </div>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg border bg-white px-3 py-2">
      <div
        className={cn(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
          signal.met ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700",
        )}
      >
        {signal.met ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          {signal.label}
          <span
            className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              signal.weight === "model" ? "bg-primary/10 text-primary" : "bg-slate-100 text-slate-600",
            )}
          >
            {signal.weight === "model" ? "model" : "trend"}
          </span>
        </div>
        <div className="text-xs text-muted-foreground">{signal.detail}</div>
      </div>
    </div>
  );
}

type Props = {
  evidence: AdoptionEvidence;
  strategyName: string;
  onClose: () => void;
};

export function AdoptionEvidenceModal({ evidence, strategyName, onClose }: Props) {
  const style = VERDICT_STYLES[evidence.verdict];
  const TrendIcon = evidence.incomeGrowthPct >= 0 ? TrendingUp : TrendingDown;
  const hasDebtSeries = evidence.indexedChartData.some((d) => d.debt !== null);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className={cn("flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden p-0 ring-1", style.ring)}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={cn("relative shrink-0 overflow-hidden bg-gradient-to-br px-6 py-5 text-white", style.gradient)}>
          <Button
            size="icon"
            variant="ghost"
            onClick={onClose}
            className="absolute right-3 top-3 text-white hover:bg-white/15 hover:text-white"
          >
            <X className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/15 ring-2 ring-white/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-white/80">Adoption evidence</div>
              <div className="text-lg font-semibold leading-tight">{strategyName}</div>
            </div>
          </div>
          <span
            className={cn(
              "mt-4 inline-flex items-center gap-1.5 rounded-full border bg-white px-3 py-1 text-xs font-semibold",
              style.badge,
            )}
          >
            <TrendIcon className="h-3.5 w-3.5" />
            {style.label}
          </span>
        </div>

        <CardContent className="flex-1 space-y-5 overflow-y-auto bg-muted/20 p-6">
          <div className="rounded-xl border-l-4 border-l-primary bg-white p-4 shadow-sm">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Verdict — why {style.label.toLowerCase()}
            </div>
            <div className="text-sm leading-relaxed text-foreground">{evidence.verdictSummary}</div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              icon={Gauge}
              label="Model probability"
              value={`${(evidence.adoptionProbability * 100).toFixed(0)}%`}
              positive={evidence.adoptionProbability >= 0.6}
            />
            <StatTile
              icon={Banknote}
              label="Income growth"
              value={`${evidence.incomeGrowthPct >= 0 ? "+" : ""}${evidence.incomeGrowthPct.toFixed(1)}%`}
              positive={evidence.incomeGrowthPct >= 0}
            />
            <StatTile
              icon={PiggyBank}
              label="Savings rate"
              value={`${evidence.savingsRateStart.toFixed(0)}%→${evidence.savingsRateEnd.toFixed(0)}%`}
              positive={evidence.savingsRateDeltaPts >= 0}
            />
            <StatTile
              icon={Wallet}
              label="Debt trend"
              value={`${evidence.debtTrendPct >= 0 ? "+" : ""}${evidence.debtTrendPct.toFixed(1)}%`}
              positive={evidence.debtTrendPct <= 0}
            />
          </div>

          <div className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold text-foreground">
              Signal checklist ({evidence.signals.filter((s) => s.met).length}/{evidence.signals.length} met)
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {evidence.signals.map((signal) => (
                <SignalRow key={signal.key} signal={signal} />
              ))}
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold text-foreground">
              {evidence.chartData.length}-month income &amp; savings-rate trend
            </div>
            <div className="h-[200px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={evidence.chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="incomeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} minTickGap={28} />
                  <YAxis
                    yAxisId="income"
                    tick={{ fontSize: 10 }}
                    width={56}
                    tickFormatter={(v: number) =>
                      v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : `${(v / 1000).toFixed(0)}k`
                    }
                  />
                  <YAxis yAxisId="rate" orientation="right" tick={{ fontSize: 10 }} width={40} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip
                    formatter={(v: number, name: string) => (name === "Savings rate" ? [`${v}%`, name] : [formatLkr(v), name])}
                    contentStyle={{ borderRadius: 10, fontSize: 12, border: "1px solid var(--border)" }}
                  />
                  <Area
                    yAxisId="income"
                    type="monotone"
                    dataKey="income"
                    stroke="var(--color-primary)"
                    strokeWidth={2.5}
                    fill="url(#incomeFill)"
                    dot={false}
                    name="Monthly income"
                  />
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="savingsRatePct"
                    stroke="#059669"
                    strokeWidth={2.5}
                    dot={false}
                    name="Savings rate"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="mb-1 text-sm font-semibold text-foreground">
              Indexed trend comparison (first month = 100)
            </div>
            <div className="mb-3 text-xs text-muted-foreground">
              Puts income, debt, liquid savings, and investments on the same scale so you can see which
              are rising and which are falling relative to where this profile started — a line above 100
              has grown, below 100 has shrunk.
            </div>
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={evidence.indexedChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} minTickGap={28} />
                  <YAxis tick={{ fontSize: 10 }} width={40} tickFormatter={(v: number) => `${v}`} />
                  <ReferenceLine y={100} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
                  <Tooltip
                    formatter={(v: number, name: string) => [`${v} (index)`, name]}
                    contentStyle={{ borderRadius: 10, fontSize: 12, border: "1px solid var(--border)" }}
                  />
                  {INDEXED_SERIES.filter((s) => s.key !== "debt" || hasDebtSeries).map((s) => (
                    <Line
                      key={s.key}
                      type="monotone"
                      dataKey={s.key}
                      stroke={s.color}
                      strokeWidth={2}
                      dot={false}
                      name={s.name}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="space-y-3">
            {evidence.sections.map((section) => (
              <div
                key={section.heading}
                className="rounded-xl border-l-4 border-l-primary bg-white p-4 shadow-sm"
              >
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {section.heading}
                </div>
                <div className="text-sm leading-relaxed text-foreground">{section.body}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
