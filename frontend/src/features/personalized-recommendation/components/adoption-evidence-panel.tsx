import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Banknote, PiggyBank, Sparkles, TrendingDown, TrendingUp, Wallet, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { AdoptionEvidence } from "../utils/adoption-evidence";
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

type Props = {
  evidence: AdoptionEvidence;
  strategyName: string;
  onClose: () => void;
};

export function AdoptionEvidenceModal({ evidence, strategyName, onClose }: Props) {
  const style = VERDICT_STYLES[evidence.verdict];
  const TrendIcon = evidence.incomeGrowthPct >= 0 ? TrendingUp : TrendingDown;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className={cn("flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden p-0 ring-1", style.ring)}
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
          <div className="grid grid-cols-3 gap-3">
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
            <div className="mb-3 text-sm font-semibold text-foreground">24-month income &amp; savings-rate trend</div>
            <div className="h-[220px] w-full">
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

          <div className="rounded-xl border-l-4 border-l-primary bg-white p-4 text-sm leading-relaxed text-foreground shadow-sm">
            {evidence.narrative}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
