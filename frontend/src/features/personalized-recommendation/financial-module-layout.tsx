import { Outlet } from "react-router-dom";

/**
 * Scopes the tax-advisory palette (navy + parchment + gold accent) to this module’s pages.
 */
export function FinancialModuleLayout() {
  return (
    <div className="theme-financial min-h-full rounded-2xl border border-border/60 bg-background p-4 shadow-sm ring-1 ring-primary/15 md:p-6">
      <div
        className="mb-6 h-1.5 w-full max-w-lg rounded-full opacity-95 shadow-sm shadow-primary/20"
        style={{
          background:
            "linear-gradient(90deg, var(--primary) 0%, var(--tax-accent) 50%, var(--primary) 100%)",
        }}
        aria-hidden
      />
      <Outlet />
    </div>
  );
}
