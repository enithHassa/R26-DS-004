import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  getLegalCoverage,
  getUnsupportedCatalogRules,
  type LegalCoverageResponse,
  type SectionCoverageRow,
} from "../api";

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.min(100, Math.max(0, pct));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-emerald-600 transition-all dark:bg-emerald-500"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

function SectionCoverageCard({ section }: { section: SectionCoverageRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{section.label}</p>
          <p className="text-xs text-muted-foreground">
            {section.n_covered}/{section.n_planned} components covered ·{" "}
            {section.coverage_pct.toFixed(1)}%
            {section.checklist_covered != null
              ? ` · checklist ${section.checklist_covered ? "✓" : "pending"}`
              : null}
          </p>
        </div>
        {section.components.length > 0 ? (
          <Button type="button" variant="ghost" size="sm" onClick={() => setOpen((v) => !v)}>
            {open ? "Hide" : "Details"}
          </Button>
        ) : null}
      </div>
      <ProgressBar pct={section.coverage_pct} />
      {open ? (
        <ul className="mt-2 space-y-1 text-xs">
          {section.components.map((c) => (
            <li
              key={c.component_id}
              className={
                c.covered
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-muted-foreground"
              }
            >
              {c.covered ? "✓" : "○"} {c.display_name}{" "}
              <span className="opacity-70">({c.component_id})</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function exportCoverageJson(data: LegalCoverageResponse) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `adaptive-tax-legal-coverage-${data.catalog_version}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function AdaptiveTaxCoveragePage() {
  const coverageQuery = useQuery({
    queryKey: ["adaptive-tax", "legal-coverage"],
    queryFn: () => getLegalCoverage(false),
    retry: false,
  });

  const unsupportedQuery = useQuery({
    queryKey: ["adaptive-tax", "unsupported-queue"],
    queryFn: getUnsupportedCatalogRules,
    retry: false,
  });

  const data = coverageQuery.data;
  const error =
    coverageQuery.error instanceof Error ? coverageQuery.error.message : null;

  const overallPct = useMemo(
    () => data?.area_summary.coverage_pct ?? 0,
    [data],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Legal coverage</h1>
          <p className="text-muted-foreground">
            Phase 6.8 — checklist areas + catalog section grain for viva / Chapter 4.
            Formula: approved ∧ engine-wired ∧ provenance-complete / planned components.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {data ? (
            <Button type="button" variant="secondary" onClick={() => exportCoverageJson(data)}>
              <Download className="h-4 w-4" />
              Export JSON
            </Button>
          ) : null}
          <Button type="button" variant="outline" asChild>
            <Link to="/adaptive-tax/home">
              <ArrowLeft className="h-4 w-4" />
              Home
            </Link>
          </Button>
        </div>
      </div>

      {coverageQuery.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading coverage…
        </div>
      ) : null}

      {error ? (
        <Card>
          <CardContent className="py-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {data ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Phase 5 checklist rollup</CardTitle>
              <CardDescription>
                {data.act_version_label} · catalog {data.catalog_version}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-3xl font-semibold">{overallPct.toFixed(1)}%</p>
                <p className="text-sm text-muted-foreground">
                  {data.area_summary.n_covered}/{data.area_summary.n_planned} core areas
                  covered
                </p>
              </div>
              <ProgressBar pct={overallPct} />
              <div className="flex flex-wrap gap-1.5">
                {data.area_summary.areas.map((a) => (
                  <span
                    key={a.area_id}
                    className={
                      a.covered
                        ? "rounded-md border border-emerald-500/40 bg-emerald-50 px-2 py-0.5 text-xs dark:bg-emerald-950/30"
                        : "rounded-md border bg-muted/60 px-2 py-0.5 text-xs"
                    }
                  >
                    {a.area_id}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Section-grain coverage</CardTitle>
              <CardDescription>{data.definition}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              {data.sections.map((section) => (
                <SectionCoverageCard key={section.section_key} section={section} />
              ))}
            </CardContent>
          </Card>
        </>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Unsupported rule queue</CardTitle>
          <CardDescription>
            Harvest / catalog rows awaiting Rule Engine handlers. Approve only after
            handler + provenance + catalog executable.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {unsupportedQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading queue…</p>
          ) : unsupportedQuery.data?.count === 0 ? (
            <p className="text-sm text-muted-foreground">No pending unsupported rules.</p>
          ) : (
            <ul className="space-y-3">
              {unsupportedQuery.data?.items.map((item) => (
                <li key={item.component_id} className="rounded-md border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{item.display_name}</span>
                    {item.section ? (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        Section {item.section}
                        {item.paragraph ? `(${item.paragraph})` : ""}
                      </span>
                    ) : null}
                    <span className="rounded border border-amber-500/50 bg-amber-50 px-1.5 py-0.5 text-xs text-amber-950 dark:bg-amber-950/40 dark:text-amber-50">
                      {item.action_required}
                    </span>
                    <span className="text-xs text-muted-foreground">Status: Pending</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.approve_blocked_reason}
                  </p>
                  {item.source_quote ? (
                    <blockquote className="mt-2 border-l-2 pl-3 text-xs italic text-foreground/80">
                      {item.source_quote.slice(0, 240)}
                      {item.source_quote.length > 240 ? "…" : ""}
                    </blockquote>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
