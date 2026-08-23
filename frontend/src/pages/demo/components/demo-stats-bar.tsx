const STATS = [
  { value: "10,000+", label: "Taxpayers" },
  { value: "LKR 850M+", label: "Tax Optimized" },
  { value: "94%", label: "Avg Compliance Score" },
  { value: "IRD Certified", label: "Legal Sources" },
] as const;

export function DemoStatsBar() {
  return (
    <section className="border-y border-[var(--demo-border)] bg-[var(--demo-bg-elevated)]/50 px-6 py-12">
      <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 md:grid-cols-4">
        {STATS.map((stat) => (
          <div key={stat.label} className="text-center">
            <p className="text-2xl font-bold text-[var(--demo-accent)] sm:text-3xl">{stat.value}</p>
            <p className="mt-1 text-sm text-[var(--demo-text-muted)]">{stat.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
