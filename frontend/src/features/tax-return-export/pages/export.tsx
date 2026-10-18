import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Download,
  FileSpreadsheet,
  Loader2,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getLatestTaxComputationSnapshot,
  getProfile,
  getProfileMonthlyTaxableIncome,
} from "@/features/personalized-recommendation/api/profiles";
import {
  getReliefs,
  postCalculate,
  type CalculateResponse,
} from "@/features/optimization-explainable-engine/api";
import { buildCalculateRequest } from "@/features/optimization-explainable-engine/build-calculate-request";
import { suggestClaimsFromProfile } from "@/features/optimization-explainable-engine/user/suggest-claims";
import {
  adjacentCompareYa,
  type InterviewSession,
} from "@/features/optimization-explainable-engine/types";
import { sessionFromSnapshot } from "@/lib/profile-bridge/oe-snapshot";
import { profileToInterviewIncome } from "@/lib/profile-bridge/tax-return-to-oe-income";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";
import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";

import {
  downloadTaxReturnWorkbook,
  triggerBlobDownload,
} from "../api";
import { buildTaxReturnExportPayload } from "../build-export-payload";

function buildSessionFromProfile(
  profile: Awaited<ReturnType<typeof getProfile>>,
  assessmentYear: string,
  reliefAnswers: InterviewSession["reliefAnswers"] = [],
): InterviewSession {
  const mapped = profileToInterviewIncome(profile);
  return {
    assessmentYear: normalizeTaxYearToOrm(assessmentYear || mapped.assessmentYear) || "2025_26",
    compareYear: adjacentCompareYa(
      normalizeTaxYearToOrm(assessmentYear || mapped.assessmentYear) || "2025_26",
    ),
    excludeSourceDocId: null,
    selectedCompareGroupId: null,
    income: mapped.income,
    reliefAnswers,
    evidenceChecks: {},
  };
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/20 px-3 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function TaxReturnExportPage() {
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);

  const profileQuery = useQuery({
    queryKey: ["tax-return-export", "profile", activeProfileId],
    queryFn: () => getProfile(activeProfileId!),
    enabled: Boolean(activeProfileId),
  });

  const assessmentYear = (() => {
    if (!profileQuery.data) return "2025_26";
    return (
      normalizeTaxYearToOrm(profileQuery.data.tax_year || "") ||
      normalizeTaxYearToOrm(profileToInterviewIncome(profileQuery.data).assessmentYear) ||
      "2025_26"
    );
  })();

  const snapshotQuery = useQuery({
    queryKey: ["tax-return-export", "snapshot", activeProfileId, assessmentYear],
    queryFn: () => getLatestTaxComputationSnapshot(activeProfileId!, assessmentYear),
    enabled: Boolean(activeProfileId) && Boolean(profileQuery.data),
    retry: false,
  });

  const taxableQuery = useQuery({
    queryKey: ["tax-return-export", "taxable", activeProfileId, profileQuery.data?.tax_year],
    queryFn: () =>
      getProfileMonthlyTaxableIncome(activeProfileId!, profileQuery.data?.tax_year || undefined),
    enabled: Boolean(activeProfileId) && Boolean(profileQuery.data),
    retry: false,
  });

  const calcQuery = useQuery({
    queryKey: [
      "tax-return-export",
      "calculate",
      activeProfileId,
      assessmentYear,
      snapshotQuery.dataUpdatedAt,
    ],
    queryFn: async (): Promise<{ session: InterviewSession; result: CalculateResponse; source: string }> => {
      const profile = profileQuery.data!;
      const snapshot = snapshotQuery.data;
      if (snapshot?.calculate_result && (snapshot.status === "calculated" || snapshot.status === "finalized")) {
        const session = sessionFromSnapshot(snapshot);
        return {
          session,
          result: snapshot.calculate_result as unknown as CalculateResponse,
          source: `Saved snapshot (${snapshot.status})`,
        };
      }

      const mapped = profileToInterviewIncome(profile);
      const ya = normalizeTaxYearToOrm(assessmentYear || mapped.assessmentYear) || "2025_26";
      let reliefAnswers: InterviewSession["reliefAnswers"] = [];
      try {
        const reliefs = await getReliefs(ya);
        reliefAnswers = suggestClaimsFromProfile(profile, mapped.income, reliefs.entries, ya);
      } catch {
        reliefAnswers = [];
      }

      const session = snapshot
        ? sessionFromSnapshot(snapshot)
        : buildSessionFromProfile(profile, ya, reliefAnswers);
      if (!snapshot) {
        session.reliefAnswers = reliefAnswers;
      }
      const result = await postCalculate(buildCalculateRequest(session));
      return { session, result, source: snapshot ? "Live calculate (snapshot income)" : "Live calculate (profile)" };
    },
    enabled: Boolean(activeProfileId) && Boolean(profileQuery.data) && !snapshotQuery.isLoading,
    retry: false,
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      if (!profileQuery.data || !calcQuery.data) {
        throw new Error("Profile and tax calculation are required before export.");
      }
      const payload = buildTaxReturnExportPayload({
        profile: profileQuery.data,
        session: calcQuery.data.session,
        calculateResult: calcQuery.data.result,
        taxableMonthly: taxableQuery.data ?? null,
      });
      return downloadTaxReturnWorkbook(payload);
    },
    onSuccess: ({ blob, filename }) => {
      triggerBlobDownload(blob, filename);
    },
  });

  const loading =
    profileQuery.isLoading ||
    snapshotQuery.isLoading ||
    (calcQuery.isLoading && !calcQuery.data);

  const result = calcQuery.data?.result;
  const taxable = taxableQuery.data;

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/[0.07] via-background to-muted/40 px-6 py-8 sm:px-8">
        <div
          className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-primary/10 blur-3xl"
          aria-hidden
        />
        <div className="relative space-y-3">
          <div className="flex items-center gap-2 text-primary">
            <FileSpreadsheet className="h-5 w-5" />
            <span className="text-xs font-semibold uppercase tracking-wider">Tax return export</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Export tax computation workbook
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Builds a single Excel file with TAX CALCULATION, SAVINGS, FD, UPLOAD FILE, Pension,
            and transaction taxable summary — mapped from the active taxpayer profile, Transaction
            Semantics taxable income, and Optimization &amp; Explainable Engine calculate results.
          </p>
        </div>
      </section>

      {!activeProfileId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Select a taxpayer</CardTitle>
            <CardDescription>
              Choose an active profile in the auditor workspace panel, then return here to preview
              and download the workbook.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/profile">Open profiles</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {activeProfileId && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              onClick={() => exportMutation.mutate()}
              disabled={loading || !calcQuery.data || exportMutation.isPending}
            >
              {exportMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download Excel
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                void profileQuery.refetch();
                void snapshotQuery.refetch();
                void taxableQuery.refetch();
                void calcQuery.refetch();
              }}
              disabled={loading}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh data
            </Button>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Assembling profile, taxable income, and OE calculation…
            </div>
          )}

          {calcQuery.isError && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Could not calculate tax via OE Engine (:8009).</p>
                <p className="mt-1 text-muted-foreground">
                  {(calcQuery.error as Error).message}. Start the engine and ensure a year view is
                  promoted, or complete the{" "}
                  <Link className="underline" to="/optimization-explainable-engine/result">
                    OE interview
                  </Link>
                  .
                </p>
              </div>
            </div>
          )}

          {exportMutation.isError && (
            <p className="text-sm text-destructive">
              Export failed: {(exportMutation.error as Error).message}
            </p>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Taxpayer profile</CardTitle>
                <CardDescription>
                  Name, TIN, FDs, savings, and pension from the Tax Return Profile.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {profileQuery.data ? (
                  <>
                    <p>
                      <span className="text-muted-foreground">Name: </span>
                      {profileQuery.data.full_name || "—"}
                    </p>
                    <p>
                      <span className="text-muted-foreground">Tax year: </span>
                      {profileQuery.data.tax_year || assessmentYear}
                    </p>
                    <p>
                      <span className="text-muted-foreground">OE source: </span>
                      {calcQuery.data?.source || "—"}
                    </p>
                  </>
                ) : (
                  <p className="text-muted-foreground">Loading profile…</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Transaction Semantics</CardTitle>
                <CardDescription>
                  Taxable income summary from classified bank transactions (Comp1).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {taxableQuery.isError && (
                  <p className="text-sm text-muted-foreground">
                    No monthly taxable income yet for this profile. Export will still include OE tax
                    sheets; the TX TAXABLE SUMMARY sheet will be omitted.
                  </p>
                )}
                {taxable && (
                  <div className="grid grid-cols-2 gap-3">
                    <Metric label="Total taxable" value={formatLkr(Number(taxable.total_taxable_lkr))} />
                    <Metric
                      label="Class lines"
                      value={String(taxable.lines.length)}
                    />
                    <Metric label="Covered months" value={String(taxable.covered_month_count)} />
                    <Metric label="Missing months" value={String(taxable.missing_month_count)} />
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Optimization &amp; Explainable Engine</CardTitle>
                <CardDescription>
                  Final taxable income, slab tax, WHT/APIT credits, and balance payable (:8009).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Metric label="Gross income" value={formatLkr(result.gross_income)} />
                    <Metric label="Taxable income" value={formatLkr(result.taxable_income)} />
                    <Metric label="Tax payable" value={formatLkr(result.tax_payable)} />
                    <Metric
                      label="Balance payable"
                      value={formatLkr(result.balance_payable ?? 0)}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Waiting for calculate result…</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Workbook sheets</CardTitle>
              <CardDescription>One .xlsx file with the following worksheets.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="grid gap-2 text-sm sm:grid-cols-2">
                <li>
                  <span className="font-medium">TAX CALCULATION</span> — OE income, reliefs, slabs,
                  WHT, balance
                </li>
                <li>
                  <span className="font-medium">SAVINGS</span> — profile savings interest / WHT
                </li>
                <li>
                  <span className="font-medium">FD</span> — profile fixed deposits
                </li>
                <li>
                  <span className="font-medium">UPLOAD FILE</span> — combined interest ledger
                </li>
                <li>
                  <span className="font-medium">Pension Sche.</span> — annual pension total when
                  present
                </li>
                <li>
                  <span className="font-medium">TX TAXABLE SUMMARY</span> — Comp1 class/month
                  taxable lines
                </li>
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
