import { cn } from "@/lib/utils";

type ChipProps = { className?: string; children: React.ReactNode };

function Chip({ className, children }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      {children}
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
  return <Chip className={styles[level]}>Risk: {level}</Chip>;
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
    <Chip className={styles[level]}>
      Confidence {pct}% · {level}
    </Chip>
  );
}

export function AdoptionChip({ probability }: { probability: number }) {
  const pct = (probability * 100).toFixed(0);
  return (
    <Chip className="border-sky-300 bg-sky-50 text-sky-900">
      Adoption {pct}%
    </Chip>
  );
}

export function SavingsChip({ label, value }: { label?: string; value: string }) {
  return (
    <Chip className="border-emerald-400/50 bg-emerald-50 text-emerald-900">
      {label ?? "Est. savings"} {value}
    </Chip>
  );
}
