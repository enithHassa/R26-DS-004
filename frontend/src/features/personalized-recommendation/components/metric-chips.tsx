import { cn } from "@/lib/utils";

type ChipProps = { className?: string; children: React.ReactNode; hint?: string };

function Chip({ className, children, hint }: ChipProps) {
  return (
    <span
      tabIndex={hint ? 0 : undefined}
      className={cn(
        "group relative inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium outline-none",
        hint && "cursor-help focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      {children}
      {hint && (
        <span
          role="tooltip"
          className="pointer-events-none absolute left-1/2 top-full z-10 mt-2 w-56 -translate-x-1/2 rounded-md border border-border bg-popover p-3 text-sm font-normal leading-snug text-popover-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
        >
          {hint}
        </span>
      )}
    </span>
  );
}

export function RiskChip({ score }: { score: number }) {
  const level = score >= 0.15 ? "high" : score >= 0.08 ? "medium" : "low";
  const styles = {
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
    <Chip className={styles[level]} hint={hints[level]}>
      Risk: {level}
    </Chip>
  );
}

export function ConfidenceChip({ value }: { value: number }) {
  const pct = (value * 100).toFixed(0);
  const level = value >= 0.75 ? "high" : value >= 0.5 ? "medium" : "low";
  const styles = {
    high: "border-primary/40 bg-primary/10 text-primary",
    medium: "border-border bg-muted text-foreground",
    low: "border-border bg-muted/50 text-muted-foreground",
  };
  return (
    <Chip
      className={styles[level]}
      hint="How sure the system is about this recommendation, based on your data."
    >
      Confidence {pct}% · {level}
    </Chip>
  );
}

export function AdoptionChip({ probability }: { probability: number }) {
  const pct = (probability * 100).toFixed(0);
  const level = probability >= 0.7 ? "Great fit" : probability >= 0.4 ? "Good fit" : "Worth a look";
  return (
    <Chip
      className="border-sky-300 bg-sky-50 text-sky-900"
      hint={`${pct}% of people in a similar situation to you go ahead with this option.`}
    >
      {level} · {pct}%
    </Chip>
  );
}

export function SavingsChip({ label, value }: { label?: string; value: string }) {
  return (
    <Chip
      className="border-emerald-400/50 bg-emerald-50 text-emerald-900"
      hint="How much this could save you on tax over a year, compared to doing nothing."
    >
      {label ?? "You could save"} {value}
    </Chip>
  );
}
