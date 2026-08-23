import { ArrowRight } from "lucide-react";

export function DemoHero() {
  return (
    <section className="px-6 pb-16 pt-20 text-center">
      <div className="mx-auto max-w-3xl">
        <p className="mb-8 inline-flex rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-sm text-[var(--demo-accent)]">
          Now available for Sri Lankan taxpayers
        </p>

        <h1 className="mb-6 text-4xl font-bold leading-tight tracking-tight text-[var(--demo-text)] sm:text-5xl md:text-[3.25rem]">
          Smart Tax Compliance,
          <br />
          Powered by AI
        </h1>

        <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-[var(--demo-text-muted)]">
          Analyze transactions, optimize tax strategy, and get legally grounded advice — tailored
          to Sri Lankan tax law.
        </p>

        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a
            href="#get-started"
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--demo-accent)] px-6 py-3 text-sm font-semibold text-[var(--demo-accent-foreground)] transition-colors hover:bg-[var(--demo-accent-hover)]"
          >
            Start Free Trial
            <ArrowRight className="h-4 w-4" />
          </a>
          <button
            type="button"
            className="rounded-lg border border-[var(--demo-border)] px-6 py-3 text-sm font-medium text-[var(--demo-text)] transition-colors hover:border-slate-500"
          >
            Watch Demo
          </button>
        </div>
      </div>
    </section>
  );
}
