import { CheckCircle2, ChevronDown, ChevronRight, XCircle } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type { TaxOptBSearchStrategiesResponseV1, TaxOptBSearchStrategyRowV1 } from "../types";

type Props = {
  data: TaxOptBSearchStrategiesResponseV1 | null;
  expanded: Record<string, boolean>;
  onToggleExpand: (candidateId: string) => void;
};

function BreakdownMetricCards({ row }: { row: TaxOptBSearchStrategyRowV1 }) {
  const b = row.breakdown;
  if (!b) return null;
  const cards: { label: string; value: string }[] = [
    { label: "Employment income", value: formatLkrAmount(b.employment_income_lkr) },
    { label: "Business income", value: formatLkrAmount(b.business_income_lkr) },
    { label: "Other income", value: formatLkrAmount(b.other_income_lkr) },
    { label: "Gross income", value: formatLkrAmount(b.gross_income_lkr) },
    { label: "Assessable (before personal relief)", value: formatLkrAmount(b.assessable_income_lkr) },
    { label: "Personal relief", value: formatLkrAmount(b.personal_relief_lkr) },
    { label: "Statutory deductions", value: formatLkrAmount(b.total_statutory_deductions_lkr) },
    { label: "Total reliefs (personal + statutory)", value: formatLkrAmount(b.total_reliefs_lkr) },
    { label: "Taxable (before slabs)", value: formatLkrAmount(b.taxable_income_lkr) },
    { label: "Total tax", value: formatLkrAmount(b.total_tax_lkr) },
    {
      label: "Effective rate",
      value: b.effective_tax_rate ?? "—",
    },
    {
      label: "Tax saving vs baseline",
      value:
        b.tax_savings_vs_baseline_lkr != null ? formatLkrAmount(b.tax_savings_vs_baseline_lkr) : "—",
    },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-lg border border-border/60 bg-background/60 px-3 py-2.5 shadow-sm"
        >
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {c.label}
          </div>
          <div className="mt-1 font-mono text-sm font-medium tabular-nums text-foreground">{c.value}</div>
        </div>
      ))}
    </div>
  );
}

