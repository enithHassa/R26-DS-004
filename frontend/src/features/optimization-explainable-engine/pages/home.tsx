import { Link } from "react-router-dom";
import {
  ArrowRight,
  Calculator,
  FileText,
  GitCompareArrows,
  Library,
  ListChecks,
  MessageCircle,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    step: "01",
    to: "/optimization-explainable-engine",
    label: "Year & interview",
    description: "Choose the year of assessment and begin the guided flow.",
    icon: MessageCircle,
  },
  {
    step: "02",
    to: "/optimization-explainable-engine/acts",
    label: "Acts",
    description: "Review promoted Act year views that drive reliefs and rates.",
    icon: FileText,
  },
  {
    step: "03",
    to: "/optimization-explainable-engine/income",
    label: "Income",
    description: "Enter assessable income by head, including APIT already paid.",
    icon: Wallet,
  },
  {
    step: "04",
    to: "/optimization-explainable-engine/reliefs",
    label: "Reliefs",
    description: "Claim qualifying reliefs with live applied amounts and caps.",
    icon: ListChecks,
  },
  {
    step: "05",
    to: "/optimization-explainable-engine/result",
    label: "Result",
    description: "See taxable income, slab tax, credits, and plain-English explanation.",
    icon: Calculator,
  },
] as const;

const EXTRA = [
  {
    to: "/optimization-explainable-engine/compare",
    label: "Compare reliefs",
    description: "Side-by-side relief options for the same year.",
    icon: GitCompareArrows,
  },
  {
    to: "/optimization-explainable-engine/load-act",
    label: "Load new act",
    description: "Ingest and promote a new Inland Revenue Act for a year.",
    icon: Library,
  },
] as const;

export function OptimizationExplainableHomePage() {
  return (
    <div className="space-y-10">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/[0.07] via-background to-muted/40 px-6 py-8 sm:px-8 sm:py-10">
        <div
          className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-primary/10 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-24 left-1/3 h-48 w-48 rounded-full bg-primary/5 blur-3xl"
          aria-hidden
        />
        <div className="relative max-w-2xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Year-aware tax interview
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Optimization and Explainable Engine
          </h1>
          <p className="text-base leading-relaxed text-muted-foreground sm:text-[17px]">
            Independent year-aware interview. Years and reliefs load from promoted
            Act year views — then income, claims, and an explainable tax result.
          </p>
          <div className="flex flex-wrap gap-3 pt-1">
            <Button type="button" size="lg" asChild>
              <Link to="/optimization-explainable-engine">
                Start interview
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
            <Button type="button" size="lg" variant="outline" asChild>
              <Link to="/optimization-explainable-engine/income">Jump to income</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Interview path</h2>
          <p className="text-sm text-muted-foreground">
            Follow the steps in order, or open any stage directly.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "group flex flex-col rounded-xl border bg-card p-4 transition-colors",
                "hover:border-primary/40 hover:bg-primary/[0.03]",
              )}
            >
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <item.icon className="h-4 w-4" />
                </span>
                <span className="font-mono text-xs text-muted-foreground">{item.step}</span>
              </div>
              <p className="font-medium group-hover:text-primary">{item.label}</p>
              <p className="mt-1 text-sm leading-snug text-muted-foreground">
                {item.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">More tools</h2>
          <p className="text-sm text-muted-foreground">
            Optional helpers outside the main interview path.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {EXTRA.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "group flex items-start gap-3 rounded-xl border bg-card p-4 transition-colors",
                "hover:border-primary/40 hover:bg-primary/[0.03]",
              )}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
                <item.icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="font-medium group-hover:text-primary">{item.label}</p>
                <p className="mt-0.5 text-sm text-muted-foreground">{item.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
