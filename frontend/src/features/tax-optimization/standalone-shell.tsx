import { NavLink, Outlet } from "react-router-dom";
import { ArrowLeft, FileText, GitCompareArrows, LayoutList, ShieldCheck, Wallet } from "lucide-react";

import { cn } from "@/lib/utils";

/** Full-page shell for Component B — vertical nav aligned with main dashboard ``AppShell``. */
export function TaxOptimizationStandalone() {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
      isActive
        ? "bg-accent text-accent-foreground"
        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
    );

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col border-r bg-card/50 p-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <Wallet className="h-6 w-6 shrink-0" />
          <div>
            <div className="font-semibold leading-tight">AI Tax Advisory</div>
            <div className="text-xs text-muted-foreground">Sri Lanka Income Tax · 2024/25</div>
          </div>
        </div>

        <div
          className="mb-6 h-px w-full bg-gradient-to-r from-primary/70 via-amber-600/40 to-primary/20"
          aria-hidden
        />

        <div className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Tax optimization
        </div>
        <nav className="flex flex-col gap-1" aria-label="Tax optimization pages">
          <NavLink to="/tax/compliance" className={navLinkClass} end>
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Check my tax
          </NavLink>
          <NavLink to="/tax/compare" className={navLinkClass} end>
            <GitCompareArrows className="h-4 w-4 shrink-0" />
            Compare strategies
          </NavLink>
          <NavLink to="/tax/explorer" className={navLinkClass} end>
            <LayoutList className="h-4 w-4 shrink-0" />
            Find best strategy
          </NavLink>
          <NavLink to="/tax/filing" className={navLinkClass} end>
            <FileText className="h-4 w-4 shrink-0" />
            Tax Filing 2025/26
          </NavLink>
        </nav>

        <div className="mt-auto space-y-4 pt-8">
          <NavLink
            to="/"
            className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" />
            Back to team dashboard
          </NavLink>
          <div className="px-2 text-xs text-muted-foreground">R26-DS-004 · Component B</div>
        </div>
      </aside>

      <main className="min-h-screen flex-1 overflow-y-auto bg-background">
        <div className="mx-auto max-w-6xl p-6 md:p-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
