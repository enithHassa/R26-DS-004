import type { ReactNode } from "react";
import { NavLink, Navigate, useLocation } from "react-router-dom";
import {
  Bell,
  Calculator,
  ChevronRight,
  LayoutDashboard,
  ListChecks,
  LogOut,
  MessageSquare,
  Receipt,
  Sparkles,
  TrendingUp,
  UserRound,
  Wallet,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import {
  TAXWISE_BASE,
  TAXWISE_FINANCIAL_IMPACT,
  TAXWISE_OE,
  TAXWISE_OE_INCOME,
  TAXWISE_OE_RELIEFS,
  TAXWISE_OE_RESULT,
  TAXWISE_PROFILE,
  TAXWISE_RECOMMENDATIONS,
} from "@/pages/user-view/paths";

import "@/pages/user-view/user-view-theme.css";

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, to: TAXWISE_BASE, enabled: true },
  {
    key: "transactions",
    label: "Transactions",
    icon: Receipt,
    to: `${TAXWISE_BASE}/transactions`,
    enabled: false,
  },
  {
    key: "ai-advisor",
    label: "AI Advisor",
    icon: MessageSquare,
    to: `${TAXWISE_BASE}/ai-advisor`,
    enabled: false,
  },
  {
    key: "profile",
    label: "Profile",
    icon: UserRound,
    to: TAXWISE_PROFILE,
    enabled: true,
  },
] as const;

const RECOMMENDATION_SUB_ITEMS = [
  { label: "Recommendations", icon: Sparkles, to: TAXWISE_RECOMMENDATIONS },
  { label: "Financial Impact", icon: TrendingUp, to: TAXWISE_FINANCIAL_IMPACT },
] as const;

const OE_SUB_ITEMS = [
  { label: "Overview", icon: TrendingUp, to: TAXWISE_OE, end: true },
  { label: "My Income", icon: Wallet, to: TAXWISE_OE_INCOME, end: false },
  { label: "My Reliefs", icon: ListChecks, to: TAXWISE_OE_RELIEFS, end: false },
  { label: "My Tax Result", icon: Calculator, to: TAXWISE_OE_RESULT, end: false },
] as const;

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "")).toUpperCase() || "U";
}

function displayFirstName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (/^Taxpayer_\d+$/i.test(parts[0] ?? "")) return parts[0]!;
  return parts[0] ?? name;
}

function FlyoutNavGroup({
  label,
  icon: Icon,
  items,
  groupClass,
}: {
  label: string;
  icon: typeof Sparkles;
  items: ReadonlyArray<{ label: string; icon: typeof Sparkles; to: string; end?: boolean }>;
  groupClass: string;
}) {
  const location = useLocation();
  const isGroupActive = items.some((item) =>
    item.end
      ? location.pathname === item.to
      : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );

  return (
    <div className={cn("relative", groupClass)}>
      <div
        className={cn(
          "flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          isGroupActive
            ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]"
            : "text-[var(--uv-text-muted)] group-hover:bg-white/5 group-hover:text-[var(--uv-text)]",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="min-w-0 leading-snug">{label}</span>
        <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0 opacity-60" />
      </div>

      <div
        className={cn(
          "invisible absolute left-full top-0 z-50 ml-1 min-w-[12.5rem] rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] py-1 pl-1 opacity-0 shadow-xl transition-all",
          "before:absolute before:-left-2 before:top-0 before:h-full before:w-2 before:content-['']",
          "group-hover:visible group-hover:opacity-100",
          isGroupActive && "border-[var(--uv-accent)]/30",
        )}
      >
        {items.map((item) => {
          const ItemIcon = item.icon;
          const active = item.end
            ? location.pathname === item.to
            : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]"
                  : "text-[var(--uv-text-muted)] hover:bg-white/5 hover:text-[var(--uv-text)]",
              )}
            >
              <ItemIcon className="h-4 w-4 shrink-0" />
              {item.label}
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

type UserViewShellProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  embedded?: boolean;
};

export function UserViewShell({ children, title, subtitle, embedded }: UserViewShellProps) {
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);

  if (!isAuthenticated || role !== "taxpayer" || !profileId) {
    return <Navigate to="/login" replace />;
  }

  const name = fullName ?? "User";
  const firstName = displayFirstName(name);

  return (
    <div className="user-view flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-[var(--uv-border)] bg-[var(--uv-bg)] p-4 md:flex">
        <div className="mb-8 flex items-center gap-2.5 px-2">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[var(--uv-accent)]">
            <Zap className="h-4 w-4 text-[var(--uv-accent-foreground)]" />
          </span>
          <span className="text-sm font-bold tracking-tight">TaxWise AI</span>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.slice(0, 2).map((item) => {
            const Icon = item.icon;
            if (!item.enabled) {
              return (
                <button
                  key={item.key}
                  type="button"
                  disabled
                  title="Coming soon"
                  className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-[var(--uv-text-muted)] opacity-60"
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </button>
              );
            }
            return (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.to === TAXWISE_BASE}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]"
                      : "text-[var(--uv-text-muted)] hover:bg-white/5 hover:text-[var(--uv-text)]",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </NavLink>
            );
          })}

          <FlyoutNavGroup
            label="Optimization and Explainable"
            icon={TrendingUp}
            items={OE_SUB_ITEMS}
            groupClass="group/oe group"
          />

          {NAV_ITEMS.slice(2, 3).map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                disabled
                title="Coming soon"
                className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-[var(--uv-text-muted)] opacity-60"
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </button>
            );
          })}

          <FlyoutNavGroup
            label="Recommendations"
            icon={Sparkles}
            items={RECOMMENDATION_SUB_ITEMS}
            groupClass="group/recommendations group"
          />

          {NAV_ITEMS.slice(3).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.key}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]"
                      : "text-[var(--uv-text-muted)] hover:bg-white/5 hover:text-[var(--uv-text)]",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3">
          <NavLink to={TAXWISE_PROFILE} className="flex items-center gap-3 rounded-lg hover:bg-white/5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--uv-accent)]/20 text-xs font-semibold text-[var(--uv-accent)]">
              {initials(name)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{name}</p>
              <p className="truncate text-xs text-[var(--uv-text-muted)]">View profile</p>
            </div>
          </NavLink>
          <button
            type="button"
            onClick={logout}
            className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-[var(--uv-text-muted)] transition-colors hover:bg-white/5 hover:text-[var(--uv-text)]"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {!embedded && (
          <header className="flex items-center justify-between border-b border-[var(--uv-border)] px-4 py-4 md:px-8">
            <div>
              <h1 className="text-xl font-bold tracking-tight md:text-2xl">
                {title ?? `Welcome back, ${firstName}`}
              </h1>
              {subtitle && <p className="mt-0.5 text-sm text-[var(--uv-text-muted)]">{subtitle}</p>}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled
                title="Notifications coming soon"
                className="rounded-lg p-2 text-[var(--uv-text-muted)] opacity-50"
              >
                <Bell className="h-5 w-5" />
              </button>
              <NavLink
                to={TAXWISE_PROFILE}
                title="Open profile"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--uv-accent)]/20 text-sm font-semibold text-[var(--uv-accent)] hover:bg-[var(--uv-accent)]/30"
              >
                {initials(name)}
              </NavLink>
            </div>
          </header>
        )}

        <main
          className={
            embedded
              ? "flex flex-1 flex-col overflow-hidden p-0"
              : "flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8"
          }
        >
          {children}
        </main>
      </div>
    </div>
  );
}
