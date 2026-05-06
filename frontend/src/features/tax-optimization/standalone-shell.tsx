import { NavLink, Outlet } from "react-router-dom";
import { ArrowLeft, ShieldCheck } from "lucide-react";

/** Full-page shell for Component B — not shown in the team sidebar (instructor / separate demo). */
export function TaxOptimizationStandalone() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b bg-card/30 px-4 py-4 md:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-8 w-8 shrink-0 text-primary" />
            <div>
              <div className="text-lg font-semibold tracking-tight">Tax Strategy Optimization</div>
              <div className="text-xs text-muted-foreground">
                Component B — Function 1 (separate page for instructor / demo)
              </div>
            </div>
          </div>
          <NavLink
            to="/profile"
            className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to team dashboard
          </NavLink>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto max-w-6xl p-6 md:p-10">
          <Outlet />
        </div>
      </main>
      <footer className="border-t py-3 text-center text-xs text-muted-foreground">
        R26-DS-004 · Component B
      </footer>
    </div>
  );
}
