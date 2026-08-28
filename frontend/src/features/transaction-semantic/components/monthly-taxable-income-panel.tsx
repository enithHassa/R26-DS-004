import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getProfileMonthlyTaxableIncome,
  getProfileMonthlyTaxableIncomeDetail,
  type ProfileTaxableIncomeMonthDetailLine,
  type ProfileTaxableIncomeMonthlyLine,
} from "@/features/personalized-recommendation/api/profiles";
import { formatLkr } from "@/features/transaction-semantic/format-lkr";
import { normalizeDocumentTaxYear } from "@/lib/profile-bridge/tax-year-bridge";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

function monthKey(line: ProfileTaxableIncomeMonthlyLine): string {
  return line.calendar_month.slice(0, 7);
}

function monthLabel(calendarMonth: string): string {
  const date = new Date(`${calendarMonth}T00:00:00`);
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export function MonthlyTaxableIncomePanel({ profileId }: { profileId: string | null }) {
  const navigate = useNavigate();
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const setPendingTransactionBreakdown = useAuditorWorkspaceStore(
    (s) => s.setPendingTransactionBreakdown,
  );
  const documentTaxYear = normalizeDocumentTaxYear(profileSummary?.taxYear);
  const [lines, setLines] = useState<ProfileTaxableIncomeMonthlyLine[]>([]);
  const [totalTaxable, setTotalTaxable] = useState("0");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);
  const [detailLines, setDetailLines] = useState<ProfileTaxableIncomeMonthDetailLine[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadSummary(): Promise<void> {
    if (!profileId) {
      setLines([]);
      setTotalTaxable("0");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await getProfileMonthlyTaxableIncome(profileId, documentTaxYear);
      setLines(response.lines);
      setTotalTaxable(response.total_taxable_lkr);
    } catch (err) {
      setLines([]);
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
      const detail = await getProfileMonthlyTaxableIncomeDetail(profileId, monthStart);
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
            Saved from classified bank credits, grouped by calendar month and income class.
            {documentTaxYear ? ` Filtered to document tax year ${documentTaxYear}.` : ""}
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
            disabled={!lines.length}
            onClick={pushTotalsToOptimization}
          >
            Push totals to Optimization
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading monthly rollup…
          </p>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!isLoading && !lines.length ? (
          <p className="text-sm text-muted-foreground">
            No saved taxable credits yet. Classify documents for this profile to build the monthly
            summary.
          </p>
        ) : null}
        {lines.length ? (
          <p className="text-sm font-medium">Profile total: {formatLkr(totalTaxable)}</p>
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
