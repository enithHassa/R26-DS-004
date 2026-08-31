import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { getYears } from "../api";
import { yaDisplay } from "../format-lkr";
import { useInterview } from "../session";

export function InterviewEntryPage() {
  const navigate = useNavigate();
  const { session, setAssessmentYear } = useInterview();
  const [draftYear, setDraftYear] = useState(session.assessmentYear);
  const yearsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "years"],
    queryFn: getYears,
    // Azure Postgres can drop idle SSL connections; retry briefly before surfacing.
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
  });
  const years = yearsQuery.data?.assessment_years ?? [];
  const selectedYear = years.includes(draftYear)
    ? draftYear
    : (years[years.length - 1] ?? draftYear);

  function onContinue(): void {
    setAssessmentYear(selectedYear, years);
    void navigate("/optimization-explainable-engine/income");
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Choose year</h2>
        <p className="text-sm text-muted-foreground">
          Assessment years come from this engine’s year views after an Act is
          promoted. Fixture 2025/26 is the usual interview year.
        </p>
      </div>

      {yearsQuery.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading years from the index…
        </p>
      ) : null}

      {yearsQuery.isError ? (
        <div className="space-y-2" role="alert">
          <p className="text-sm text-destructive">
            Could not load years.{" "}
            {yearsQuery.error instanceof Error
              ? yearsQuery.error.message
              : "Start Optimization and Explainable Engine on port 8009, then retry."}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void yearsQuery.refetch()}
            disabled={yearsQuery.isFetching}
          >
            {yearsQuery.isFetching ? "Retrying…" : "Retry"}
          </Button>
        </div>
      ) : null}

      {!yearsQuery.isLoading && !yearsQuery.isError && years.length === 0 ? (
        <p className="text-sm text-muted-foreground" role="status">
          No assessment years yet. Promote a fixture Act (Load new act or
          promote-fixture), then refresh.
        </p>
      ) : null}

      {years.length > 0 ? (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="oe-assessment-year">Assessment year</Label>
          <Select
            id="oe-assessment-year"
            value={selectedYear}
            onChange={(event) => setDraftYear(event.target.value)}
          >
            {years.map((ya) => (
              <option key={ya} value={ya}>
                YA {yaDisplay(ya)}
              </option>
            ))}
          </Select>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={onContinue}
          disabled={years.length === 0 || yearsQuery.isLoading}
        >
          Continue to income
        </Button>
      </div>
    </div>
  );
}
