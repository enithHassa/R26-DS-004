import { PiggyBank, Wallet, TrendingUp, ShieldAlert } from "lucide-react";

import type { ImpactSummary } from "../types";
import { formatLkr } from "../utils/format-lkr";

type Props = {
  summary: ImpactSummary;
  hasStrategy: boolean;
};

export function ImpactSummaryCards({ summary, hasStrategy }: Props) {
  const oddsPct = (summary.probability_of_net_gain * 100).toFixed(0);

  const items = [
    {
      icon: PiggyBank,
      label: "Money you could save",
      value: formatLkr(summary.expected_total_savings),
      hint: hasStrategy
        ? "Extra cash in your pocket vs. doing nothing, on average"
        : "Based on your current profile, no strategy applied yet",
      tone: "text-emerald-600 dark:text-emerald-400",
    },
    {
      icon: Wallet,
      label: "What you could be worth later",
      value: formatLkr(summary.expected_net_worth),
      hint: `Your estimated total savings & investments after ${summary.horizon_years} years`,
      tone: "text-foreground",
    },
    {
      icon: TrendingUp,
      label: "Odds this plan pays off",
      value: `${oddsPct} in 100`,
      hint: "How often this plan beats doing nothing, across many simulations",
      tone: "text-foreground",
    },
    {
      icon: ShieldAlert,
      label: "Worst realistic case",
      value: formatLkr(summary.value_at_risk_p10),
      hint: "If things go badly, this is roughly how much less you'd have",
      tone: "text-amber-600 dark:text-amber-400",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.label}
            tabIndex={0}
            className="group relative rounded-lg border border-border/80 bg-card/80 p-4 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </div>
            <div className={`mt-1 text-lg font-semibold tabular-nums ${item.tone}`}>
              {item.value}
            </div>

            <div
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-10 mt-2 w-60 -translate-x-1/2 rounded-md border border-border bg-popover p-3 text-sm leading-snug text-popover-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
            >
              {item.hint}
            </div>
          </div>
        );
      })}
    </div>
  );
}
