import { useQuery } from "@tanstack/react-query";
import { Loader2, Scale } from "lucide-react";
import { Link } from "react-router-dom";

import type { CalculateResponse } from "../../api";
import { postCalculate } from "../../api";
import { buildCalculateRequest } from "../../build-calculate-request";
import { buildPlainExplanation } from "../../build-plain-explanation";
import { buildScenarioCitations } from "../../build-scenario-citations";
import { yaDisplay } from "../../format-lkr";
import { PlainExplanationView } from "../../plain-explanation-view";
import { TAXWISE_OE_RESULT } from "../paths";
import { useTaxpayerOe } from "../taxpayer-oe-context";
import { OeNavChips } from "./oe-nav-chips";
import { UvPanelShell, YaSelector } from "./uv-chrome";

export function ExplanationsPanel() {
  const { scenario, isLoading, isError, selectYear, assessmentYear } = useTaxpayerOe();

  const liveQuery = useQuery({
    queryKey: [
      "taxwise-oe",
      "explanations-live",
      scenario?.assessmentYear,
      scenario?.session.income,
      scenario?.session.reliefAnswers,
    ],
    queryFn: () => postCalculate(buildCalculateRequest(scenario!.session)),
    enabled: Boolean(scenario && !scenario.finalized?.calculate_result),
    retry: false,
  });

  if (isError) {
    return (
      <p className="text-sm text-red-400" role="alert">
        Could not load explanations. Please try again in a moment.
      </p>
    );
  }

  if (isLoading || !scenario) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading explanations…
      </p>
    );
  }

  const ya = assessmentYear ?? scenario.assessmentYear;
  const official = scenario.finalized?.calculate_result as CalculateResponse | null | undefined;
  const result = official ?? liveQuery.data ?? null;
  const plain = result ? buildPlainExplanation(result) : null;
  const legalCitations = result
    ? buildScenarioCitations(result, scenario.session)
    : [];

  return (
    <UvPanelShell
      header={
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <OeNavChips />
            <h2 className="mt-3 text-lg font-semibold">Explanations</h2>
            <p className="text-sm text-[var(--uv-text-muted)]">
              YA {yaDisplay(ya)} — a plain-language walkthrough of your tax, with the Act quotes
              that support it.
            </p>
          </div>
          <YaSelector value={ya} years={scenario.availableYears} onChange={selectYear} />
        </div>
      }
    >
      <div className="flex flex-wrap gap-2">
        <Link
          to={TAXWISE_OE_RESULT}
          className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
        >
          Back to My Tax Result
        </Link>
      </div>

      {!result && liveQuery.isFetching ? (
        <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Preparing your explanation…
        </p>
      ) : null}

      {!result && liveQuery.isError ? (
        <p className="text-sm text-red-400" role="alert">
          Could not prepare an explanation yet. Open My Tax Result first, then come back here.
        </p>
      ) : null}

      {result && plain ? (
        <>
          <PlainExplanationView explanation={plain} variant="taxpayer" />

          {legalCitations.length > 0 ? (
            <section className="space-y-3 rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
              <div className="flex items-start gap-2">
                <Scale className="mt-0.5 h-4 w-4 shrink-0 text-[var(--uv-accent)]" aria-hidden />
                <div>
                  <h3 className="text-sm font-semibold text-[var(--uv-text)]">
                    Where this comes from in the Act
                  </h3>
                  <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
                    Short quotes from the same rules used to calculate your tax.
                  </p>
                </div>
              </div>
              <ul className="space-y-3">
                {legalCitations.map((cite, index) => (
                  <li
                    key={`${cite.entry_id ?? cite.source_doc_id}-${cite.section_ref}-${index}`}
                    className="rounded-lg border border-[var(--uv-border)] bg-black/20 p-3"
                  >
                    {cite.display_name ? (
                      <p className="text-sm font-medium text-[var(--uv-text)]">
                        {cite.display_name}
                      </p>
                    ) : null}
                    <p className="mt-1 text-xs font-medium text-[var(--uv-accent)]">
                      {cite.act_name}
                      {cite.section_ref ? ` · ${cite.section_ref}` : ""}
                    </p>
                    {cite.quote ? (
                      <p className="mt-2 text-sm leading-relaxed text-[var(--uv-text-muted)]">
                        “{cite.quote}”
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      ) : null}
    </UvPanelShell>
  );
}
