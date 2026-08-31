import { cn } from "@/lib/utils";

type ChipProps = {
  className?: string;
  children: React.ReactNode;
  hint?: string;
  userView?: boolean;
};

function Chip({ className, children, hint, userView }: ChipProps) {
  return (
    <span
      tabIndex={hint ? 0 : undefined}
      className={cn(
        "group relative inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium outline-none",
        hint && "cursor-help focus-visible:ring-2 focus-visible:ring-[var(--uv-accent)]/50",
        className,
      )}
    >
      {children}
      {hint && (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-none absolute left-1/2 top-full z-10 mt-2 w-56 -translate-x-1/2 rounded-md border p-3 text-sm font-normal leading-snug opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100",
            userView
              ? "border-[var(--uv-border)] bg-[var(--uv-bg-elevated)] text-[var(--uv-text)]"
              : "border-border bg-popover text-popover-foreground",
          )}
        >
          {hint}
        </span>
      )}
    </span>
  );
}

export function RiskChip({ score, userView }: { score: number; userView?: boolean }) {
  const level = score >= 0.15 ? "high" : score >= 0.08 ? "medium" : "low";
  const styles = userView
    ? {
        low: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
        medium: "border-amber-500/40 bg-amber-500/15 text-amber-200",
        high: "border-rose-500/40 bg-rose-500/15 text-rose-300",
      }
    : {
        low: "border-emerald-300 bg-emerald-50 text-emerald-800",
        medium: "border-amber-300 bg-amber-50 text-amber-900",
        high: "border-rose-300 bg-rose-50 text-rose-800",
      };
  const hints = {
    low: "This is straightforward and unlikely to cause problems — low chance of surprises.",
    medium: "This could need some attention or double-checking — a moderate chance of surprises.",
    high: "This is more complex or uncertain — a higher chance something doesn't go as planned.",
  };
  return (
    <Chip className={styles[level]} hint={hints[level]} userView={userView}>
      Risk: {level}
    </Chip>
  );
}

export function ConfidenceChip({ value, userView }: { value: number; userView?: boolean }) {
  const pct = (value * 100).toFixed(0);
  const level = value >= 0.75 ? "high" : value >= 0.5 ? "medium" : "low";
  const styles = userView
    ? {
        high: "border-[var(--uv-accent)]/40 bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]",
        medium: "border-[var(--uv-border)] bg-white/5 text-[var(--uv-text-muted)]",
        low: "border-[var(--uv-border)] bg-white/5 text-[var(--uv-text-muted)]",
      }
    : {
        high: "border-primary/40 bg-primary/10 text-primary",
        medium: "border-border bg-muted text-foreground",
        low: "border-border bg-muted/50 text-muted-foreground",
      };
  return (
    <Chip
      className={styles[level]}
      hint="How sure the system is about this recommendation, based on your data."
      userView={userView}
    >
      Confidence {pct}% · {level}
    </Chip>
  );
}

export function AdoptionChip({ probability, userView }: { probability: number; userView?: boolean }) {
  const pct = (probability * 100).toFixed(probability < 0.01 && probability > 0 ? 1 : 0);
  const level = probability >= 0.7 ? "Great fit" : probability >= 0.4 ? "Good fit" : "Worth a look";
  return (
    <Chip
      className={
        userView
          ? "border-sky-500/40 bg-sky-500/15 text-sky-200"
          : "border-sky-300 bg-sky-50 text-sky-900"
      }
      hint={`${pct}% of people in a similar situation to you go ahead with this option.`}
      userView={userView}
    >
      {level} · {pct}%
    </Chip>
  );
}

export function SavingsChip({
  label,
  value,
  userView,
}: {
  label?: string;
  value: string;
  userView?: boolean;
}) {
  return (
    <Chip
      className={
        userView
          ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
          : "border-emerald-400/50 bg-emerald-50 text-emerald-900"
      }
      hint="How much this could save you on tax over a year, compared to doing nothing."
      userView={userView}
    >
      {label ?? "You could save"} {value}
    </Chip>
  );
}
