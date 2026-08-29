import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import type { CalculateResponse } from "../../api";
import { postCalculate } from "../../api";
import { buildCalculateRequest } from "../../build-calculate-request";
import { buildPlainExplanation } from "../../build-plain-explanation";
import { formatLkr, yaDisplay } from "../../format-lkr";
import {
  activeSlabLines,
  formatBandRange,
  slabKey,
  taxBuildupFromResult,
} from "../../tax-buildup";
import { OeNavChips } from "./oe-nav-chips";
import { UvPanelShell, UvTile, YaSelector } from "./uv-chrome";
import { useTaxpayerOe } from "../taxpayer-oe-context";

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
  const plain = result ? buildPlainExplanation(result) : null;
  const reliefLines = (result?.relief_lines ?? []).filter((l) => l.applied > 0);

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
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <UvTile label="Gross income" value={formatLkr(result.gross_income)} />
            <UvTile label="Reliefs applied" value={formatLkr(result.total_reliefs)} />
            <UvTile label="Taxable income" value={formatLkr(result.taxable_income)} />
            <UvTile label="Tax payable" value={formatLkr(result.tax_payable)} emphasize />
            <UvTile label="WHT credit" value={formatLkr(result.wht_credit ?? 0)} />
            <UvTile label="APIT credit" value={formatLkr(result.apit_credit ?? 0)} />
            <UvTile
              label="Balance payable"
              value={formatLkr(result.balance_payable ?? result.tax_payable)}
              emphasize
            />
          </div>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold">Reliefs applied</h3>
            {reliefLines.length === 0 ? (
              <p className="text-sm text-[var(--uv-text-muted)]">
                No reliefs reduced tax in this scenario.
              </p>
            ) : (
              <ul className="space-y-2">
                {reliefLines.map((line) => (
                  <li
                    key={line.entry_id}
                    className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3 text-sm"
                  >
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{line.display_name}</span>
                      <span className="text-[var(--uv-accent)]">{formatLkr(line.applied)}</span>
                    </div>
                    {line.quote ? (
                      <p className="mt-1 text-xs italic text-[var(--uv-text-muted)]">
                        “{line.quote}”
                      </p>
                    ) : null}
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

          {plain ? (
            <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
              <h3 className="text-sm font-semibold">In plain English</h3>
              <p className="mt-2 text-sm font-medium">{plain.headline}</p>
              <p className="mt-1 text-sm text-[var(--uv-text-muted)]">{plain.summary}</p>
              <div className="mt-4 space-y-3">
                {plain.blocks.map((block) => (
                  <div key={block.heading}>
                    <h4 className="text-sm font-semibold">{block.heading}</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-[var(--uv-text-muted)]">
                      {block.lines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </UvPanelShell>
  );
}
