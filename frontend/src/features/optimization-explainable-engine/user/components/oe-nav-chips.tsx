import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";
import {
  TAXWISE_OE,
  TAXWISE_OE_EXPLANATIONS,
  TAXWISE_OE_INCOME,
  TAXWISE_OE_RELIEFS,
  TAXWISE_OE_RESULT,
} from "../paths";

const TABS = [
  { label: "Overview", to: TAXWISE_OE, end: true },
  { label: "My Income", to: TAXWISE_OE_INCOME, end: false },
  { label: "My Reliefs", to: TAXWISE_OE_RELIEFS, end: false },
  { label: "My Tax Result", to: TAXWISE_OE_RESULT, end: false },
  { label: "Explanations", to: TAXWISE_OE_EXPLANATIONS, end: false },
] as const;

export function OeNavChips() {
  return (
    <nav
      className="flex flex-wrap gap-2"
      aria-label="Optimization and Explainable sections"
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]"
                : "border border-[var(--uv-border)] bg-[var(--uv-bg-card)] text-[var(--uv-text-muted)] hover:bg-white/5 hover:text-[var(--uv-text)]",
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
