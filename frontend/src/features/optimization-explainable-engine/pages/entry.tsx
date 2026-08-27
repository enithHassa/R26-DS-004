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
    retry: false,
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
        <p className="text-sm text-destructive" role="alert">
          Could not load years. Start Optimization and Explainable Engine on port 8009,
          then refresh.
        </p>
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
