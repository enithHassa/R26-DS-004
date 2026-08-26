import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

import { getActs, getReliefs } from "../api";
import { formatLkr, yaDisplay } from "../format-lkr";
import { parseCap } from "../types";
import { useInterview } from "../session";

export function InterviewActsPage() {
  const { session, setExcludeSourceDocId } = useInterview();
  const { assessmentYear, excludeSourceDocId } = session;

  const actsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "acts", assessmentYear],
    queryFn: () => getActs(assessmentYear),
    enabled: Boolean(assessmentYear),
    retry: false,
  });

  const reliefsQuery = useQuery({
    queryKey: [
      "optimization-explainable-engine",
      "reliefs",
      assessmentYear,
      excludeSourceDocId,
    ],
    queryFn: () => getReliefs(assessmentYear, excludeSourceDocId),
    enabled: Boolean(assessmentYear),
    retry: false,
  });

  const personal = (reliefsQuery.data?.entries ?? []).find(
    (entry) => entry.compare_group_id === "personal_relief",
  );
  const personalCap = parseCap(personal?.cap_amount);

  function toggleRemove(sourceDocId: string, remove: boolean): void {
    setExcludeSourceDocId(remove ? sourceDocId : null);
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Acts in YA {yaDisplay(assessmentYear)}</h2>
        <p className="text-sm text-muted-foreground">
          Toggle removes this act’s rows from this year’s catalog. PDFs and index
          files stay on disk — load/change/remove without deleting sources.
        </p>
      </div>

      {actsQuery.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading acts from the index…
        </p>
      ) : null}

      {actsQuery.isError ? (
        <p className="text-sm text-destructive" role="alert">
          Could not load acts. Start Optimization and Explainable Engine on port 8009.
        </p>
      ) : null}

      <ul className="space-y-3">
        {(actsQuery.data?.acts ?? []).map((act) => {
          const removed = excludeSourceDocId === act.source_doc_id;
          return (
            <li
              key={act.source_doc_id}
              className="space-y-2 rounded-md border p-3"
            >
              <p className="text-sm font-medium">{act.title}</p>
              <p className="text-xs text-muted-foreground">
                {act.source_doc_id}
                {" · "}
                {act.relief_count} relief{act.relief_count === 1 ? "" : "s"}
                {act.rate_band_count
                  ? ` · ${act.rate_band_count} rate band${act.rate_band_count === 1 ? "" : "s"}`
                  : ""}
              </p>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={removed}
                  onChange={(event) =>
                    toggleRemove(act.source_doc_id, event.target.checked)
                  }
                />
                Remove this act’s rules
              </label>
            </li>
          );
        })}
      </ul>

      <div className="rounded-md border bg-muted/30 p-3 text-sm">
        <p className="text-xs text-muted-foreground">Personal relief (this YA)</p>
        <p className="font-medium">
          {reliefsQuery.isLoading
            ? "…"
            : personalCap == null
              ? "—"
              : formatLkr(personalCap)}
        </p>
        {personal?.source_doc_id ? (
          <p className="text-xs text-muted-foreground">{personal.source_doc_id}</p>
        ) : null}
        {excludeSourceDocId ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Excluding {excludeSourceDocId}. Remaining row for this group is used
            (same idea as year selection).
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine">Back to year</Link>
        </Button>
        <Button type="button" asChild>
          <Link to="/optimization-explainable-engine/income">Continue to income</Link>
        </Button>
      </div>
    </div>
  );
}
