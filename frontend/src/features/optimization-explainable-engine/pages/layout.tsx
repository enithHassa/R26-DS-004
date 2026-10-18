import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Library, Scale } from "lucide-react";

import { Select } from "@/components/ui/select";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

import { getYears } from "../api";
import { yaDisplay } from "../format-lkr";
import { InterviewProvider, useInterview } from "../session";
import { useActiveProfileId } from "@/features/personalized-recommendation/store/dashboard-store";

const STEPS = [
  { to: "/optimization-explainable-engine", end: true, label: "Years" },
  { to: "/optimization-explainable-engine/acts", end: false, label: "Acts" },
  { to: "/optimization-explainable-engine/income", end: false, label: "Income" },
  { to: "/optimization-explainable-engine/reliefs", end: false, label: "Reliefs" },
  { to: "/optimization-explainable-engine/result", end: false, label: "Result" },
] as const;

function StepNav() {
  const { session, setAssessmentYear } = useInterview();
  const location = useLocation();
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const syncedProfileYaRef = useRef<string | null>(null);
  const yearsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "years"],
    queryFn: getYears,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
  });
  const listed = yearsQuery.data?.assessment_years ?? [];

  // Active taxpayer's profile tax_year is the YA for OE (and Comp 1 rollups).
  useEffect(() => {
    if (listed.length === 0) return;
    const profileYa = normalizeTaxYearToOrm(profileSummary?.taxYear);
    if (profileYa && listed.includes(profileYa)) {
      const key = `${profileSummary?.id ?? ""}:${profileYa}`;
      if (syncedProfileYaRef.current !== key) {
        syncedProfileYaRef.current = key;
        if (session.assessmentYear !== profileYa) {
          setAssessmentYear(profileYa, listed);
        }
      }
      return;
    }
    if (!listed.includes(session.assessmentYear)) {
      const fallback = listed.includes("2025_26")
        ? "2025_26"
        : listed[listed.length - 1];
      setAssessmentYear(fallback, listed);
    }
  }, [
    listed,
    profileSummary?.id,
    profileSummary?.taxYear,
    session.assessmentYear,
    setAssessmentYear,
  ]);
  const years = listed;

  return (
    <div className="space-y-3 border-b border-border pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Scale className="h-5 w-5 text-muted-foreground" aria-hidden />
            Optimization and Explainable Engine
          </h1>
          <p className="text-sm text-muted-foreground">
            Year-specific reliefs from this engine’s year views. Change year to load a
            different catalog.
          </p>
        </div>
        <div className="min-w-[11rem] space-y-1">
          <label htmlFor="oe-ya-select" className="text-[10px] font-medium text-muted-foreground">
            Assessment year
          </label>
          {years.length === 0 ? (
            <p className="text-xs text-muted-foreground" role="status">
              No years indexed yet
            </p>
          ) : (
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
          )}
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
  const activeProfileId = useActiveProfileId();
  return (
    <InterviewProvider profileId={activeProfileId}>
      <InterviewShell />
    </InterviewProvider>
  );
}

/** Standalone compare page — outside the interview step flow. */
export function CompareLayout() {
  const activeProfileId = useActiveProfileId();
  return (
    <InterviewProvider profileId={activeProfileId}>
      <div className="mx-auto max-w-4xl">
        <Outlet />
      </div>
    </InterviewProvider>
  );
}

/** Load new act — owned here, not Catalog Admin. */
export function LoadActLayout() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-1 border-b border-border pb-4">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Library className="h-5 w-5 text-muted-foreground" aria-hidden />
          Load new act
        </h1>
        <p className="text-sm text-muted-foreground">
          Upload a new Act via Act admin. Corpus library and fixture tools live under Past Acts.
        </p>
      </div>
      <Outlet />
    </div>
  );
}

/** Past Acts — ingested corpus library (read-focused). */
export function PastActsLayout() {
  return (
    <div className="mx-auto max-w-4xl">
      <Outlet />
    </div>
  );
}
