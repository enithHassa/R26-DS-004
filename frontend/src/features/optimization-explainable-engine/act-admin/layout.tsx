import { useEffect } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";

import { clearActAdminSession } from "./session";

const INTERNAL_NAV = [
  { to: "/optimization-explainable-engine/act-admin", end: true, label: "Queue" },
  { to: "/optimization-explainable-engine/act-admin/upload", end: false, label: "Add New Act" },
] as const;

/**
 * Act admin is gated by the global auditor login at ``/login``.
 * The engine API token is injected from ``VITE_OE_ENGINE_ACT_ADMIN_TOKEN``
 * (default ``local-oe-act-admin``) — no middle login form.
 */
export function ActAdminLayout() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);

  useEffect(() => {
    // Drop any leftover middle-login session from older builds.
    clearActAdminSession();
  }, []);

  if (!isAuthenticated || role !== "auditor") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <ShieldCheck className="h-5 w-5 text-muted-foreground" aria-hidden />
            Act admin
          </h1>
          <p className="text-sm text-muted-foreground">
            Upload a new Inland Revenue Act PDF for this engine. This is not the taxpayer interview.
          </p>
          <nav className="flex flex-wrap gap-1 pt-2" aria-label="Act admin">
            {INTERNAL_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive
                    ? "rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                    : "rounded-md px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Reviewer{" "}
            <span className="font-medium text-foreground">{fullName || "Auditor"}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              clearActAdminSession();
              logout();
              navigate("/login", { replace: true });
            }}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
