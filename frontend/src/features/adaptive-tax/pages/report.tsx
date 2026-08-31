import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, ChevronRight, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  explainByCalcId,
  getCalculation,
  getReasoningGraph,
  type CalculationTraceStep,
  type EvidenceSourceQuote,
  type ExplainTaxResponse,
  type ReasoningGraphResponse,
  type StoredCalculation,
} from "../api";
import { formatLkr } from "../format-lkr";
import { buildReportNarrative } from "../build-report-narrative";
import { CalculatedUsingStrip } from "../components/calculated-using-strip";
import { UnresolvedClaimsBanner } from "../components/unresolved-claims-banner";
import {
  ComponentTraceByCard,
  HeadSubtotalsPanel,
} from "../components/head-subtotals-panel";
import { LegalReasoningGraphPanel } from "../components/legal-reasoning-graph";
import { ReportNarrative } from "../components/report-narrative";

function Chip({
  children,
  highlight = false,
}: {
  children: string;
  highlight?: boolean;
}) {
  return (
    <span
      className={
        highlight
          ? "inline-flex max-w-full truncate rounded-md border border-amber-500/50 bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-950 dark:bg-amber-950/40 dark:text-amber-50"
          : "inline-flex max-w-full truncate rounded-md border bg-muted/60 px-1.5 py-0.5 text-[11px] text-foreground"
      }
    >
      {children}
    </span>
  );
}

function isMoneyOutput(value: string): boolean {
  return /^-?\d+(\.\d+)?$/.test(value);
}

