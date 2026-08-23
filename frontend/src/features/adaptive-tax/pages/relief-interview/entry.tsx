import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { useReliefInterview } from "./session";
import {
  RELIEF_INTERVIEW_YAS,
  adjacentCompareYa,
  yaDisplay,
  type ReliefInterviewYa,
} from "./types";

export function ReliefInterviewEntryPage() {
  const navigate = useNavigate();
  const { session, setYears } = useReliefInterview();
  const [assessmentYear, setAssessmentYear] = useState<ReliefInterviewYa>(
    session.assessmentYear,
  );

  function onContinue(): void {
    // Compare YA is derived (adjacent prior year) for the Compare step — not chosen here.
    setYears(assessmentYear, adjacentCompareYa(assessmentYear));
    void navigate("/adaptive-tax/relief-interview/income");
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Choose year</h2>
        <p className="text-sm text-muted-foreground">
          Select the assessment year for this interview. Reliefs and tax use this
          year only. Supported range is YA 2018/19–2025/26 (Phase 1 harvest).
        </p>
      </div>

      <div className="max-w-sm space-y-2">
        <Label htmlFor="ri-assessment-year">Assessment year</Label>
        <Select
          id="ri-assessment-year"
          value={assessmentYear}
          onChange={(event) =>
            setAssessmentYear(event.target.value as ReliefInterviewYa)
          }
        >
          {RELIEF_INTERVIEW_YAS.map((ya) => (
            <option key={ya} value={ya}>
              YA {yaDisplay(ya)}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={onContinue}>
          Continue to income
        </Button>
      </div>
    </div>
  );
}
