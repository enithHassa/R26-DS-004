import { NavLink, Outlet, useLocation } from "react-router-dom";
import { MessageCircle } from "lucide-react";

import { ReliefInterviewProvider, useReliefInterview } from "./session";
import { yaDisplay } from "./types";

const STEPS = [
  { to: "/adaptive-tax/relief-interview", end: true, label: "Years" },
  { to: "/adaptive-tax/relief-interview/income", end: false, label: "Income" },
  { to: "/adaptive-tax/relief-interview/reliefs", end: false, label: "Reliefs" },
  { to: "/adaptive-tax/relief-interview/result", end: false, label: "Result" },
  { to: "/adaptive-tax/relief-interview/report", end: false, label: "Report" },
] as const;

function StepNav() {
  const { session } = useReliefInterview();
  const location = useLocation();

  return (
    <div className="space-y-3 border-b border-border pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <MessageCircle className="h-5 w-5 text-muted-foreground" aria-hidden />
            Relief Interview
          </h1>
          <p className="text-sm text-muted-foreground">
            Act-backed relief interview for one assessment year.
          </p>
        </div>
        <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            YA {yaDisplay(session.assessmentYear)}
          </span>
        </div>
      </div>
      <nav className="flex flex-wrap gap-1" aria-label="Relief Interview steps">
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

function ReliefInterviewShell() {
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <StepNav />
      <Outlet />
    </div>
  );
}

export function ReliefInterviewLayout() {
  return (
    <ReliefInterviewProvider>
      <ReliefInterviewShell />
    </ReliefInterviewProvider>
  );
}
