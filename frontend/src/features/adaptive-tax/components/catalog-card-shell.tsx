import type { ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { FilingCatalogCard } from "../api";

type CatalogCardShellProps = {
  card?: FilingCatalogCard | null;
  title: string;
  subtitle: string;
  actVersionLabel?: string | null;
  fieldCount?: number;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function CalculatorGroupHead({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="border-b border-border/60 pb-2">
      <h2 className="text-sm font-semibold tracking-tight text-foreground">{title}</h2>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  );
}

export function CatalogCardShell({
  card,
  title,
  subtitle,
  actVersionLabel,
  fieldCount,
  open,
  onToggle,
  children,
}: CatalogCardShellProps) {
  const displayTitle = card?.display_name ?? title;
  const section = card?.section;

  return (
    <div className="space-y-3 rounded-lg border border-border/80 bg-card/50 p-4 shadow-sm">
      <button
        type="button"
        className="flex w-full items-start justify-between gap-3 text-left"
        onClick={onToggle}
        aria-expanded={open}
      >
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium">{displayTitle}</p>
            {section ? (
              <span className="rounded-md border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                Sec {section}
              </span>
            ) : null}
            {actVersionLabel ? (
              <span className="rounded-md border border-emerald-200/80 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200">
                {actVersionLabel}
              </span>
            ) : null}
            {fieldCount != null && fieldCount > 0 ? (
              <span className="text-[10px] text-muted-foreground">
                {fieldCount} catalog field{fieldCount === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {open ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {open ? children : null}
    </div>
  );
}
