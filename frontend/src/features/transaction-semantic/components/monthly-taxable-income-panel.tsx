import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getProfileMonthlyTaxableIncome,
  getProfileMonthlyTaxableIncomeDetail,
  type ProfileTaxableIncomeMonthCoverage,
  type ProfileTaxableIncomeMonthDetailLine,
  type ProfileTaxableIncomeMonthlyLine,
} from "@/features/personalized-recommendation/api/profiles";
import { formatLkr } from "@/features/transaction-semantic/format-lkr";
import { normalizeDocumentTaxYear } from "@/lib/profile-bridge/tax-year-bridge";
import { cn } from "@/lib/utils";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

function monthKey(line: ProfileTaxableIncomeMonthlyLine): string {
  return line.calendar_month.slice(0, 7);
}

function monthLabel(calendarMonth: string): string {
  const date = new Date(`${calendarMonth}T00:00:00`);
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function MonthCoverageGrid({ coverage }: { coverage: ProfileTaxableIncomeMonthCoverage[] }) {
  if (!coverage.length) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/80" aria-hidden />
          Covered (extracted transactions)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-amber-400/90" aria-hidden />
          Missing (no extracted activity)
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
        {coverage.map((month) => {
          const covered = month.status === "covered";
          return (
            <div
              key={month.calendar_month}
              className={cn(
                "rounded-md border px-2 py-2 text-center text-xs",
                covered
                  ? "border-emerald-300/60 bg-emerald-50 text-emerald-950"
                  : "border-amber-300/70 bg-amber-50 text-amber-950",
              )}
              title={
                covered
                  ? `${month.extracted_transaction_count} extracted transaction(s)${month.classified_transaction_count ? `, ${month.classified_transaction_count} classified` : ""}${month.taxable_credit_count ? `, ${month.taxable_credit_count} taxable credit(s)` : ""}`
                  : "No extracted transactions for this month in the Year of Assessment"
              }
            >
              <div className="font-semibold">{month.month_label}</div>
              <div className="mt-1 text-[10px] opacity-80">{covered ? "Covered" : "Missing"}</div>
              {covered && Number(month.taxable_amount_lkr) > 0 ? (
                <div className="mt-1 text-[10px] font-medium">{formatLkr(month.taxable_amount_lkr)}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MonthlyTaxableIncomePanel({ profileId }: { profileId: string | null }) {
  const navigate = useNavigate();
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const setPendingTransactionBreakdown = useAuditorWorkspaceStore(
    (s) => s.setPendingTransactionBreakdown,
  );
  const documentTaxYear = normalizeDocumentTaxYear(profileSummary?.taxYear);
  const [lines, setLines] = useState<ProfileTaxableIncomeMonthlyLine[]>([]);
  const [monthCoverage, setMonthCoverage] = useState<ProfileTaxableIncomeMonthCoverage[]>([]);
  const [assessmentYearLabel, setAssessmentYearLabel] = useState<string | null>(null);
  const [yaPeriodStart, setYaPeriodStart] = useState<string | null>(null);
  const [yaPeriodEnd, setYaPeriodEnd] = useState<string | null>(null);
  const [coveredMonthCount, setCoveredMonthCount] = useState(0);
  const [missingMonthCount, setMissingMonthCount] = useState(0);
  const [totalTaxable, setTotalTaxable] = useState("0");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);
  const [detailLines, setDetailLines] = useState<ProfileTaxableIncomeMonthDetailLine[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadSummary(): Promise<void> {
    if (!profileId) {
      setLines([]);
      setMonthCoverage([]);
      setTotalTaxable("0");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await getProfileMonthlyTaxableIncome(profileId, documentTaxYear);
      setLines(response.lines);
      setMonthCoverage(response.month_coverage ?? []);
      setAssessmentYearLabel(response.assessment_year_label);
      setYaPeriodStart(response.ya_period_start);
      setYaPeriodEnd(response.ya_period_end);
      setCoveredMonthCount(response.covered_month_count ?? 0);
      setMissingMonthCount(response.missing_month_count ?? 0);
      setTotalTaxable(response.total_taxable_lkr);
    } catch (err) {
      setLines([]);
      setMonthCoverage([]);
      setTotalTaxable("0");
      setError(err instanceof Error ? err.message : "Failed to load monthly taxable income.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadSummary();
    setExpandedMonth(null);
    setDetailLines([]);
  }, [profileId, documentTaxYear]);

  const missingMonths = useMemo(
    () => monthCoverage.filter((m) => m.status === "missing"),
    [monthCoverage],
  );

  const hasTaxableRollup = lines.length > 0;
  const hasCoveredMonths = coveredMonthCount > 0;
  const hasNonTaxableCoverage = hasCoveredMonths && !hasTaxableRollup;

  const byMonth = useMemo(() => {
    const grouped = new Map<
      string,
      { monthStart: string; rows: ProfileTaxableIncomeMonthlyLine[]; total: number }
    >();
    for (const line of lines) {
      const key = monthKey(line);
      const bucket = grouped.get(key) ?? {
        monthStart: line.calendar_month,
        rows: [],
        total: 0,
      };
      bucket.rows.push(line);
      bucket.total += Number(line.taxable_amount_lkr);
      grouped.set(key, bucket);
    }
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [lines]);

  async function toggleMonth(monthStart: string, key: string): Promise<void> {
    if (expandedMonth === key) {
      setExpandedMonth(null);
      setDetailLines([]);
      return;
    }
    if (!profileId) return;
    setExpandedMonth(key);
    setDetailLoading(true);
    try {
      const detail = await getProfileMonthlyTaxableIncomeDetail(
        profileId,
        monthStart,
        documentTaxYear,
      );
      setDetailLines(detail.lines);
    } catch (err) {
      setDetailLines([]);
      setError(err instanceof Error ? err.message : "Failed to load month detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  function pushTotalsToOptimization(): void {
    const byClass = new Map<string, number>();
    for (const line of lines) {
      const amount = Number(line.taxable_amount_lkr);
      if (!Number.isFinite(amount) || amount <= 0) continue;
      byClass.set(line.class_key, (byClass.get(line.class_key) ?? 0) + amount);
    }
    const breakdown = [...byClass.entries()].map(([classKey, amount]) => ({
      classKey,
      amount,
    }));
    if (!breakdown.length) return;
    setPendingTransactionBreakdown(breakdown);
    navigate("/optimization-explainable-engine/income");
  }

  if (!profileId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monthly taxable income</CardTitle>
          <CardDescription>Select and lock a taxpayer profile to view saved monthly rollups.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>Monthly taxable income</CardTitle>
          <CardDescription>
            Month coverage uses extracted transaction dates from all documents uploaded for this
            taxpayer (any row counts — taxable, exempt, or review). Taxable totals below come from
            classified credits only. Sri Lanka Year of Assessment: 1 April – 31 March.
            {assessmentYearLabel ? ` Showing YA ${assessmentYearLabel}.` : ""}
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" disabled={isLoading} onClick={() => void loadSummary()}>
            Refresh
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={!hasTaxableRollup}
            title={
              hasNonTaxableCoverage
                ? "Months are covered but no taxable credits to merge — review/indeterminate rows are excluded"
                : "Send combined taxable income buckets to Optimization (manual step)"
            }
            onClick={pushTotalsToOptimization}
          >
            Push totals to Optimization
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading monthly rollup…
          </p>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {monthCoverage.length ? (
          <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">Year of Assessment coverage</p>
                <p className="text-xs text-muted-foreground">
                  {yaPeriodStart && yaPeriodEnd
                    ? `${yaPeriodStart} → ${yaPeriodEnd} · `
                    : ""}
                  {coveredMonthCount} of 12 months have extracted bank data
                </p>
              </div>
              {missingMonthCount > 0 ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900">
                  <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                  {missingMonthCount} month{missingMonthCount === 1 ? "" : "s"} missing
                </span>
              ) : (
                <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-900">
                  Full YA coverage
                </span>
              )}
            </div>
            <MonthCoverageGrid coverage={monthCoverage} />
            {missingMonths.length ? (
              <div className="rounded-md border border-amber-200 bg-amber-50/80 px-3 py-2 text-sm text-amber-950">
                <p className="font-medium">Upload or classify statements for missing months:</p>
                <p className="mt-1">{missingMonths.map((m) => m.month_label).join(", ")}</p>
              </div>
            ) : null}
            {hasNonTaxableCoverage ? (
              <p className="text-sm text-muted-foreground">
                {coveredMonthCount} month{coveredMonthCount === 1 ? "" : "s"} have extracted
                transactions, but no taxable credits are saved yet. Classify rows and resolve
                review items to build taxable totals for Optimization.
              </p>
            ) : null}
          </div>
        ) : null}

        {!isLoading && !lines.length && !hasCoveredMonths ? (
          <p className="text-sm text-muted-foreground">
            No extracted transactions yet for this profile and year. Upload and save documents,
            then refresh — months with any extracted row will show as covered.
          </p>
        ) : null}
        {lines.length ? (
          <p className="text-sm font-medium">Profile total (all documents): {formatLkr(totalTaxable)}</p>
        ) : null}
        <div className="space-y-2">
          {byMonth.map(([key, bucket]) => (
            <div key={key} className="rounded-md border">
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-muted/40"
                onClick={() => void toggleMonth(bucket.monthStart, key)}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  {expandedMonth === key ? (
                    <ChevronDown className="h-4 w-4" aria-hidden />
                  ) : (
                    <ChevronRight className="h-4 w-4" aria-hidden />
                  )}
                  {monthLabel(bucket.monthStart)}
                </span>
                <span className="text-sm text-muted-foreground">{formatLkr(String(bucket.total))}</span>
              </button>
              {expandedMonth === key ? (
                <div className="space-y-3 border-t px-3 py-3">
                  <div className="space-y-1">
                    {bucket.rows.map((row) => (
                      <div
                        key={`${row.calendar_month}-${row.class_key}-${row.tax_year ?? "na"}`}
                        className="flex justify-between text-sm"
                      >
                        <span>{row.class_key.replaceAll("_", " ")}</span>
                        <span>{formatLkr(row.taxable_amount_lkr)}</span>
                      </div>
                    ))}
                  </div>
                  {detailLoading ? (
                    <p className="text-xs text-muted-foreground">Loading transactions…</p>
                  ) : detailLines.length ? (
                    <div className="space-y-1 border-t pt-2">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Transactions
                      </p>
                      {detailLines.map((line) => (
                        <div key={line.extracted_transaction_id} className="text-xs">
                          <span className="font-medium">{line.tx_date}</span> · {line.description} ·{" "}
                          {formatLkr(line.taxable_amount_lkr)}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
