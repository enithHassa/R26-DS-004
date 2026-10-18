import { ArrowRight, Link2 } from "lucide-react";

import { cn } from "@/lib/utils";

import type { GraphContext } from "../types";
import { humanizeSlug } from "./language-model-display";
import type { GraphSourceAnchor } from "./graph-source-anchor";

interface GraphLinkMapProps {
  anchors: GraphSourceAnchor[];
  context: GraphContext;
  intentLabel?: string | null;
}

interface GraphPath {
  id: string;
  from: string;
  relation: string;
  to: string;
  count: number;
}

function buildPaths(context: GraphContext, intentLabel?: string | null): GraphPath[] {
  const paths: GraphPath[] = [
    {
      id: "mentions",
      from: "Matched passages",
      relation: "mention",
      to: "Tax concepts",
      count: context.concepts.length,
    },
    {
      id: "covers-relief",
      from: "Law sections",
      relation: "cover",
      to: "Reliefs and deductions",
      count: context.reliefs.length,
    },
    {
      id: "applies-to",
      from: "Rate bands",
      relation: "apply to",
      to: "Tax concepts",
      count: context.rate_bands.length > 0 && context.concepts.length > 0
        ? Math.min(context.rate_bands.length, context.concepts.length)
        : context.rate_bands.length,
    },
    {
      id: "derived-from",
      from: "Law sections",
      relation: "define",
      to: "Filing deadlines",
      count: context.procedure_milestones.length,
    },
    {
      id: "relevant-relief",
      from: "Taxpayer profiles",
      relation: "relate to",
      to: "Reliefs and deductions",
      count:
        context.taxpayer_profiles.length > 0 && context.reliefs.length > 0
          ? Math.min(context.taxpayer_profiles.length, context.reliefs.length)
          : context.taxpayer_profiles.length,
    },
    {
      id: "overrides",
      from: "Stronger law sections",
      relation: "override",
      to: "Older sections",
      count: context.lex_notes.length,
    },
    {
      id: "supersedes",
      from: "Newer instruments",
      relation: "replace",
      to: "Older instruments",
      count: context.superseded_by.length,
    },
  ];

  if (intentLabel?.trim()) {
    paths.unshift({
      id: "intent",
      from: `Topic: ${humanizeSlug(intentLabel.trim())}`,
      relation: "also loads",
      to: "Graph entities",
      count:
        context.reliefs.length +
        context.rate_bands.length +
        context.taxpayer_profiles.length,
    });
  }

  return paths.filter((path) => path.count > 0);
}

function PathRow({ path }: { path: GraphPath }) {
  return (
    <div className="grid gap-2 rounded-lg border border-border/70 bg-background/80 p-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center">
      <p className="text-sm font-medium text-foreground">{path.from}</p>
      <div className="flex items-center gap-2 text-xs text-muted-foreground sm:justify-center">
        <span className="rounded-full bg-muted px-2 py-0.5 font-medium uppercase tracking-wide">
          {path.relation}
        </span>
        <ArrowRight className="hidden h-3.5 w-3.5 sm:block" aria-hidden />
      </div>
      <div className="flex items-center justify-between gap-3 sm:justify-end">
        <p className="text-sm font-medium text-foreground">{path.to}</p>
        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
          {path.count}
        </span>
      </div>
    </div>
  );
}

export function GraphLinkMap({ anchors, context, intentLabel }: GraphLinkMapProps) {
  const paths = buildPaths(context, intentLabel);

  return (
    <section className="space-y-4 rounded-xl border border-border/80 bg-muted/15 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Link2 className="h-4 w-4 text-primary" aria-hidden />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">How this extra context was linked</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            We take the Match passages from above, look them up in the tax knowledge graph, and pull
            related concepts, reliefs, rates, and deadlines.
          </p>
        </div>
      </div>

      {anchors.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Starting from these Match sources
          </p>
          <div className="grid gap-2 lg:grid-cols-2">
            {anchors.map((anchor) => (
              <div
                key={anchor.chunkId}
                className="rounded-lg border border-border/70 bg-card px-3 py-2.5"
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {anchor.rank}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Match {anchor.rank}
                    </p>
                    <p className="text-sm font-medium text-foreground">{anchor.title}</p>
                    {anchor.subtitle ? (
                      <p className="text-xs text-muted-foreground">{anchor.subtitle}</p>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {paths.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            What we connected
          </p>
          <div className="space-y-2">
            {paths.map((path) => (
              <PathRow key={path.id} path={path} />
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No extra tax-knowledge links were found for these matches.
        </p>
      )}

      <p className={cn("text-xs text-muted-foreground")}>
        Summary of links only — not every relationship in the full tax database.
      </p>
    </section>
  );
}
