import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CalendarRange,
  GitCompareArrows,
  Loader2,
  MessageCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

import { getCompare } from "../api";
import {
  compareRowStatus,
  type CompareSeriesRow,
} from "../compare-types";
import { formatLkr, yaDisplay } from "../format-lkr";
import { useInterview } from "../session";
import type { ReliefEntry } from "../types";

function formatCatalogCap(entry: ReliefEntry): string {
  const raw = entry.cap_amount;
  if (raw == null || raw === "") return "—";
  if (entry.unit === "percent" || entry.compare_group_id === "rental_income_relief") {
    return `${String(raw).replace(/%$/, "")}%`;
  }
  if (entry.unit === "text") return String(raw);
  return formatLkr(String(raw));
}

function formatCapCell(
  row: CompareSeriesRow,
  assessmentYear: string,
  compareGroupId?: string,
): string {
  const status = compareRowStatus(row.entry ?? undefined, assessmentYear, compareGroupId);
  if (status === "Removed") return "—";
  const entry = row.entry;
  if (entry?.cap_amount != null && entry.cap_amount !== "") {
    return formatCatalogCap(entry);
  }
  return entry ? "—" : "Not in catalog";
}

function StatusPill({
  status,
}: {
  status: string;
}) {
  if (status === "Removed") {
    return (
      <span className="inline-flex rounded-md bg-destructive/10 px-2 py-0.5 text-[11px] font-semibold text-destructive">
        Removed
      </span>
    );
  }
  if (status === "Last known figure — not confirmed for this year") {
    return (
      <span className="inline-flex rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-950">
        Last known
      </span>
    );
  }
  if (status === "Listed") {
    return (
      <span className="inline-flex rounded-md bg-emerald-100/80 px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
        Listed
      </span>
    );
  }
  return (
    <span className="inline-flex rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
      {status}
    </span>
  );
}

