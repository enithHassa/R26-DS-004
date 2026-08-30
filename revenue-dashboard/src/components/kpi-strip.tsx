import { cn } from "@/lib/utils";

type Kpi = {
  label: string;
  value: string;
  hint?: string;
  accent?: "teal" | "gold" | "slate";
};

const accentBg = {
  teal: "from-[var(--revenue-teal)] to-[#0a5252]",
  gold: "from-[var(--revenue-gold)] to-[#a8861f]",
  slate: "from-slate-700 to-slate-900",
};

export function KpiStrip({ items }: { items: Kpi[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((kpi) => (
        <div
          key={kpi.label}
          className={cn(
            "overflow-hidden rounded-2xl bg-gradient-to-br p-[1px] shadow-md",
            accentBg[kpi.accent ?? "teal"],
          )}
        >
          <div className="rounded-[15px] bg-white/95 px-5 py-4 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--revenue-muted)]">
              {kpi.label}
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[var(--revenue-slate)]">
              {kpi.value}
            </p>
            {kpi.hint ? (
              <p className="mt-1 text-xs text-[var(--revenue-muted)]">{kpi.hint}</p>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
