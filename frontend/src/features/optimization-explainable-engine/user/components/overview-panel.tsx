import type { CalculateResponse } from "../../api";
import { formatLkr, yaDisplay } from "../../format-lkr";
import { buildPlainExplanation } from "../../build-plain-explanation";
import { ordinaryTaxFromSlabs } from "../compute-scenario";
import { OeNavChips } from "./oe-nav-chips";
import {
  IncomeMixChart,
  IncomeSummaryStrip,
  OpportunityCards,
  ReliefImpactChart,
  TaxBreakdownPanel,
} from "./overview-charts";
import { UvPanelShell, YaSelector } from "./uv-chrome";
import {
  TAXWISE_OE_INCOME,
  TAXWISE_OE_RELIEFS,
  TAXWISE_OE_RESULT,
} from "../paths";
import { useTaxpayerOe } from "../taxpayer-oe-context";
import { TAXWISE_PROFILE } from "@/pages/user-view/paths";
import { Link } from "react-router-dom";
import { Eye, Loader2 } from "lucide-react";

function opportunitiesFromResult(result: CalculateResponse) {
  const taxable = result.taxable_income ?? 0;
  const bands = result.slab_lines ?? [];
  return (result.relief_lines ?? [])
    .filter((l) => l.applied > 0)
    .map((l) => {
      const taxWith = ordinaryTaxFromSlabs(taxable, bands);
      const taxBefore = ordinaryTaxFromSlabs(taxable + l.applied, bands);
      return {
        ...l,
        tax_saved: Math.max(0, taxBefore - taxWith),
        tax_before: taxBefore,
      };
    })
    .sort((a, b) => b.tax_saved - a.tax_saved || b.applied - a.applied)
    .slice(0, 5);
}

export function OverviewPanel() {
  const {
    scenario,
    isLoading,
    isError,
    explore,
    exploreLoading,
    selectYear,
    assessmentYear,
  } = useTaxpayerOe();

  if (isError) {
    return (
      <p className="text-sm text-red-400" role="alert">
        Could not load your profile scenario. Confirm Comp 3 (:8003) and OE Engine (:8009)
        are running, then refresh.
      </p>
    );
  }

  if (isLoading || !scenario) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading your tax scenario…
      </p>
    );
  }

  const ya = assessmentYear ?? scenario.assessmentYear;
  const finalizedResult = scenario.finalized?.calculate_result as
    | CalculateResponse
    | null
    | undefined;
  const official = finalizedResult ?? null;
  const result = official ?? explore?.optimized ?? null;
  const plain = result ? buildPlainExplanation(result) : null;
  const opportunityLines =
    explore?.opportunities ?? (result ? opportunitiesFromResult(result) : []);

  return (
    <UvPanelShell
      header={
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <OeNavChips />
            <h2 className="mt-3 text-xl font-bold tracking-tight">Tax strategy overview</h2>
            <p className="mt-1 text-sm text-[var(--uv-text-muted)]">
              {scenario.fullName || "Taxpayer"}
              {scenario.tin ? ` · TIN ${scenario.tin}` : ""}
              {ya ? ` · YA ${yaDisplay(ya)}` : ""}
              {opportunityLines.length > 0
                ? ` · ${opportunityLines.length} relief${opportunityLines.length === 1 ? "" : "s"} identified`
                : ""}
            </p>
          </div>
          <YaSelector
            value={ya}
            years={scenario.availableYears}
            onChange={selectYear}
          />
        </div>
      }
    >
      {official ? (
        <div className="inline-flex w-fit items-center rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
          Auditor approved · YA {yaDisplay(ya)}
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] px-3 py-2 text-sm text-[var(--uv-text-muted)]">
          No auditor-approved result for YA {yaDisplay(ya)} yet.
          {!scenario.hasProfileIncome ? (
            <>
              {" "}
              Complete your{" "}
              <Link to={TAXWISE_PROFILE} className="text-[var(--uv-accent)] underline">
                Tax Return Profile
              </Link>{" "}
              so we can explore what’s best for you.
            </>
          ) : (
            " Showing an exploratory estimate from your profile."
          )}
        </div>
      )}

      {result ? (
        <IncomeSummaryStrip income={scenario.session.income} result={result} />
      ) : exploreLoading ? (
        <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Estimating what’s best for you…
        </p>
      ) : null}

      {result || explore ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,0.9fr)]">
          <div className="space-y-4">
            <OpportunityCards opportunities={opportunityLines} />

            {opportunityLines.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                <Link
                  to={TAXWISE_OE_RELIEFS}
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)]"
                >
                  <Eye className="h-4 w-4" aria-hidden />
                  View relief details
                </Link>
                <Link
                  to={TAXWISE_OE_RESULT}
                  className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
                >
                  Compare full result
                </Link>
              </div>
            ) : null}

            <ReliefImpactChart lines={opportunityLines} />
          </div>

          <div className="space-y-4">
            <TaxBreakdownPanel explore={explore} official={official} />
            <IncomeMixChart income={scenario.session.income} />
          </div>
        </div>
      ) : null}

      {plain && result ? (
        <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start">
            <div className="min-w-0 space-y-2">
              <h2 className="text-base font-semibold">In plain English</h2>
              <p className="text-base font-medium leading-snug text-[var(--uv-text)]">
                {plain.headline}
              </p>
              <p className="text-sm leading-relaxed text-[var(--uv-text-muted)]">
                {plain.summary}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-2">
              {[
                { label: "Gross income", value: result.gross_income },
                { label: "Reliefs applied", value: result.total_reliefs },
                { label: "Taxable income", value: result.taxable_income },
                {
                  label: "Tax payable",
                  value: result.tax_payable,
                  emphasize: true,
                },
              ].map((cell) => (
                <div
                  key={cell.label}
                  className="rounded-lg border border-[var(--uv-border)] bg-black/20 px-3 py-2.5"
                >
                  <dt className="text-[11px] text-[var(--uv-text-muted)]">{cell.label}</dt>
                  <dd
                    className={`mt-1 text-sm font-semibold tabular-nums ${
                      cell.emphasize ? "text-[var(--uv-accent)]" : "text-[var(--uv-text)]"
                    }`}
                  >
                    {formatLkr(cell.value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--uv-border)] pt-4">
            <Link
              to={TAXWISE_OE_INCOME}
              className="rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)]"
            >
              Review income
            </Link>
            <Link
              to={TAXWISE_OE_RELIEFS}
              className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
            >
              Adjust reliefs
            </Link>
            <Link
              to={TAXWISE_OE_RESULT}
              className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
            >
              See full result
            </Link>
          </div>
        </section>
      ) : plain ? (
        <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
          <h2 className="text-base font-semibold">In plain English</h2>
          <p className="mt-2 text-sm font-medium">{plain.headline}</p>
          <p className="mt-1 text-sm text-[var(--uv-text-muted)]">{plain.summary}</p>
        </section>
      ) : null}

      {!(plain && result) ? (
        <div className="flex flex-wrap gap-2">
          <Link
            to={TAXWISE_OE_INCOME}
            className="rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)]"
          >
            Review income
          </Link>
          <Link
            to={TAXWISE_OE_RELIEFS}
            className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
          >
            Adjust reliefs
          </Link>
          <Link
            to={TAXWISE_OE_RESULT}
            className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium text-[var(--uv-text)] hover:bg-white/5"
          >
            See full result
          </Link>
        </div>
      ) : null}
    </UvPanelShell>
  );
}