export function InterviewComparePage() {
  const { session, setSelectedCompareGroupId } = useInterview();
  const [groupId, setGroupId] = useState(session.selectedCompareGroupId ?? "");

  const compareQuery = useQuery({
    queryKey: [
      "optimization-explainable-engine",
      "compare",
      session.excludeSourceDocId,
      groupId,
    ],
    queryFn: () => getCompare(session.excludeSourceDocId, groupId || undefined),
    retry: false,
  });

  useEffect(() => {
    if (!compareQuery.data?.groups.length) return;
    const ids = new Set(compareQuery.data.groups.map((g) => g.compare_group_id));
    if (groupId && ids.has(groupId)) return;
    const preferred = session.selectedCompareGroupId;
    const fallback =
      (preferred && ids.has(preferred) ? preferred : null) ??
      compareQuery.data.groups.find((g) => g.compare_group_id === "personal_relief")
        ?.compare_group_id ??
      compareQuery.data.groups[0]?.compare_group_id;
    if (fallback) {
      setGroupId(fallback);
      setSelectedCompareGroupId(fallback);
    }
  }, [
    compareQuery.data,
    groupId,
    session.selectedCompareGroupId,
    setSelectedCompareGroupId,
  ]);

  const series = compareQuery.data?.series ?? [];
  const groupOptions = compareQuery.data?.groups ?? [];
  const indexedYears = compareQuery.data?.assessment_years ?? series.map((row) => row.assessment_year);

  const selectedLabel = useMemo(
    () => groupOptions.find((g) => g.compare_group_id === groupId)?.display_name ?? groupId,
    [groupOptions, groupId],
  );

  const yearRangeLabel = useMemo(() => {
    if (!indexedYears.length) return "every indexed assessment year";
    const first = yaDisplay(indexedYears[0] ?? "");
    const last = yaDisplay(indexedYears[indexedYears.length - 1] ?? "");
    if (!first || first === last) return `YA ${first || last}`;
    return `YA ${first}–${last}`;
  }, [indexedYears]);

  const selectedQuestion = useMemo(() => {
    const prompt = series.find((row) => row.entry?.question_prompt)?.entry?.question_prompt;
    return String(prompt ?? "").trim();
  }, [series]);

  const statusCounts = useMemo(() => {
    let listed = 0;
    let removed = 0;
    let other = 0;
    for (const row of series) {
      const status = compareRowStatus(row.entry ?? undefined, row.assessment_year, groupId);
      if (status === "Listed") listed += 1;
      else if (status === "Removed") removed += 1;
      else other += 1;
    }
    return { listed, removed, other };
  }, [series, groupId]);

  if (compareQuery.isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading multi-year catalogs from RAG…
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-xl border bg-gradient-to-br from-primary/[0.07] via-background to-muted/40 px-5 py-5 sm:px-6 sm:py-6">
        <div
          className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-primary/10 blur-3xl"
          aria-hidden
        />
        <div className="relative max-w-2xl space-y-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
            Year-by-year relief compare
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Compare</h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Pick one relief group and see its catalog value across {yearRangeLabel}. Values come
            from this engine’s year views — outside the taxpayer interview step flow.
          </p>
          <div className="flex flex-wrap gap-2 pt-0.5">
            <Button type="button" size="sm" asChild>
              <Link to="/optimization-explainable-engine">
                Open interview
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Link>
            </Button>
            <Button type="button" size="sm" variant="outline" asChild>
              <Link to="/optimization-explainable-engine/home">Back to home</Link>
            </Button>
          </div>
        </div>
      </section>

      {compareQuery.error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive" role="alert">
          {compareQuery.error instanceof Error
            ? compareQuery.error.message
            : "Failed to load compare data."}
        </p>
      ) : null}

      {session.excludeSourceDocId ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-950">
          Act exclusion from the Acts step is applied:{" "}
          <span className="font-mono text-xs">{session.excludeSourceDocId}</span>
        </p>
      ) : null}

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Choose a relief</h2>
          <p className="text-sm text-muted-foreground">
            Interview as-of and compare years are highlighted when a session exists.
          </p>
        </div>

        {groupOptions.length === 0 ? (
          <p className="rounded-xl border bg-card px-4 py-6 text-sm text-muted-foreground">
            No compare groups in the year views yet. Promote a fixture Act, then refresh.
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <GitCompareArrows className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium">Relief group</p>
                  <p className="text-xs text-muted-foreground">{groupOptions.length} groups available</p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="oe-compare-group">Relief</Label>
                <Select
                  id="oe-compare-group"
                  value={groupId}
                  onChange={(event) => {
                    const next = event.target.value;
                    setGroupId(next);
                    setSelectedCompareGroupId(next || null);
                  }}
                >
                  {groupOptions.map((option) => (
                    <option key={option.compare_group_id} value={option.compare_group_id}>
                      {option.display_name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <MessageCircle className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium">Interview wording</p>
                  <p className="text-xs text-muted-foreground">{selectedLabel || "Selected relief"}</p>
                </div>
              </div>
              {selectedQuestion ? (
                <p className="text-sm leading-relaxed text-foreground">{selectedQuestion}</p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No taxpayer question stored for this group in the live catalog.
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-md bg-emerald-100/80 px-2.5 py-1 text-xs font-medium text-emerald-900">
                  {statusCounts.listed} listed
                </span>
                <span className="rounded-md bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
                  {statusCounts.removed} removed
                </span>
                {statusCounts.other > 0 ? (
                  <span className="rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                    {statusCounts.other} other
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </section>

      {series.length > 0 ? (
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Across assessment years</h2>
              <p className="text-sm text-muted-foreground">
                Caps and status for {selectedLabel || "this relief"} in each indexed year.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-lg border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">
              <CalendarRange className="h-3.5 w-3.5" aria-hidden />
              {yearRangeLabel}
            </span>
          </div>

          <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <caption className="sr-only">
                {selectedLabel} caps across assessment years
              </caption>
              <thead className="border-b bg-muted/30 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-semibold">Assessment year</th>
                  <th className="px-4 py-3 font-semibold">Cap / value</th>
                  <th className="px-4 py-3 font-semibold">Section</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {series.map((row) => {
                  const status = compareRowStatus(
                    row.entry ?? undefined,
                    row.assessment_year,
                    groupId,
                  );
                  const isAsOf = row.assessment_year === session.assessmentYear;
                  const isCompare = row.assessment_year === session.compareYear;
                  return (
                    <tr
                      key={row.assessment_year}
                      className={cn(
                        "border-b border-border/60 last:border-0 transition-colors",
                        isAsOf && "bg-primary/[0.06]",
                        !isAsOf && isCompare && "bg-muted/40",
                      )}
                    >
                      <td className="px-4 py-3.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">YA {yaDisplay(row.assessment_year)}</span>
                          {isAsOf ? (
                            <span className="rounded-md bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
                              As of
                            </span>
                          ) : null}
                          {isCompare ? (
                            <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Compare
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 font-medium tabular-nums">
                        {status === "Removed" ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          formatCapCell(row, row.assessment_year, groupId)
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-muted-foreground">
                        {status === "Removed"
                          ? "—"
                          : (row.section_ref ?? row.entry?.section_ref ?? "—")}
                      </td>
                      <td className="px-4 py-3.5">
                        <StatusPill status={status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
