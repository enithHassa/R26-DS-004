import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { GitCompare, Scale } from "lucide-react";

import { Select } from "@/components/ui/select";

import { getYears } from "../api";
import { yaDisplay } from "../format-lkr";
import { InterviewProvider, useInterview } from "../session";

const STEPS = [
  { to: "/optimization-explainable", end: true, label: "Years" },
  { to: "/optimization-explainable/acts", end: false, label: "Acts" },
  { to: "/optimization-explainable/income", end: false, label: "Income" },
  { to: "/optimization-explainable/reliefs", end: false, label: "Reliefs" },
  { to: "/optimization-explainable/result", end: false, label: "Result" },
] as const;

function StepNav() {
  const { session, setAssessmentYear } = useInterview();
  const location = useLocation();
  const yearsQuery = useQuery({
    queryKey: ["optimization-explainable", "years"],
    queryFn: getYears,
    retry: false,
  });
  const listed = yearsQuery.data?.assessment_years;
  const years =
    listed && listed.includes(session.assessmentYear)
      ? listed
      : listed && listed.length > 0
        ? [...listed, session.assessmentYear]
        : [session.assessmentYear];

  return (
    <div className="space-y-3 border-b border-border pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Scale className="h-5 w-5 text-muted-foreground" aria-hidden />
            Optimization and Explainable
          </h1>
          <p className="text-sm text-muted-foreground">
            Year-specific reliefs from the RAG index. Change year to load a different
            catalog — no hardcoded relief list.
          </p>
        </div>
        <div className="min-w-[11rem] space-y-1">
          <label htmlFor="oe-ya-select" className="text-[10px] font-medium text-muted-foreground">
            Assessment year
          </label>
          <Select
            id="oe-ya-select"
            value={session.assessmentYear}
            onChange={(event) => setAssessmentYear(event.target.value, years)}
          >
            {years.map((ya) => (
              <option key={ya} value={ya}>
                YA {yaDisplay(ya)}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <nav className="flex flex-wrap gap-1" aria-label="Interview steps">
        {STEPS.map((step) => {
          const active = step.end
            ? location.pathname === step.to
            : location.pathname.startsWith(step.to);
          return (
            <NavLink
              key={step.to}
              to={step.to}
              end={step.end}
              className={
                active
                  ? "rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                  : "rounded-md px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
              }
            >
              {step.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}

function InterviewShell() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <StepNav />
      <Outlet />
    </div>
  );
}

export function InterviewLayout() {
  return (
    <InterviewProvider>
      <InterviewShell />
    </InterviewProvider>
  );
}

/** Standalone compare page — outside the interview step flow. */
export function CompareLayout() {
  return (
    <InterviewProvider>
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="space-y-1 border-b border-border pb-4">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <GitCompare className="h-5 w-5 text-muted-foreground" aria-hidden />
            Compare
          </h1>
          <p className="text-sm text-muted-foreground">
            Year-to-year catalog values for one relief. This is an Optimization and Explainable
            page, not a step in the taxpayer interview flow. Values come from the RAG index.
          </p>
        </div>
        <Outlet />
      </div>
    </InterviewProvider>
  );
}