function TraceStepAccordion({
  step,
  defaultOpen = false,
}: {
  step: CalculationTraceStep;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b last:border-0">
      <button
        type="button"
        className="flex w-full items-start gap-2 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium">{step.step_id}</span>
            <span className="whitespace-nowrap text-sm font-medium">
              {isMoneyOutput(step.output) ? formatLkr(step.output) : step.output}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{step.description}</p>
        </div>
      </button>
      {open ? (
        <div className="space-y-3 pb-3 pl-6 text-sm">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Formula</p>
            <code className="mt-1 block whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">
              {step.formula}
            </code>
          </div>
          {Object.keys(step.inputs).length > 0 ? (
            <div>
              <p className="text-xs font-medium text-muted-foreground">Inputs</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(step.inputs).map(([key, val]) => (
                  <Chip key={key}>{`${key}=${isMoneyOutput(val) ? formatLkr(val) : val}`}</Chip>
                ))}
              </div>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-1.5">
            {step.concept_ids.map((id) => (
              <Chip key={`c-${step.step_id}-${id}`}>{id}</Chip>
            ))}
            {step.section_uids.map((uid) => (
              <Chip key={`s-${step.step_id}-${uid}`}>
                {uid.split("::").slice(-1)[0] || uid}
              </Chip>
            ))}
            {step.rule_source_ids.map((id) => (
              <Chip key={`r-${step.step_id}-${id}`}>{id}</Chip>
            ))}
            {step.provenance ? (
              <Chip highlight={step.provenance !== "approved"}>
                {`provenance=${step.provenance}`}
              </Chip>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function highlightedQuoteIds(explanation: ExplainTaxResponse | undefined): Set<string> {
  const ids = new Set<string>();
  if (!explanation) return ids;
  for (const step of explanation.steps_explained) {
    if (step.rule_source_id) ids.add(step.rule_source_id);
  }
  return ids;
}

function QuoteRow({
  quote,
  highlight,
}: {
  quote: EvidenceSourceQuote;
  highlight: boolean;
}) {
  return (
    <div
      className={
        highlight
          ? "space-y-2 rounded-md border border-amber-500/40 bg-amber-50/60 p-3 dark:bg-amber-950/20"
          : "space-y-2 rounded-md border p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip highlight={highlight}>{`section ${quote.section}`}</Chip>
        {quote.amends_section ? <Chip>{`amends ${quote.amends_section}`}</Chip> : null}
        {quote.concept_id ? <Chip>{quote.concept_id}</Chip> : null}
        {quote.maximum != null ? <Chip>{`max ${formatLkr(String(quote.maximum))}`}</Chip> : null}
        {highlight ? <Chip highlight>cited in narrative</Chip> : null}
      </div>
      <p className="text-xs text-muted-foreground">
        <code>{quote.rule_source_id}</code> · {quote.status}
      </p>
      <blockquote className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic text-foreground/90">
        {quote.source_quote}
      </blockquote>
    </div>
  );
}

function ReportBody({
  stored,
  explanation,
  reasoningGraph,
  reasoningLoading = false,
  explainLoading = false,
  explainError = null,
  onRetryExplain,
}: {
  stored: StoredCalculation;
  explanation: ExplainTaxResponse | undefined;
  reasoningGraph?: ReasoningGraphResponse;
  reasoningLoading?: boolean;
  explainLoading?: boolean;
  explainError?: string | null;
  onRetryExplain?: () => void;
}) {
  const result = stored.response;
  const evidence = explanation?.evidence;
  const highlightIds = useMemo(
    () => highlightedQuoteIds(explanation),
    [explanation],
  );
  const amendmentContext = stored.amendment_context;

  return (
    <div className="space-y-6">
      <CalculatedUsingStrip versions={result.knowledge_versions} sticky />
      <UnresolvedClaimsBanner claims={result.unresolved_claims ?? []} />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tax result</CardTitle>
          <CardDescription>
            Deterministic rule-engine result for calc{" "}
            <code className="text-xs">{stored.calc_id}</code>
            {stored.param_set_effective
              ? ` · param set ${stored.param_set_effective}`
              : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Gross liability</p>
            <p className="text-4xl font-semibold tracking-tight">
              {formatLkr(result.final_tax_lkr)}
            </p>
          </div>
          {result.tax_payable_lkr ? (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">
                Tax payable after credits
              </p>
              <p className="text-2xl font-semibold tracking-tight">
                {formatLkr(result.tax_payable_lkr)}
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {explainLoading && !explanation ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading legal evidence and narrative (first Chroma load can take a minute)…
        </div>
      ) : explainError && !explanation ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-destructive">
              <FileText className="h-4 w-4" />
              Explanation unavailable
            </CardTitle>
            <CardDescription>{explainError}</CardDescription>
          </CardHeader>
          <CardContent>
            {onRetryExplain ? (
              <Button type="button" variant="secondary" onClick={onRetryExplain}>
                Retry explanation
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <ReportNarrative view={buildReportNarrative(stored, explanation)} />
      )}

      <details className="rounded-xl border bg-card text-card-foreground shadow">
        <summary className="cursor-pointer px-6 py-4 text-sm font-medium">
          Full technical audit
        </summary>
        <div className="space-y-6 border-t px-6 pb-6 pt-4">
          <LegalReasoningGraphPanel graph={reasoningGraph} loading={reasoningLoading} />

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Tax result</CardTitle>
              <CardDescription>
                Head subtotals, component trace, and rules applied.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <HeadSubtotalsPanel subtotals={result.head_subtotals} />
              <ComponentTraceByCard trace={result.component_trace} cards={[]} />
              <div className="flex flex-wrap gap-1.5">
                {result.rules_applied.map((rule) => (
                  <Chip key={rule}>{rule}</Chip>
                ))}
                {result.provenance_complete != null ? (
                  <Chip highlight={!result.provenance_complete}>
                    {result.provenance_complete
                      ? "provenance_complete=true"
                      : "provenance_complete=false"}
                  </Chip>
                ) : null}
              </div>
            </CardContent>
          </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Provenance</CardTitle>
          <CardDescription>
            Every executable step must resolve to an approved official Act section +
            verbatim source quote (Phase 5.0b).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(result.rule_source_refs?.filter((r) => r.source_quote).length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              No Act-backed quotes attached to this calculation (legacy seed or missing
              bootstrap).
            </p>
          ) : (
            result.rule_source_refs
              .filter((r) => r.source_quote)
              .map((ref) => (
                <div key={`prov-${ref.id}`} className="space-y-2 rounded-md border p-3">
                  <div className="flex flex-wrap gap-1.5">
                    <Chip highlight>{ref.id}</Chip>
                    {ref.section ? <Chip>{`Section ${ref.section}`}</Chip> : null}
                    {ref.source_doc_id ? <Chip>{ref.source_doc_id}</Chip> : null}
                    {ref.status ? <Chip>{ref.status}</Chip> : null}
                    {ref.concept_id ? <Chip>{ref.concept_id}</Chip> : null}
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-foreground/90">
                    {ref.source_quote}
                  </p>
                </div>
              ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Calculation trace</CardTitle>
          <CardDescription>
            Expand a step for formula, inputs, and section anchors.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {result.calculation_trace.map((step, index) => (
            <TraceStepAccordion
              key={step.step_id}
              step={step}
              defaultOpen={index === 0}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Legal evidence</CardTitle>
          <CardDescription>
            RAG chunks retrieved for cited sections (
            {explanation?.sections_retrieved.join(", ") || "none"}).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!explanation && !explainLoading ? (
            <p className="text-sm text-muted-foreground">
              Evidence loads with the explanation request.
            </p>
          ) : (evidence?.chunks.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              No Chroma chunks retrieved for this calculation.
            </p>
          ) : (
            evidence?.chunks.map((chunk) => (
              <div key={chunk.chunk_id} className="space-y-2 rounded-md border p-3">
                <div className="flex flex-wrap gap-1.5">
                  <Chip>{chunk.chunk_id}</Chip>
                  {chunk.section_ref ? <Chip>{chunk.section_ref}</Chip> : null}
                  {chunk.source_doc_id ? <Chip>{chunk.source_doc_id}</Chip> : null}
                  {chunk.page != null ? <Chip>{`p.${chunk.page}`}</Chip> : null}
                  {chunk.score != null ? (
                    <Chip>{`score ${chunk.score.toFixed(2)}`}</Chip>
                  ) : null}
                </div>
                <p className="whitespace-pre-wrap text-sm text-foreground/90">
                  {chunk.text}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Rule sources</CardTitle>
          <CardDescription>
            Approved Postgres <code className="text-xs">source_quote</code> rows.
            Rows cited in the narrative are highlighted.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(evidence?.source_quotes.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              No approved rule_source quotes matched cited sections.
              {amendmentContext
                ? " Amendment context is present on this calc store record."
                : null}
            </p>
          ) : (
            evidence?.source_quotes.map((quote) => (
              <QuoteRow
                key={quote.rule_source_id}
                quote={quote}
                highlight={highlightIds.has(quote.rule_source_id)}
              />
            ))
          )}
          {amendmentContext ? (
            <p className="text-xs text-muted-foreground">
              Amendment context:{" "}
              <code className="break-all">{JSON.stringify(amendmentContext)}</code>
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Graph delta (MODIFIES)</CardTitle>
          <CardDescription>
            Neo4j amendment edges for sections in this calculation (empty if Neo4j is
            down).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {(evidence?.graph_modifies.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              No MODIFIES edges returned for cited sections.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {evidence?.graph_modifies.map((edge) => (
                <li
                  key={`${edge.amendment_source_doc_id}-${edge.section_uid}`}
                  className="rounded-md border p-3"
                >
                  <div className="flex flex-wrap gap-1.5">
                    <Chip>{edge.amendment_source_doc_id}</Chip>
                    <Chip>MODIFIES</Chip>
                    <Chip>
                      {edge.section_label ||
                        edge.section_uid.split("::").slice(-1)[0] ||
                        edge.section_uid}
                    </Chip>
                  </div>
                  {edge.source_note ? (
                    <p className="mt-2 text-muted-foreground">{edge.source_note}</p>
                  ) : null}
                  {edge.effective_from ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Effective from {edge.effective_from}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
        </div>
      </details>
    </div>
  );
}

export function AdaptiveTaxReportPage() {
  const { calcId = "" } = useParams<{ calcId: string }>();

  const storedQuery = useQuery({
    queryKey: ["adaptive-tax", "calculation", calcId],
    queryFn: () => getCalculation(calcId),
    enabled: Boolean(calcId),
    retry: false,
  });

  const explainQuery = useQuery({
    queryKey: ["adaptive-tax", "explain", calcId],
    queryFn: () => explainByCalcId(calcId),
    enabled: Boolean(calcId) && storedQuery.isSuccess,
    retry: false,
  });

  const reasoningQuery = useQuery({
    queryKey: ["adaptive-tax", "reasoning-graph", calcId],
    queryFn: () => getReasoningGraph(calcId),
    enabled: Boolean(calcId) && storedQuery.isSuccess,
    retry: false,
  });

  const calcError =
    storedQuery.error instanceof Error ? storedQuery.error.message : null;
  const explainError =
    explainQuery.error instanceof Error ? explainQuery.error.message : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tax report</h1>
          <p className="text-muted-foreground">
            Phase 4 — final tax, expandable trace, legal evidence, and grounded
            narrative for{" "}
            <code className="rounded bg-muted px-1 text-xs">{calcId || "…"}</code>
          </p>
        </div>
        <Button type="button" variant="outline" asChild>
          <Link to="/adaptive-tax/calculator">
            <ArrowLeft className="h-4 w-4" />
            Calculator
          </Link>
        </Button>
      </div>

      {!calcId ? (
        <Card>
          <CardContent className="py-8 text-sm text-muted-foreground">
            Missing calculation id. Run a calculation first, then open the report from
            the calculator.
          </CardContent>
        </Card>
      ) : null}

      {storedQuery.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading calculation…
        </div>
      ) : null}

      {calcError ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-destructive">
              <FileText className="h-4 w-4" />
              Could not load report
            </CardTitle>
            <CardDescription>{calcError}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button type="button" variant="secondary" asChild>
              <Link to="/adaptive-tax/calculator">Back to calculator</Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {storedQuery.data ? (
        <ReportBody
          stored={storedQuery.data}
          explanation={explainQuery.data}
          reasoningGraph={reasoningQuery.data}
          reasoningLoading={reasoningQuery.isLoading || reasoningQuery.isFetching}
          explainLoading={explainQuery.isLoading || explainQuery.isFetching}
          explainError={explainError}
          onRetryExplain={() => void explainQuery.refetch()}
        />
      ) : null}
    </div>
  );
}
