import type { ImpactSummary } from "../types";
import { formatLkr } from "../utils/format-lkr";

type Props = {
  summary: ImpactSummary;
  hasStrategy: boolean;
};

export function ImpactSummaryCards({ summary, hasStrategy }: Props) {
  const items = [
    {
      label: "Expected total tax savings",
      value: formatLkr(summary.expected_total_savings),
      hint: hasStrategy ? "Baseline vs strategy paths" : "Baseline only",
    },
    {
      label: "Expected net worth (horizon end)",
      value: formatLkr(summary.expected_net_worth),
      hint: `After ${summary.horizon_years} years`,
    },
    {
      label: "Probability of net gain",
      value: `${(summary.probability_of_net_gain * 100).toFixed(1)}%`,
      hint: "Strategy beats baseline at horizon",
    },
    {
      label: "Value at risk (P10 net gain)",
      value: formatLkr(summary.value_at_risk_p10),
      hint: "Downside vs baseline",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border/80 bg-card/80 p-4 shadow-sm"
        >
          <div className="text-xs text-muted-foreground">{item.label}</div>
          <div className="mt-1 text-lg font-semibold tabular-nums">{item.value}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">{item.hint}</div>
        </div>
      ))}
    </div>
  );
}
