import { GitCompare } from "lucide-react";

import { ReliefInterviewComparePage } from "./relief-interview/compare";
import { ReliefInterviewProvider } from "./relief-interview/session";

/** Standalone Adaptive Tax page — not a Relief Interview stepper step. */
export function AdaptiveTaxComparePage() {
  return (
    <ReliefInterviewProvider>
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <GitCompare className="h-5 w-5 text-muted-foreground" aria-hidden />
            Compare
          </h1>
          <p className="text-sm text-muted-foreground">
            Year-to-year catalog values for one relief. This is an Adaptive Tax
            page, not a step in the taxpayer Relief Interview.
          </p>
        </div>
        <ReliefInterviewComparePage />
      </div>
    </ReliefInterviewProvider>
  );
}
