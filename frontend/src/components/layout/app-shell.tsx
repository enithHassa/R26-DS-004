import { Component, type ErrorInfo, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Wallet } from "lucide-react";

import { AuditorWorkspacePanel } from "@/components/auditor/auditor-workspace-panel";
import { AuditorWorkspaceMobileBar } from "@/components/auditor/auditor-workspace-mobile-bar";
import { features } from "@/features";
import { cn } from "@/lib/utils";

class RouteErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Route render failed", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="space-y-2" role="alert">
          <p className="font-medium">This page failed to render.</p>
          <p className="text-sm text-muted-foreground">{this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Reset the boundary when the URL changes so a prior route error does not stick. */
function RouteErrorOutlet() {
  const location = useLocation();
  return (
    <RouteErrorBoundary key={location.pathname}>
      <Outlet />
    </RouteErrorBoundary>
  );
}

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden h-full w-64 shrink-0 flex-col overflow-hidden border-r bg-card/50 p-4 md:flex">
        <div className="mb-8 flex shrink-0 items-center gap-2 px-2">
          <Wallet className="h-6 w-6" />
          <div>
            <div className="font-semibold">AI Tax Advisory</div>
            <div className="text-xs text-muted-foreground">Decision Support</div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {features.map((feature) => (
            <div key={feature.id} className="mb-6">
              {feature.navRoot ? (
                <NavLink
                  to={feature.navRoot}
                  end
                  className={({ isActive }) =>
                    cn(
                      "mb-1 block rounded-md px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors",
                      isActive
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                    )
                  }
                >
                  {feature.title}
                </NavLink>
              ) : (
                <div className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {feature.title}
                </div>
              )}
              <nav className="flex flex-col gap-1">
                {feature.nav.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                        isActive
                          ? "bg-accent text-accent-foreground"
                          : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                      )
                    }
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          ))}
        </div>

        <div className="mt-auto shrink-0 px-2 pt-4 text-xs text-muted-foreground">R26-DS-004</div>
      </aside>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-6 md:p-10">
          <AuditorWorkspaceMobileBar />
          <RouteErrorOutlet />
        </div>
      </main>

      <AuditorWorkspacePanel />
    </div>
  );
}
