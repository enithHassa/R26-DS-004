import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import { postCalculate, postExplain } from "../api";
import { buildCalculateRequest } from "../build-calculate-request";
import { buildPlainExplanation } from "../build-plain-explanation";
import { buildScenarioCitations } from "../build-scenario-citations";
import { formatLkr, formatMoneyInput, yaDisplay } from "../format-lkr";
import { useInterview } from "../session";

export function InterviewResultPage() {
  const navigate = useNavigate();
  const { session } = useInterview();
  const request = buildCalculateRequest(session);

  const calcQuery = useQuery({
    queryKey: [
      "optimization-explainable",
      "calculate",
      request.assessment_year,
      request.income,
      request.claims,
      request.exclude_source_doc_id,
    ],
    queryFn: () => postCalculate(request),
    retry: false,
  });

  const explainQuery = useQuery({
    queryKey: [
      "optimization-explainable",
      "explain",
      request.assessment_year,
      request.income,
      request.claims,
      request.exclude_source_doc_id,
    ],
    queryFn: () => postExplain(request),
    enabled: calcQuery.isSuccess,
    retry: false,
  });

  if (calcQuery.isPending) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Calculating tax from RAG rules for YA {yaDisplay(session.assessmentYear)}…
      </p>
    );
  }

  if (calcQuery.isError || !calcQuery.data) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive" role="alert">
          Could not calculate. Confirm the service on port 8008 is running.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable/reliefs")}
        >
          Back to reliefs
        </Button>
      </div>
    );
  }

  const result = calcQuery.data;
  const reliefLines = (result.relief_lines ?? []).filter((line) => line.applied > 0);
  const slabLines = result.slab_lines ?? [];
  const plainExplanation = buildPlainExplanation(result);
  const narrativeParagraphs = (explainQuery.data?.narrative ?? "")
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  const legalCitations = buildScenarioCitations(result, session);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Result</h2>
        <p className="text-sm text-muted-foreground">
          Tax for YA {yaDisplay(result.assessment_year)} uses this year’s RAG caps
          and First Schedule slabs — not a hardcoded table.
          {result.exclude_source_doc_id
            ? ` ${result.exclude_source_doc_id} is excluded; remaining group rows apply.`
            : ""}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SummaryTile label="Gross income" value={result.gross_income} />
        <SummaryTile label="Reliefs applied" value={result.total_reliefs} />
        <SummaryTile label="Taxable income" value={result.taxable_income} />
        <SummaryTile label="Tax payable" value={result.tax_payable} emphasize />
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Reliefs applied in this scenario</h3>
        {reliefLines.length === 0 ? (
          <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
            No reliefs reduced tax for this income and claim combination.
          </p>
        ) : (
          <ul className="space-y-3">
            {reliefLines.map((line) => (
            <li
              key={line.entry_id}
              className="space-y-2 rounded-md border p-3 text-xs"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-foreground">{line.display_name}</p>
                <p className="font-medium text-foreground">
                  Applied {formatLkr(line.applied)}
                </p>
              </div>
              <p className="text-muted-foreground">
                Cap:{" "}
                {line.cap == null
                  ? "—"
                  : line.unit === "percent"
                    ? `${line.cap}%`
                    : formatLkr(line.cap)}
                {" · "}
                Binder: {line.binder}
                {line.formula ? ` · ${line.formula}` : ""}
              </p>
              <div className="rounded-md border bg-muted/30 p-2 text-[11px] text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">Provenance</p>
                <p>
                  {line.act_name} · {line.section_ref} · {line.source_doc_id}
                </p>
                {line.quote ? <p className="italic">“{line.quote}”</p> : null}
              </div>
            </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Rate bands (this YA)</h3>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Band</th>
                <th className="px-3 py-2 font-medium">Rate</th>
                <th className="px-3 py-2 font-medium">Slice</th>
                <th className="px-3 py-2 font-medium">Tax</th>
                <th className="px-3 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {slabLines.map((band) => (
                <tr key={band.band_index} className="border-t">
                  <td className="px-3 py-2">
                    {band.band_label || `#${band.band_index}`}
                  </td>
                  <td className="px-3 py-2">{band.rate_percent}%</td>
                  <td className="px-3 py-2">{formatMoneyInput(String(band.slice))}</td>
                  <td className="px-3 py-2">{formatLkr(band.tax)}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {band.source_doc_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-4 rounded-md border bg-muted/20 p-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold">In plain English</h3>
          <p className="text-xs text-muted-foreground">
            A step-by-step story of your result — written so anyone can follow, no tax background
            needed.
          </p>
        </div>
        <p className="text-base font-medium leading-snug">{plainExplanation.headline}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{plainExplanation.summary}</p>
        <div className="space-y-4">
          {plainExplanation.blocks.map((block) => (
            <div key={block.heading} className="space-y-2">
              <h4 className="text-sm font-semibold text-foreground">{block.heading}</h4>
              <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
                {block.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Legal detail (optional)</h3>
        <p className="text-xs text-muted-foreground">
          Generated from the same calculation. Amounts above cannot be changed by this text.
        </p>
        {explainQuery.isPending ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading a short legal summary…
          </p>
        ) : null}
        {explainQuery.isError ? (
          <p className="text-sm text-muted-foreground">
            Legal summary is unavailable (needs OPENAI_API_KEY on the service). The plain
            English summary above is still complete.
          </p>
        ) : null}
        {explainQuery.data?.insufficient_evidence ? (
          <p className="text-sm text-muted-foreground">
            We could not match every step to a legal quote for this year
            {explainQuery.data.detail ? `: ${explainQuery.data.detail}` : "."}
          </p>
        ) : null}
        {narrativeParagraphs.length > 0 ? (
          <div className="space-y-2 text-sm leading-relaxed">
            {narrativeParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        ) : null}
        {legalCitations.length > 0 ? (
          <details className="rounded-md border bg-muted/30 p-3 text-xs">
            <summary className="cursor-pointer font-medium text-foreground">
              Legal sources for this scenario ({legalCitations.length})
            </summary>
            <ul className="mt-3 space-y-2 text-muted-foreground">
              {legalCitations.map((cite, index) => (
                <li
                  key={`${cite.entry_id ?? cite.source_doc_id}-${cite.section_ref}-${index}`}
                  className="rounded-md border bg-background p-2"
                >
                  {cite.display_name ? (
                    <p className="text-[11px] font-medium text-foreground">{cite.display_name}</p>
                  ) : null}
                  <p className="font-medium text-foreground">
                    {cite.act_name} · {cite.section_ref}
                  </p>
                  {cite.quote ? <p className="mt-1 italic">“{cite.quote}”</p> : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {explainQuery.data?.disclaimer ? (
          <p className="text-[11px] text-muted-foreground">{explainQuery.data.disclaimer}</p>
        ) : null}
      </section>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable/reliefs")}
        >
          Back to reliefs
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable/income")}
        >
          Back to income
        </Button>
      </div>
    </div>
  );
}

function SummaryTile({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: number;
  emphasize?: boolean;
}) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={emphasize ? "text-lg font-semibold" : "text-sm font-medium"}>
        {formatLkr(value)}
      </p>
    </div>
  );
}
