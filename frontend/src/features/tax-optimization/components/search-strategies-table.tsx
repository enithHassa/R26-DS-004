import { Check, CheckCircle2, ChevronDown, ChevronRight, XCircle } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type {
  TaxOptBSearchStrategiesResponseV1,
  TaxOptBSearchStrategyRowV1,
} from "../types";

type Props = {
  data: TaxOptBSearchStrategiesResponseV1 | null;
  expanded: Record<string, boolean>;
  onToggleExpand: (candidateId: string) => void;
  mlAssisted?: boolean;
  baselineCandidateId: string | null;
  rankedBySubtitle: string;
};

function displayStrategyName(raw: string): string {
  return raw.replace(/\bcap_subset_\d+\b/gi, "").replace(/\s+/g, " ").trim();
}

function sanitizeConsumerLine(s: string): string {
  return s
    .replace(/\bcap_subset_\d+\b/gi, "")
    .replace(/\bsearch:[\w_.]+\b/gi, "")
    .replace(/\bit220[a-z0-9_]+\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function stripRuleTraceAmounts(summary: string): string {
  const s = sanitizeConsumerLine(summary);
  const idx = s.search(/\s+Allowed\s+LKR\s+/i);
  if (idx > 0) return `${s.slice(0, idx).trim()}.`;
  return s.replace(/\s*\(claimed\s+LKR[^)]*\)\s*\.?$/i, "").trim();
}

function formatReliefAmountsLine(
  relief: NonNullable<TaxOptBSearchStrategyRowV1["applied_relief_summary"][number]>,
): string | null {
  const parts: string[] = [];
  if (relief.allowed != null && relief.allowed !== "") {
    parts.push(`Allowed: ${formatLkrAmount(relief.allowed)}`);
  }
  if (
    relief.cap != null &&
    relief.cap !== "" &&
    relief.allowed != null &&
    relief.allowed !== "" &&
    relief.cap !== relief.allowed
  ) {
    parts.push(`Statutory cap: ${formatLkrAmount(relief.cap)}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function formatSavesVsBaseline(
  isBaselineRow: boolean,
  deltaStr: string | null | undefined,
): { text: string; tone: "neutral" | "better" | "worse" } {
  if (isBaselineRow) return { text: "—", tone: "neutral" };
  if (deltaStr == null || deltaStr === "") return { text: "—", tone: "neutral" };
  const delta = parseDecimalSafe(deltaStr);
  if (delta == null) return { text: "—", tone: "neutral" };
  if (delta === 0) return { text: "Same as baseline", tone: "neutral" };
  const abs = Math.abs(Math.round(delta));
  if (delta < 0) return { text: `LKR ${abs.toLocaleString("en-LK")} less`, tone: "better" };
  return { text: `LKR ${abs.toLocaleString("en-LK")} more`, tone: "worse" };
}

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
    { label: "Effective rate", value: b.effective_tax_rate ?? "—" },
    {
      label: "Tax saving vs baseline",
      value: b.tax_savings_vs_baseline_lkr != null ? formatLkrAmount(b.tax_savings_vs_baseline_lkr) : "—",
    },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-lg border border-border/60 bg-background/60 px-3 py-2.5 shadow-sm"
        >
          <div className="text-xs font-medium text-muted-foreground">{c.label}</div>
          <div className="mt-1 text-sm font-medium tabular-nums text-foreground">{c.value}</div>
        </div>
      ))}
    </div>
  );
}

export function SearchStrategiesTable({
  data,
  expanded,
  onToggleExpand,
  mlAssisted = false,
  baselineCandidateId,
  rankedBySubtitle,
}: Props) {
  if (!data) return null;

  const mlScores = data.rows.map((r) => parseDecimalSafe(r.ml_score ?? "") ?? 0);
  const maxMlScore = Math.max(...mlScores, 0.0001);

  return (
    <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
      <CardHeader className="space-y-1 p-6 pb-4">
        <CardTitle className="text-base font-semibold">All evaluated strategies</CardTitle>
        <CardDescription className="text-sm text-muted-foreground">{rankedBySubtitle}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 p-6 pt-0">

        {/* Column header row */}
        <div className="hidden grid-cols-[2.5rem_1fr_9rem_9rem_6rem_7rem] gap-3 px-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground sm:grid">
          <div>#</div>
          <div>Strategy</div>
          <div className="text-right">Tax you&apos;d pay</div>
          <div className="text-right">You save</div>
          <div className="text-center">IRD rules</div>
          <div></div>
        </div>

        {data.rows.map((row) => {
          const isBest = row.rank === 1;
          const isBaseline = baselineCandidateId != null && row.candidate_id === baselineCandidateId;
          const saves = formatSavesVsBaseline(isBaseline, row.delta_total_tax_vs_baseline);
          const compliant = row.result?.compliance?.passed !== false;
          const isExpanded = expanded[row.candidate_id];

          return (
            <div key={row.candidate_id}>
              {/* Strategy card row */}
              <div
                className={cn(
                  "grid grid-cols-1 gap-3 rounded-xl border px-4 py-3.5 transition-colors sm:grid-cols-[2.5rem_1fr_9rem_9rem_6rem_7rem] sm:items-center",
                  isBest
                    ? "border-primary/40 bg-primary/5"
                    : isBaseline
                      ? "border-border/60 bg-muted/20"
                      : "border-border/50 bg-background hover:bg-muted/10",
                )}
              >
                {/* Rank + badges */}
                <div className="flex items-center gap-2 sm:flex-col sm:items-start sm:gap-1">
                  <span
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                      isBest
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {row.rank}
                  </span>
                  {isBest && (
                    <span className="rounded-full bg-primary-600 px-2 py-0.5 text-[10px] font-semibold text-white sm:hidden">
                      Best
                    </span>
                  )}
                </div>

                {/* Strategy name + badges (desktop) */}
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("font-medium leading-snug text-foreground", isBest && "font-semibold")}>
                      {displayStrategyName(row.display_name)}
                    </span>
                    {isBest && (
                      <span className="hidden rounded-full bg-primary-600 px-2.5 py-0.5 text-[10px] font-semibold text-white sm:inline">
                        Best pick
                      </span>
                    )}
                    {mlAssisted && isBest && (
                      <span className="rounded-full bg-amber-500 px-2.5 py-0.5 text-[10px] font-semibold text-white">
                        AI recommended
                      </span>
                    )}
                    {isBaseline && (
                      <span className="rounded-full bg-slate-400 px-2.5 py-0.5 text-[10px] font-semibold text-white">
                        No claims
                      </span>
                    )}
                  </div>
                  {mlAssisted && row.ml_score != null && !isBaseline && (
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className="text-[10px] font-medium text-muted-foreground">AI score</span>
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            isBest ? "bg-primary" : "bg-slate-400",
                          )}
                          style={{
                            width: `${Math.min(100, Math.max(4, ((parseDecimalSafe(row.ml_score) ?? 0) / maxMlScore) * 100))}%`,
                          }}
                        />
                      </div>
                      <span className="text-[10px] tabular-nums text-muted-foreground">
                        {(((parseDecimalSafe(row.ml_score) ?? 0) / maxMlScore) * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Tax amount */}
                <div className="sm:text-right">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground sm:hidden">
                    Tax you&apos;d pay
                  </div>
                  <div className="tabular-nums font-semibold text-foreground">
                    {formatLkrAmount(parseDecimalSafe(row.total_tax) ?? row.total_tax)}
                  </div>
                </div>

                {/* Savings */}
                <div className="sm:text-right">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground sm:hidden">
                    You save
                  </div>
                  <div
                    className={cn(
                      "tabular-nums font-semibold",
                      saves.tone === "better" && "text-emerald-600 dark:text-emerald-400",
                      saves.tone === "worse" && "text-red-600 dark:text-red-400",
                      saves.tone === "neutral" && "text-muted-foreground",
                    )}
                  >
                    {saves.text}
                  </div>
                </div>

                {/* Compliant badge */}
                <div className="sm:flex sm:justify-center">
                  {compliant ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2.5 py-0.5 text-[11px] font-semibold text-white">
                      <Check className="h-3 w-3" />
                      Compliant
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-0.5 text-[11px] font-semibold text-white">
                      <XCircle className="h-3 w-3" />
                      Fails IRD
                    </span>
                  )}
                </div>

                {/* Expand button */}
                <div className="sm:flex sm:justify-end">
                  <button
                    type="button"
                    onClick={() => onToggleExpand(row.candidate_id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                      isExpanded
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-border bg-background text-foreground hover:bg-muted/50",
                    )}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                    )}
                    Details
                  </button>
                </div>
              </div>

              {/* Expanded breakdown */}
              {isExpanded && (
                <div className="mx-1 space-y-5 rounded-b-xl border border-t-0 border-border/60 bg-muted/10 p-5 text-sm">
                  <div className="text-base font-semibold text-foreground">
                    {displayStrategyName(row.display_name)}
                  </div>

                  <div>
                    <h4 className="mb-3 text-sm font-semibold text-foreground">Income &amp; tax breakdown</h4>
                    {row.breakdown ? (
                      <BreakdownMetricCards row={row} />
                    ) : (
                      <p className="text-xs text-muted-foreground">No breakdown available for this row.</p>
                    )}
                  </div>

                  {(row.rule_summary?.length ?? 0) > 0 ? (
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-foreground">Compliance checks</h4>
                      <ul className="space-y-2">
                        {row.rule_summary.map((line, i) => (
                          <li key={i} className="flex gap-2 text-foreground/90">
                            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                            <span>{sanitizeConsumerLine(line)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {(row.detailed_explanations?.length ?? 0) > 0 ? (
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-foreground">Strategy explanation</h4>
                      <div className="space-y-2 leading-relaxed text-foreground/90">
                        {row.detailed_explanations.map((para, i) => (
                          <p key={i}>{para}</p>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {(row.rule_trace?.length ?? 0) > 0 ? (
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-foreground">Compliance verification</h4>
                      <ul className="space-y-2">
                        {row.rule_trace
                          .filter((t) => t.relief_code != null && t.category !== "compliance_meta")
                          .map((t, idx) => {
                          const passed = (t.outcome ?? "passed") === "passed";
                          const reliefExtra = row.applied_relief_summary.find(
                            (a) => a.relief_code && a.relief_code === t.relief_code,
                          );
                          const reliefLine = reliefExtra ? formatReliefAmountsLine(reliefExtra) : null;
                          return (
                            <li
                              key={`trace-${idx}`}
                              className="flex gap-2 rounded-lg border border-border/50 bg-background/60 p-3"
                            >
                              <span className="mt-0.5 shrink-0">
                                {passed ? (
                                  <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                                ) : (
                                  <XCircle className="h-4 w-4 text-destructive" />
                                )}
                              </span>
                              <div className="min-w-0 flex-1 space-y-1">
                                <p className="text-sm leading-relaxed text-foreground">
                                  {stripRuleTraceAmounts(t.summary)}
                                </p>
                                {reliefLine ? (
                                  <p className="text-xs text-muted-foreground">{reliefLine}</p>
                                ) : null}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}

                </div>
              )}
            </div>
          );
        })}

        <p className="pt-2 text-center text-xs text-muted-foreground">
          Tax figures are calculated using IRD 2025/26 rates and relief thresholds. This is not legal or filing advice — verify all figures against current Inland Revenue notices before use.
        </p>
      </CardContent>
    </Card>
  );
}
