/**
 * Phase 4 — Knowledge Graph context panel.
 * Presents graph enrichment in plain language with scannable sections.
 */

import {
  AlertTriangle,
  BookMarked,
  Brain,
  Calendar,
  Coins,
  Network,
  Users,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type {
  ConceptNode,
  GraphContext,
  LexNote,
  ProcedureMilestoneNode,
  RateBandNode,
  ReliefNode,
  TaxpayerProfileNode,
} from "../types";
import { GraphLinkMap } from "./graph-link-map";
import type { GraphSourceAnchor } from "./graph-source-anchor";
import { humanizeSlug } from "./language-model-display";

const MONTHS = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function fmtLkr(n: number | null | undefined): string {
  if (n == null) return "—";
  return "Rs. " + n.toLocaleString("en-LK");
}

function SectionTitle({
  icon: Icon,
  title,
  description,
  count,
}: {
  icon: React.ElementType;
  title: string;
  description?: string;
  count: number;
}) {
  return (
    <div className="mb-4 space-y-1">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {count}
        </span>
      </div>
      {description ? (
        <p className="text-sm text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}

function AliasChips({ aliases }: { aliases: string[] }) {
  if (aliases.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Also known as
      </p>
      <div className="flex flex-wrap gap-2">
        {aliases.map((alias) => (
          <span
            key={alias}
            className="rounded-full border border-border/70 bg-background px-2.5 py-1 text-xs text-foreground/90"
          >
            {alias}
          </span>
        ))}
      </div>
    </div>
  );
}

function conceptTheme(concept: ConceptNode): "income" | "residency" | "general" {
  const haystack = `${concept.concept_id} ${concept.canonical_name ?? ""} ${concept.aliases?.join(" ") ?? ""}`.toLowerCase();
  if (/(resident|non-resident|nonresident|domicile)/.test(haystack)) return "residency";
  if (/(income|employment|business|investment|salary|wage|dividend|rent)/.test(haystack)) {
    return "income";
  }
  return "general";
}

const themeStyles = {
  income: "border-sky-200/80 bg-sky-50/70 dark:border-sky-900/60 dark:bg-sky-950/20",
  residency: "border-violet-200/80 bg-violet-50/70 dark:border-violet-900/60 dark:bg-violet-950/20",
  general: "border-border/80 bg-muted/20",
} as const;

const themeLabels = {
  income: "Income category",
  residency: "Residency status",
  general: "Tax concept",
} as const;

function ConceptsSection({ items }: { items: ConceptNode[] }) {
  return (
    <div>
      <SectionTitle
        icon={Brain}
        title="Key tax concepts"
        description="Definitions linked to the sources we retrieved for your question."
        count={items.length}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {items.map((concept) => {
          const theme = conceptTheme(concept);
          return (
            <div
              key={concept.concept_id}
              className={cn("rounded-xl border p-4 shadow-sm", themeStyles[theme])}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {themeLabels[theme]}
                  </p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {concept.canonical_name ?? humanizeSlug(concept.concept_id)}
                  </p>
                </div>
              </div>
              {concept.notes ? (
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{concept.notes}</p>
              ) : null}
              <AliasChips aliases={concept.aliases ?? []} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ReliefsSection({ items }: { items: ReliefNode[] }) {
  return (
    <div>
      <SectionTitle
        icon={Coins}
        title="Reliefs and deductions"
        description="Allowances or deductions that may reduce taxable income."
        count={items.length}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {items.map((relief) => (
          <div key={relief.relief_id} className="rounded-xl border border-border/80 bg-card p-4 shadow-sm">
            <p className="text-base font-semibold text-foreground">
              {relief.display_name ?? humanizeSlug(relief.relief_id)}
            </p>
            {relief.statutory_label ? (
              <p className="mt-1 text-sm text-muted-foreground">{relief.statutory_label}</p>
            ) : null}
            {relief.description ? (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{relief.description}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function RateBandsSection({ items }: { items: RateBandNode[] }) {
  const maxRate = Math.max(...items.map((band) => band.rate_percent ?? 0), 1);

  return (
    <div>
      <SectionTitle
        icon={BookMarked}
        title="Tax rate bands"
        description="How income is taxed across slabs or ceilings for the matched concepts."
        count={items.length}
      />
      <div className="space-y-3">
        {items.map((band) => {
          const width = band.rate_percent != null ? Math.max((band.rate_percent / maxRate) * 100, 8) : 8;
          return (
            <div
              key={band.rate_band_id}
              className="rounded-xl border border-border/80 bg-card p-4 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-foreground">
                    {band.band_label ?? humanizeSlug(band.rate_band_id)}
                  </p>
                  {band.band_type ? (
                    <p className="mt-1 text-sm capitalize text-muted-foreground">
                      {humanizeSlug(band.band_type)}
                    </p>
                  ) : null}
                </div>
                <p className="text-lg font-semibold text-primary">
                  {band.rate_percent != null ? `${band.rate_percent}%` : "—"}
                </p>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary/80" style={{ width: `${width}%` }} />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                {fmtLkr(band.lower_bound)} to{" "}
                {band.upper_bound != null ? fmtLkr(band.upper_bound) : "and above"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MilestonesSection({ items }: { items: ProcedureMilestoneNode[] }) {
  return (
    <div>
      <SectionTitle
        icon={Calendar}
        title="Filing and payment deadlines"
        description="Important dates connected to the retrieved legal material."
        count={items.length}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {items.map((milestone) => (
          <div
            key={milestone.milestone_id}
            className="rounded-xl border border-border/80 bg-card p-4 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <p className="font-semibold text-foreground">
                {milestone.display_name ?? humanizeSlug(milestone.milestone_id)}
              </p>
              {milestone.due_day != null && milestone.due_month != null ? (
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                  Due {milestone.due_day} {MONTHS[milestone.due_month]}
                  {milestone.recurrence ? ` · ${humanizeSlug(milestone.recurrence)}` : ""}
                </span>
              ) : null}
            </div>
            {milestone.description ? (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{milestone.description}</p>
            ) : null}
            {milestone.applies_to && milestone.applies_to.length > 0 ? (
              <p className="mt-3 text-xs text-muted-foreground">
                Applies to: {milestone.applies_to.map(humanizeSlug).join(", ")}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function ProfilesSection({ items }: { items: TaxpayerProfileNode[] }) {
  return (
    <div>
      <SectionTitle
        icon={Users}
        title="Who this applies to"
        description="Taxpayer profiles connected to the matched reliefs or rules."
        count={items.length}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {items.map((profile) => (
          <div
            key={profile.profile_type}
            className="rounded-xl border border-border/80 bg-card p-4 shadow-sm"
          >
            <p className="font-semibold text-foreground">
              {profile.display_name ?? humanizeSlug(profile.profile_type)}
            </p>
            {profile.description ? (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{profile.description}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function SupersededSection({ items }: { items: string[] }) {
  return (
    <div>
      <SectionTitle
        icon={AlertTriangle}
        title="Newer law versions"
        description="Matched instruments that have been replaced by a newer source in the graph."
        count={items.length}
      />
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-xl border border-border/80 bg-card px-4 py-3 text-sm text-foreground"
          >
            Prefer the newer instrument instead of{" "}
            <span className="font-medium">{humanizeSlug(item)}</span>.
          </li>
        ))}
      </ul>
    </div>
  );
}

function LexNotesSection({ notes }: { notes: LexNote[] }) {
  return (
    <div>
      <SectionTitle
        icon={AlertTriangle}
        title="Law override notices"
        description="When a newer or stronger legal source may replace an older section."
        count={notes.length}
      />
      <ul className="space-y-3">
        {notes.map((note, index) => (
          <li
            key={`${note.winner_section_uid}-${note.overridden_section_uid}-${index}`}
            className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950/20"
          >
            <p className="font-medium text-amber-900 dark:text-amber-200">
              A newer or stronger section may override an older one.
            </p>
            <p className="mt-2 text-amber-800 dark:text-amber-300">
              Prefer <span className="font-medium">{note.winner_section_uid}</span> over{" "}
              <span className="font-medium">{note.overridden_section_uid}</span>.
            </p>
            {note.authority_class ? (
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
                Authority class: {humanizeSlug(note.authority_class)}
              </p>
            ) : null}
            {note.note ? (
              <p className="mt-2 text-amber-800 dark:text-amber-300">{note.note}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function GraphSummary({ context }: { context: GraphContext }) {
  const items = [
    { label: "Concepts", count: context.concepts.length },
    { label: "Reliefs", count: context.reliefs.length },
    { label: "Rate bands", count: context.rate_bands.length },
    { label: "Deadlines", count: context.procedure_milestones.length },
    { label: "Profiles", count: context.taxpayer_profiles.length },
    { label: "Overrides", count: context.lex_notes.length },
    { label: "Superseded", count: context.superseded_by.length },
  ].filter((item) => item.count > 0);

  return (
    <div className="rounded-xl border border-primary/15 bg-primary/5 p-4">
      <p className="text-sm font-medium text-foreground">
        We linked your retrieved sources to related tax knowledge.
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        These are supporting definitions, reliefs, rates, deadlines, and audience notes — not a generated legal answer.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={item.label}
            className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1 text-xs font-medium"
          >
            <span>{item.label}</span>
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
              {item.count}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

interface GraphContextPanelProps {
  context: GraphContext;
  sourceAnchors?: GraphSourceAnchor[];
  intentLabel?: string | null;
}

export function GraphContextPanel({
  context,
  sourceAnchors = [],
  intentLabel,
}: GraphContextPanelProps) {
  const hasAnything =
    context.concepts.length > 0 ||
    context.reliefs.length > 0 ||
    context.rate_bands.length > 0 ||
    context.procedure_milestones.length > 0 ||
    context.taxpayer_profiles.length > 0 ||
    context.lex_notes.length > 0 ||
    context.superseded_by.length > 0;

  return (
    <Card className="overflow-hidden rounded-xl border border-border/80 shadow-sm">
      <div className="h-1 w-full bg-gradient-to-r from-primary/70 via-sky-500/60 to-violet-500/60" aria-hidden />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Network className="h-5 w-5 text-primary" />
          Related tax knowledge
        </CardTitle>
        <CardDescription>
          Linked context from the Sri Lanka tax knowledge graph, mapped from your matched passages
          through Neo4j relationships such as mentions, covered reliefs, rate bands, and deadlines.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!hasAnything ? (
          <p className="text-sm text-muted-foreground">
            No related graph context was found for this query yet.
          </p>
        ) : (
          <div className="space-y-8">
            <GraphSummary context={context} />
            <GraphLinkMap
              anchors={sourceAnchors}
              context={context}
              intentLabel={intentLabel}
            />
            {context.concepts.length > 0 ? <ConceptsSection items={context.concepts} /> : null}
            {context.reliefs.length > 0 ? <ReliefsSection items={context.reliefs} /> : null}
            {context.rate_bands.length > 0 ? <RateBandsSection items={context.rate_bands} /> : null}
            {context.procedure_milestones.length > 0 ? (
              <MilestonesSection items={context.procedure_milestones} />
            ) : null}
            {context.taxpayer_profiles.length > 0 ? (
              <ProfilesSection items={context.taxpayer_profiles} />
            ) : null}
            {context.lex_notes.length > 0 ? <LexNotesSection notes={context.lex_notes} /> : null}
            {context.superseded_by.length > 0 ? (
              <SupersededSection items={context.superseded_by} />
            ) : null}
          </div>
        )}
        <p className="mt-6 text-right text-[11px] text-muted-foreground/70">
          Knowledge graph source: {humanizeSlug(context.graph_model)}
        </p>
      </CardContent>
    </Card>
  );
}
