import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

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

function statusCell(
  entry: ReliefEntry | null | undefined,
  assessmentYear: string,
  compareGroupId?: string,
): string {
  const status = compareRowStatus(entry, assessmentYear, compareGroupId);
  return status;
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

  const selectedLabel = useMemo(
    () => groupOptions.find((g) => g.compare_group_id === groupId)?.display_name ?? groupId,
    [groupOptions, groupId],
  );

  if (compareQuery.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading multi-year catalogs from RAG…
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          Pick one relief group and see its catalog value for every supported assessment year
          (YA 2018/19–2025/26). Interview as-of and compare years are highlighted when an
          interview session exists.
        </p>
        {session.excludeSourceDocId ? (
          <p className="text-xs text-amber-800 dark:text-amber-200">
            Act exclusion from the Acts step is applied:{" "}
            <span className="font-mono">{session.excludeSourceDocId}</span>
          </p>
        ) : null}
      </div>

      {compareQuery.error ? (
        <p className="text-sm text-destructive" role="alert">
          {compareQuery.error instanceof Error
            ? compareQuery.error.message
            : "Failed to load compare data."}
        </p>
      ) : null}

      {groupOptions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No compare groups in the year views yet. Promote a fixture Act, then
          refresh.
        </p>
      ) : (
        <div className="max-w-md space-y-2">
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
      )}

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <caption className="sr-only">
            {selectedLabel} caps across assessment years
          </caption>
          <thead className="border-b bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Assessment year</th>
              <th className="px-3 py-2 font-medium">Cap / value</th>
              <th className="px-3 py-2 font-medium">Section</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {series.map((row) => {
              const status = compareRowStatus(
                row.entry ?? undefined,
                row.assessment_year,
                groupId,
              );
              return (
                <tr
                  key={row.assessment_year}
                  className={
                    row.assessment_year === session.assessmentYear
                      ? "bg-primary/5"
                      : row.assessment_year === session.compareYear
                        ? "bg-muted/30"
                        : undefined
                  }
                >
                  <td className="px-3 py-2 font-medium">
                    YA {yaDisplay(row.assessment_year)}
                    {row.assessment_year === session.assessmentYear ? (
                      <span className="ml-1 text-[10px] text-muted-foreground">(as of)</span>
                    ) : null}
                    {row.assessment_year === session.compareYear ? (
                      <span className="ml-1 text-[10px] text-muted-foreground">(compare)</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    {status === "Removed" ? (
                      <span className="text-destructive">—</span>
                    ) : (
                      formatCapCell(row, row.assessment_year, groupId)
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {status === "Removed" ? "—" : (row.section_ref ?? "—")}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {status === "Removed" ? (
                      <span className="font-medium text-destructive">Removed</span>
                    ) : status === "Last known figure — not confirmed for this year" ? (
                      <span className="text-amber-800 dark:text-amber-200">{status}</span>
                    ) : (
                      statusCell(row.entry, row.assessment_year, groupId)
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/home">Back to home</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine">Open interview</Link>
        </Button>
      </div>
    </div>
  );
}