function MetricsTable({ row }: { row: TaxOptBSearchStrategyRowV1 }) {
  const m = row.metrics;
  if (!m) {
    return (
      <p className="text-xs text-muted-foreground">
        Enable full result detail on the request to include structured tax metrics.
      </p>
    );
  }
  const rows: [string, string][] = [
    ["Gross income (LKR)", formatLkrAmount(m.gross_income)],
    ["Income basis before personal relief", formatLkrAmount(m.income_basis_before_personal_relief)],
    ["Personal relief (annual)", formatLkrAmount(m.personal_relief_annual)],
    ["Taxable after personal relief", formatLkrAmount(m.taxable_after_personal_relief)],
    ["Total statutory deductions", formatLkrAmount(m.total_statutory_deductions)],
    ["Taxable before slab bands", formatLkrAmount(m.taxable_income_before_slabs)],
    ["Final tax (LKR)", formatLkrAmount(m.final_tax)],
    ["Effective tax rate (ratio)", m.effective_tax_rate ?? "—"],
    [
      "Tax saving vs baseline (LKR)",
      m.tax_savings_vs_baseline_lkr != null ? formatLkrAmount(m.tax_savings_vs_baseline_lkr) : "—",
    ],
  ];
  return (
    <div className="overflow-x-auto rounded-md border border-border/60">
      <table className="w-full min-w-[280px] text-left text-xs">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b border-border/40 last:border-0">
              <th className="px-3 py-1.5 font-medium text-muted-foreground">{k}</th>
              <td className="px-3 py-1.5 text-right font-mono tabular-nums">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SearchStrategiesTable({ data, expanded, onToggleExpand }: Props) {
  if (!data) return null;

  return (
    <Card className="border-border/80 shadow-sm">
      <CardHeader className="space-y-1">
        <CardTitle className="text-lg font-semibold tracking-tight">Ranked legal strategies</CardTitle>
        <CardDescription className="text-sm leading-relaxed">
          Legal strategy ranking with transparent rule evaluation — only compliance-passing candidates are listed. Grid{" "}
          <span className="font-mono text-xs">{data.grid_version}</span> · reproducibility id{" "}
          <span className="font-mono text-xs">{data.search_space_id}</span> · evaluated{" "}
          {data.candidates_evaluated}, passing {data.passing_count}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-x-auto rounded-lg border border-border/80">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b bg-muted/40 font-medium">
              <tr>
                <th className="px-3 py-2.5">Rank</th>
                <th className="px-3 py-2.5">Strategy</th>
                <th className="px-3 py-2.5 text-right">Tax (LKR)</th>
                <th className="px-3 py-2.5 text-right">Eff. rate</th>
                <th className="px-3 py-2.5 text-right">Δ vs baseline</th>
                <th className="px-3 py-2.5">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => {
                const isBest = row.rank === 1;
                return (
                  <tr
                    key={row.candidate_id}
                    className={cn(
                      "border-b border-border/50 transition-colors last:border-0",
                      isBest && "bg-primary/[0.06]",
                    )}
                  >
                    <td className="px-3 py-2.5 align-top">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-muted-foreground">{row.rank}</span>
                        {isBest ? (
                          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
                            Best
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <div className="max-w-md font-medium leading-snug">{row.display_name}</div>
                      {row.optimization_summary ? (
                        <p className="mt-1 text-xs text-muted-foreground">{row.optimization_summary}</p>
                      ) : null}
                      <div className="mt-1 font-mono text-[10px] text-muted-foreground">{row.candidate_id}</div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums align-top">
                      {formatLkrAmount(parseDecimalSafe(row.total_tax) ?? row.total_tax)}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums align-top">
                      {row.effective_rate ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums align-top">
                      {row.delta_total_tax_vs_baseline != null
                        ? formatLkrAmount(parseDecimalSafe(row.delta_total_tax_vs_baseline) ?? row.delta_total_tax_vs_baseline)
                        : "—"}
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <button
                        type="button"
                        onClick={() => onToggleExpand(row.candidate_id)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        {expanded[row.candidate_id] ? (
                          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                        )}
                        Breakdown
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {data.rows.map((row) =>
          expanded[row.candidate_id] ? (
            <div
              key={`${row.candidate_id}-detail`}
              className="space-y-4 rounded-xl border border-border/80 bg-muted/15 p-4 text-sm"
            >
              <div>
                <div className="text-sm font-semibold">{row.display_name}</div>
                <div className="font-mono text-xs text-muted-foreground">{row.candidate_id}</div>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Income &amp; tax path (cards)
                  </div>
                  {row.breakdown ? (
                    <BreakdownMetricCards row={row} />
                  ) : (
                    <p className="text-xs text-muted-foreground">No breakdown payload (detail disabled on request).</p>
                  )}
                </div>
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Engine metrics (table, LKR)
                  </div>
                  <MetricsTable row={row} />
                </div>
              </div>

              {(row.rule_summary?.length ?? 0) > 0 ? (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Rule &amp; compliance summary
                  </div>
                  <ul className="list-inside list-disc space-y-1 text-sm text-foreground/90">
                    {row.rule_summary.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {(row.detailed_explanations?.length ?? 0) > 0 ? (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Detailed explanation
                  </div>
                  <div className="space-y-2 text-sm leading-relaxed text-foreground/90">
                    {row.detailed_explanations.map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                </div>
              ) : null}

              {(row.rule_trace?.length ?? 0) > 0 ? (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Rule trace (transparent pass/fail styling)
                  </div>
                  <ul className="space-y-2 text-xs">
                    {row.rule_trace.map((t, idx) => {
                      const passed = (t.outcome ?? "passed") === "passed";
                      return (
                        <li
                          key={`${t.rule_id}-${idx}`}
                          className="flex gap-2 rounded-md border border-border/50 bg-background/50 p-2"
                        >
                          <span className="mt-0.5 shrink-0">
                            {passed ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" aria-hidden />
                            ) : (
                              <XCircle className="h-4 w-4 text-destructive" aria-hidden />
                            )}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                              <span className="font-medium text-foreground">{t.short_label || t.summary.slice(0, 80)}</span>
                              {t.category ? (
                                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                                  {t.category}
                                </span>
                              ) : null}
                            </div>
                            <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{t.rule_id}</div>
                            {t.relief_code ? (
                              <div className="font-mono text-[10px] text-muted-foreground">{t.relief_code}</div>
                            ) : null}
                            <p className="mt-1 text-foreground/90">{t.summary}</p>
                            {t.reference ? (
                              <p className="mt-1 text-[10px] text-muted-foreground">{t.reference}</p>
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : null}

              {row.included_relief_codes.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Grid codes (max cap): {row.included_relief_codes.join(", ")}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">No statutory claims in this candidate.</p>
              )}

              {row.result?.tax_computation ? (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Progressive slabs
                  </div>
                  <ul className="space-y-1 font-mono text-xs text-muted-foreground">
                    {row.result.tax_computation.slab_slices.map((s) => (
                      <li key={s.slab_index}>
                        Band {s.slab_index}: {s.taxable_in_slice} @ {s.rate} → {s.tax_in_slice}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null,
        )}

        <p className="text-[11px] leading-relaxed text-muted-foreground">{data.research_disclaimer}</p>
      </CardContent>
    </Card>
  );
}
