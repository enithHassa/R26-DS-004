import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Loader2, MessageSquareText } from "lucide-react";

import type { CalculateResponse } from "../../api";
import { postCalculate } from "../../api";
import { buildCalculateRequest } from "../../build-calculate-request";
import { formatLkr, yaDisplay } from "../../format-lkr";
import { auditorCommentsFromSnapshot } from "@/lib/profile-bridge/oe-snapshot";
import {
  activeSlabLines,
  formatBandRange,
  slabKey,
  taxBuildupFromResult,
} from "../../tax-buildup";
import { TAXWISE_OE_EXPLANATIONS } from "../paths";
import { useTaxpayerOe } from "../taxpayer-oe-context";
import { OeNavChips } from "./oe-nav-chips";
import { ResultFlowBoard } from "./result-flow-board";
import { UvPanelShell, YaSelector } from "./uv-chrome";

export function ResultPanel() {
  const { scenario, isLoading, isError, selectYear, assessmentYear } = useTaxpayerOe();

  const liveQuery = useQuery({
    queryKey: [
      "taxwise-oe",
      "result-live",
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
        Could not load result. Confirm Comp 3 (:8003) and OE Engine (:8009) are running, then
        refresh.
      </p>
    );
  }

  if (isLoading || !scenario) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading result…
      </p>
    );
  }

  const ya = assessmentYear ?? scenario.assessmentYear;
  const official = scenario.finalized?.calculate_result as CalculateResponse | null | undefined;
  const result = official ?? liveQuery.data ?? null;
  const reliefLines = (result?.relief_lines ?? []).filter((l) => l.applied > 0);
  const auditorNote = auditorCommentsFromSnapshot(scenario.finalized);

  return (
    <UvPanelShell
      header={
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <OeNavChips />
            <h2 className="mt-3 text-lg font-semibold">My Tax Result</h2>
            <p className="text-sm text-[var(--uv-text-muted)]">
              YA {yaDisplay(ya)}
              {official
                ? " — auditor-approved computation."
                : " — live calculation from your income and claims."}
            </p>
          </div>
          <YaSelector value={ya} years={scenario.availableYears} onChange={selectYear} />
        </div>
      }
    >
      {official ? (
        <div className="inline-flex w-fit items-center rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
          Auditor approved · YA {yaDisplay(ya)}
        </div>
      ) : null}

      {auditorNote ? (
        <section className="rounded-xl border border-sky-500/35 bg-sky-500/10 p-4">
          <div className="mb-2 flex items-center gap-2 text-sky-200">
            <MessageSquareText className="h-4 w-4 shrink-0" aria-hidden />
            <h3 className="text-sm font-semibold">Message from your auditor</h3>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--uv-text)]">
            {auditorNote}
          </p>
        </section>
      ) : null}

      {!result && liveQuery.isFetching ? (
        <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Calculating…
        </p>
      ) : null}

      {!result && liveQuery.isError ? (
        <p className="text-sm text-red-400" role="alert">
          Could not calculate. Confirm OE Engine has a promoted year view for YA{" "}
          {yaDisplay(ya)}.
        </p>
      ) : null}

      {result ? (
        <>
          <ResultFlowBoard result={result} />

          <section className="space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold">Reliefs applied</h3>
              <Link
                to={TAXWISE_OE_EXPLANATIONS}
                className="text-xs font-medium text-[var(--uv-accent)] hover:underline"
              >
                Why these applied →
              </Link>
            </div>
            {reliefLines.length === 0 ? (
              <p className="text-sm text-[var(--uv-text-muted)]">
                No reliefs reduced tax in this scenario.
              </p>
            ) : (
              <ul className="space-y-2">
                {reliefLines.map((line) => (
                  <li
                    key={line.entry_id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] px-3 py-2.5 text-sm"
                  >
                    <span className="font-medium">{line.display_name}</span>
                    <span className="shrink-0 tabular-nums text-[var(--uv-accent)]">
                      {formatLkr(line.applied)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold">How tax is built</h3>
            <p className="text-xs text-[var(--uv-text-muted)]">
              Taxable income {formatLkr(result.taxable_income)} is split across First Schedule
              rate bands. Each row is one band: income in that band × rate = tax.
            </p>
            {(result.slab_lines ?? []).length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)]">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-[var(--uv-border)] text-[11px] text-[var(--uv-text-muted)]">
                    <tr>
                      <th className="px-3 py-2 font-medium">Band / rate</th>
                      <th className="px-3 py-2 font-medium">Income in band</th>
                      <th className="px-3 py-2 font-medium text-right">Tax</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeSlabLines(result.slab_lines).map((slab, i) => (
                      <tr
                        key={slabKey(slab, i)}
                        className="border-b border-[var(--uv-border)]/60 last:border-0"
                      >
                        <td className="px-3 py-2">
                          <span className="font-medium">{slab.rate_percent}%</span>
                          <span className="mt-0.5 block text-[11px] text-[var(--uv-text-muted)]">
                            {slab.band_label || formatBandRange(slab)}
                          </span>
                        </td>
                        <td className="px-3 py-2 tabular-nums text-[var(--uv-text-muted)]">
                          {formatLkr(slab.slice)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums font-medium">
                          {formatLkr(slab.tax)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    {(() => {
                      const buildup = taxBuildupFromResult(result);
                      return (
                        <>
                          <tr className="border-t border-[var(--uv-border)]">
                            <td className="px-3 py-2 text-[var(--uv-text-muted)]" colSpan={2}>
                              Ordinary tax (sum of bands)
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums font-medium">
                              {formatLkr(buildup.ordinaryTax)}
                            </td>
                          </tr>
                          {buildup.terminalTax > 0 ? (
                            <tr>
                              <td className="px-3 py-2 text-[var(--uv-text-muted)]" colSpan={2}>
                                + Terminal-benefit tax
                              </td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {formatLkr(buildup.terminalTax)}
                              </td>
                            </tr>
                          ) : null}
                          <tr>
                            <td className="px-3 py-2 font-medium" colSpan={2}>
                              Tax payable
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums font-semibold text-[var(--uv-accent)]">
                              {formatLkr(buildup.taxPayable)}
                            </td>
                          </tr>
                          {buildup.apitCredit > 0 ? (
                            <tr>
                              <td className="px-3 py-2 text-[var(--uv-text-muted)]" colSpan={2}>
                                − APIT credit
                              </td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {formatLkr(buildup.apitCredit)}
                              </td>
                            </tr>
                          ) : null}
                          {buildup.whtCredit > 0 ? (
                            <tr>
                              <td className="px-3 py-2 text-[var(--uv-text-muted)]" colSpan={2}>
                                − WHT credit
                              </td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {formatLkr(buildup.whtCredit)}
                              </td>
                            </tr>
                          ) : null}
                          <tr className="border-t border-[var(--uv-border)]">
                            <td className="px-3 py-2 font-semibold" colSpan={2}>
                              {buildup.taxRefund > 0 ? "Refund" : "Balance payable"}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums text-base font-semibold text-[var(--uv-accent)]">
                              {formatLkr(
                                buildup.taxRefund > 0
                                  ? buildup.taxRefund
                                  : buildup.balancePayable,
                              )}
                            </td>
                          </tr>
                        </>
                      );
                    })()}
                  </tfoot>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--uv-text-muted)]">No rate bands returned.</p>
            )}
          </section>

          <Link
            to={TAXWISE_OE_EXPLANATIONS}
            className="flex items-start gap-3 rounded-xl border border-[var(--uv-accent)]/40 bg-[var(--uv-accent)]/10 p-4 transition-colors hover:bg-[var(--uv-accent)]/15"
          >
            <BookOpen className="mt-0.5 h-5 w-5 shrink-0 text-[var(--uv-accent)]" aria-hidden />
            <div>
              <p className="text-sm font-semibold text-[var(--uv-text)]">Read the explanations</p>
              <p className="mt-1 text-xs leading-relaxed text-[var(--uv-text-muted)]">
                Plain-language walkthrough and Act quotes for your reliefs — kept on a separate
                page so this result stays short.
              </p>
            </div>
          </Link>
        </>
      ) : null}
    </UvPanelShell>
  );
}
