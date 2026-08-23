import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

import type {
  CatalogEngineReceipt,
  CatalogEngineResponse,
  ReliefInterviewRatesYear,
} from "../../api";
import { formatLkr } from "../../format-lkr";
import { yaDisplay } from "./types";

export const CATALOG_HONESTY_COPY =
  "This estimate is not independently verified against the official tax engine — it reflects extracted Act provisions only.";

export function ProvenanceReceipt({ receipts }: { receipts: CatalogEngineReceipt[] }) {
  if (!receipts.length) return null;
  return (
    <details className="rounded-md border bg-muted/30 p-3 text-sm">
      <summary className="cursor-pointer font-medium">
        Provenance receipt ({receipts.length})
      </summary>
      <ul className="mt-3 space-y-3">
        {receipts.map((r, idx) => (
          <li
            key={`${r.kind}-${r.source_doc_id}-${idx}`}
            className="border-t border-border/60 pt-2 text-xs text-muted-foreground first:border-0 first:pt-0"
          >
            <p className="font-medium text-foreground">
              {r.label} · {formatLkr(r.amount_lkr)}
            </p>
            <p>
              {r.act_name} · {r.section_ref} · {r.source_doc_id}
            </p>
            {r.quote ? <p className="mt-1 italic">“{r.quote}”</p> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function ActRulesPanel({
  ya,
  rates,
}: {
  ya: string;
  rates: ReliefInterviewRatesYear | null;
}) {
  const formulas = rates?.special_formulas ?? [];
  return (
    <details className="rounded-md border bg-muted/30 p-3 text-sm">
      <summary className="cursor-pointer font-medium">
        Act rules for YA {yaDisplay(ya)} ({formulas.length})
      </summary>
      <p className="mt-2 text-xs text-muted-foreground">
        Extractor-only provenance from{" "}
        <code className="text-[10px]">rates/{ya}.json</code>. These rules are shown
        as a receipt — they are not applied to the tax figure unless a separate
        engine binding exists.
      </p>
      {formulas.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          No special_formulas promoted for this YA yet.
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {formulas.map((f, idx) => (
            <li
              key={`${f.source_doc_id ?? "rule"}-${idx}`}
              className="border-t border-border/60 pt-2 text-xs text-muted-foreground first:border-0 first:pt-0"
            >
              <p className="font-medium text-foreground">
                {f.description || f.rule_kind || "Rule"}
                {f.value ? ` · ${f.value}` : ""}
              </p>
              <p>
                {f.act_name} · {f.section_ref} · {f.source_doc_id}
                {f.effective_from ? ` · from ${f.effective_from}` : ""}
              </p>
              {f.quote ? <p className="mt-1 italic">“{f.quote}”</p> : null}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

export function OfficialEngineWrap({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-3 border-l-4 border-primary pl-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold">Verified calculation (official engine)</h3>
        <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-medium text-primary-foreground">
          Official engine
        </span>
      </div>
      {children}
    </div>
  );
}

export function CatalogEstimateCard({
  ya,
  result,
  loading,
  error,
  onRetry,
  rates,
  engineYearCompanion,
  showInterviewReportLink,
}: {
  ya: string;
  result: CatalogEngineResponse | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  rates: ReliefInterviewRatesYear | null;
  /** True when this card sits under a calculate() official card. */
  engineYearCompanion?: boolean;
  showInterviewReportLink?: boolean;
}) {
  const navigate = useNavigate();
  const badge = result?.verification_badge;

  return (
    <div className="space-y-3 rounded-md border bg-card p-4 pl-3 border-l-4 border-l-muted-foreground/35">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-foreground">
          Full catalog estimate (includes all claimed reliefs)
        </h3>
        <span className="rounded-full border bg-muted/50 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          Extracted — not engine-verified
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{CATALOG_HONESTY_COPY}</p>

      {engineYearCompanion ? null : badge?.show ? (
        <p className="text-xs text-muted-foreground">
          {badge.label}. YA {yaDisplay(ya)} is outside the{" "}
          <code className="text-[10px]">calculate()</code> enum. Figures come from
          extracted <code className="text-[10px]">rates/{ya}.json</code>.
        </p>
      ) : badge ? (
        <p className="text-xs font-medium text-foreground">
          {badge.label}
        </p>
      ) : null}

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading catalog estimate…
        </p>
      ) : null}

      {error ? (
        <div className="space-y-2">
          <p className="text-sm text-foreground">Catalog estimate unavailable</p>
          <p className="text-xs text-muted-foreground">{error}</p>
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" onClick={onRetry}>
              Retry catalog estimate
            </Button>
          ) : null}
        </div>
      ) : null}

      {result && !error ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Catalog tax</p>
              <p className="text-base font-medium">{formatLkr(result.final_tax_lkr)}</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Taxable income</p>
              <p className="text-base font-medium">
                {formatLkr(result.taxable_income_lkr)}
              </p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Gross income</p>
              <p className="font-medium">{formatLkr(result.gross_income_lkr)}</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Personal relief</p>
              <p className="font-medium">{formatLkr(result.personal_relief_lkr)}</p>
            </div>
          </div>

          {(result.reliefs_applied?.length ?? 0) > 0 ? (
            <ul className="space-y-1 text-sm">
              {result.reliefs_applied?.map((row, idx) => (
                <li
                  key={`${row.compare_group_id ?? "r"}-${idx}`}
                  className="flex justify-between gap-3"
                >
                  <span>− {String(row.display_name ?? row.compare_group_id)}</span>
                  <span className="tabular-nums">
                    {formatLkr(String(row.amount_lkr ?? "0"))}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          {(result.band_slices?.length ?? 0) > 0 ? (
            <ul className="space-y-1 text-xs text-muted-foreground">
              {result.band_slices?.map((slice, idx) => (
                <li key={`band-${idx}`} className="flex justify-between gap-3">
                  <span>
                    {slice.band_label}
                    {slice.rate_percent != null ? ` (${slice.rate_percent}%)` : ""}
                  </span>
                  <span className="tabular-nums">
                    {formatLkr(String(slice.tax_slice_lkr ?? "0"))}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          <ProvenanceReceipt receipts={result.receipts ?? []} />
          <ActRulesPanel ya={ya} rates={rates} />

          {showInterviewReportLink ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void navigate("/adaptive-tax/relief-interview/report")}
            >
              Catalog report
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
