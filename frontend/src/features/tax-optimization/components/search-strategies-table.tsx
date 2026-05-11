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
import type { TaxOptBSearchStrategiesResponseV1, TaxOptBSearchStrategyRowV1 } from "../types";

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

  return (
    <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
      <CardHeader className="space-y-1 p-6 pb-2">
        <CardTitle className="text-base font-semibold">All evaluated strategies</CardTitle>
        <CardDescription className="text-sm text-muted-foreground">{rankedBySubtitle}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-6 pt-2">
        <div className="overflow-x-auto rounded-lg border border-border/80">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-border text-xs font-medium text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Rank</th>
                <th className="px-4 py-3">Strategy</th>
                <th className="px-4 py-3 text-right">Tax (LKR)</th>
                <th className="px-4 py-3 text-right">Saves vs baseline</th>
                {mlAssisted && (
                  <th className="px-4 py-3" title="How much upfront cash is needed to claim these reliefs">
                    AI Ranking
                  </th>
                )}
                <th className="px-4 py-3">Compliant</th>
                <th className="px-4 py-3">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => {
                const isBest = row.rank === 1;
                const isBaseline = baselineCandidateId != null && row.candidate_id === baselineCandidateId;
                const saves = formatSavesVsBaseline(isBaseline, row.delta_total_tax_vs_baseline);
                const compliant = row.result?.compliance?.passed !== false;
                return (
                  <tr
                    key={row.candidate_id}
                    className={cn(
                      "border-b border-border/60 transition-colors last:border-0",
                      isBest && "bg-primary/[0.04]",
                    )}
                  >
                    <td className="px-4 py-3 align-top">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="tabular-nums text-muted-foreground">{row.rank}</span>
                        {isBest ? (
                          <span className="rounded-full bg-emerald-600/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:text-emerald-200">
                            Best
                          </span>
                        ) : null}
                        {mlAssisted && isBest ? (
                          <span className="rounded-full bg-violet-600/15 px-2 py-0.5 text-[10px] font-semibold text-violet-800 dark:text-violet-200">
                            AI pick
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="max-w-md font-medium leading-snug text-foreground">
                        {displayStrategyName(row.display_name)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right align-top tabular-nums">
                      {formatLkrAmount(parseDecimalSafe(row.total_tax) ?? row.total_tax)}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-3 text-right align-top text-sm tabular-nums",
                        saves.tone === "better" && "font-medium text-emerald-600 dark:text-emerald-400",
                        saves.tone === "worse" && "text-amber-800 dark:text-amber-200",
                        saves.tone === "neutral" && "text-muted-foreground",
                      )}
                    >
                      {saves.text}
                    </td>
                    {mlAssisted && (
                      <td className="px-4 py-3 align-top">
                        {row.ml_assist_rank != null && row.rule_only_rank != null && row.ml_assist_rank !== row.rule_only_rank ? (
                          <span className="rounded-full bg-emerald-600/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:text-emerald-200">
                            ↓ Lower cost
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                    )}
                    <td className="px-4 py-3 align-top">
                      {compliant ? (
                        <span className="font-medium text-emerald-600 dark:text-emerald-400">Yes</span>
                      ) : (
                        <span className="font-medium text-destructive">No</span>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top">
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
                        View breakdown
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
              className="space-y-5 rounded-xl border border-border/80 bg-muted/15 p-5 text-sm"
            >
              <div className="text-base font-semibold text-foreground">
                {displayStrategyName(row.display_name)}
              </div>

              <div>
                <h4 className="mb-3 text-base font-semibold text-foreground">Income &amp; tax breakdown</h4>
                {row.breakdown ? (
                  <BreakdownMetricCards row={row} />
                ) : (
                  <p className="text-xs text-muted-foreground">No breakdown available for this row.</p>
                )}
              </div>

              {(row.rule_summary?.length ?? 0) > 0 ? (
                <div>
                  <h4 className="mb-3 text-base font-semibold text-foreground">Compliance checks</h4>
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
                  <h4 className="mb-3 text-base font-semibold text-foreground">Strategy explanation</h4>
                  <div className="space-y-2 leading-relaxed text-foreground/90">
                    {row.detailed_explanations.map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                </div>
              ) : null}

              {(row.rule_trace?.length ?? 0) > 0 ? (
                <div>
                  <h4 className="mb-3 text-base font-semibold text-foreground">Compliance verification</h4>
                  <ul className="space-y-2">
                    {row.rule_trace.map((t, idx) => {
                      const passed = (t.outcome ?? "passed") === "passed";
                      const reliefExtra = row.applied_relief_summary.find(
                        (a) => a.relief_code && a.relief_code === t.relief_code,
                      );
                      const reliefLine = reliefExtra
                        ? [
                            reliefExtra.claimed != null && reliefExtra.claimed !== ""
                              ? `Claimed: ${formatLkrAmount(reliefExtra.claimed)}`
                              : null,
                            reliefExtra.allowed != null && reliefExtra.allowed !== ""
                              ? `Allowed: ${formatLkrAmount(reliefExtra.allowed)}`
                              : null,
                            reliefExtra.cap != null && reliefExtra.cap !== ""
                              ? `Cap: ${formatLkrAmount(reliefExtra.cap)}`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")
                        : "";
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
                              {sanitizeConsumerLine(t.summary)}
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
          ) : null,
        )}

        <p className="text-center text-xs text-muted-foreground">{data.research_disclaimer}</p>
      </CardContent>
    </Card>
  );
}
