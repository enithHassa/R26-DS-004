import { Navigate, Outlet, useNavigate } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";

import { useUserSessionStore } from "./store/user-session-store";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "A";
}

/**
 * Scopes the tax-advisory palette (navy + parchment + gold accent) to this module’s pages.
 *
 * These are the auditor-facing admin pages (profile management, ranking,
 * impact, compare) — gated behind the auditor account from the common
 * login page. Taxpayer logins land on TaxWise (`/taxwise`), not AppShell.
 */
export function FinancialModuleLayout() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);

  if (!isAuthenticated || role !== "auditor") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="theme-financial min-h-full rounded-2xl border border-border/60 bg-background shadow-sm ring-1 ring-primary/15">
      <div
        className="flex items-center justify-between gap-3 rounded-t-2xl px-4 py-3 md:px-6"
        style={{
          background:
            "linear-gradient(90deg, var(--primary) 0%, color-mix(in srgb, var(--primary) 70%, var(--tax-accent) 30%) 100%)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-sm font-semibold text-white ring-1 ring-white/25">
            {initials(fullName ?? "Auditor")}
          </div>
          <div>
            <div className="text-sm font-medium leading-tight text-white">
              {fullName ?? "Auditor"}
            </div>
            <div className="flex items-center gap-1 text-[11px] leading-tight text-white/70">
              <ShieldCheck className="h-3 w-3" />
              Auditor access
            </div>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="bg-white/15 text-white hover:bg-white/25"
          onClick={() => {
            logout();
            navigate("/login", { replace: true });
          }}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
      <div
        className="h-1 w-full opacity-90"
        style={{ background: "linear-gradient(90deg, var(--tax-accent) 0%, transparent 100%)" }}
        aria-hidden
      />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  );
}
