import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { postCalculate as postOeRagCalculate } from "@/features/optimization-explainable/api";
import { buildCalculateRequest as buildOeRagRequest } from "@/features/optimization-explainable/build-calculate-request";
import { postCalculate as postOeEngineCalculate } from "@/features/optimization-explainable-engine/api";
import { buildCalculateRequest as buildOeEngineRequest } from "@/features/optimization-explainable-engine/build-calculate-request";
import { sessionFromSnapshot } from "@/lib/profile-bridge/oe-snapshot";
import { profileToInterviewIncome } from "@/lib/profile-bridge/tax-return-to-oe-income";

import { getLatestTaxComputationSnapshot, getProfile } from "../api/profiles";
import type { DerivedFeatures } from "../types";
import { formatLkr } from "../utils/format-lkr";
import {
  parseSnapshotCalculateResult,
  profileTaxYearToAssessmentYear,
  summaryFromDerivedFeatures,
  summaryFromOeEngineResult,
  summaryFromOeRagResult,
  type ProfileTaxSummary,
} from "./profile-tax-context";

type Variant = "oe-engine" | "oe-rag";

type Props = {
  profileId: string | null;
  taxYear?: string;
  variant: Variant;
  derivedFeatures?: DerivedFeatures;
};

function serviceOfflineNotice(variant: Variant): string {
  if (variant === "oe-rag") {
    return "Optimization & Explainable (port 8008) is not running. Showing baseline tax from Component 3 derived features until you start that service or complete the OE RAG interview.";
  }
  return "Optimization & Explainable Engine (port 8009) is not running. Showing baseline tax from Component 3 derived features until you start that service or complete the OE Engine interview.";
}

const META: Record<
  Variant,
  { title: string; description: string; interviewPath: string; linkLabel: string }
> = {
  "oe-engine": {
    title: "Optimization & Explainable Engine",
    description:
      "Taxable income, tax payable, and applied reliefs from the OE Engine (saved snapshot or live estimate from profile income).",
    interviewPath: "/optimization-explainable-engine/income",
    linkLabel: "Open OE Engine interview",
  },
  "oe-rag": {
    title: "Optimization & Explainable (RAG)",
    description:
      "Cross-check taxable income, tax, and reliefs from the RAG-based component — feeds recommendation context.",
    interviewPath: "/optimization-explainable/income",
    linkLabel: "Open OE RAG interview",
  },
};

function buildSessionFromProfile(profile: Awaited<ReturnType<typeof getProfile>>, assessmentYear: string) {
  const mapped = profileToInterviewIncome(profile);
  return {
    assessmentYear: profileTaxYearToAssessmentYear(assessmentYear || mapped.assessmentYear),
    compareYear: profileTaxYearToAssessmentYear(assessmentYear || mapped.assessmentYear),
    excludeSourceDocId: null as string | null,
    selectedCompareGroupId: null as string | null,
    income: mapped.income,
    reliefAnswers: [] as [],
    evidenceChecks: {} as Record<string, Record<string, boolean>>,
  };
}

function TaxSummaryBody({ summary }: { summary: ProfileTaxSummary }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metric label="Taxable income" value={formatLkr(summary.taxableIncome)} accent />
        <Metric label="Tax payable" value={formatLkr(summary.taxPayable)} />
        <Metric label="Total reliefs" value={formatLkr(summary.totalReliefs)} />
      </div>
      {summary.reliefs.length > 0 ? (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Reliefs applied
          </p>
          <ul className="divide-y rounded-lg border text-sm">
            {summary.reliefs.map((r) => (
              <li key={r.name} className="flex items-center justify-between gap-2 px-3 py-2">
                <span className="min-w-0 truncate">{r.name}</span>
                <span className="shrink-0 tabular-nums text-emerald-700">
                  {formatLkr(r.applied)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No reliefs applied yet — complete the linked interview to claim reliefs for this profile.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Source: {summary.source === "snapshot" ? "Saved snapshot" : "Live estimate"}
        {summary.statusLabel ? ` · ${summary.statusLabel}` : ""}
      </p>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border bg-muted/20 px-3 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${accent ? "text-primary" : ""}`}>
        {value}
      </p>
    </div>
  );
}

export function ProfileTaxSourceSection({
  profileId,
  taxYear,
  variant,
  derivedFeatures,
}: Props) {
  const meta = META[variant];

  const profileQuery = useQuery({
    queryKey: ["profile-tax-source-profile", profileId],
    queryFn: () => getProfile(profileId!),
    enabled: !!profileId,
  });

  const assessmentYear = profileTaxYearToAssessmentYear(
    taxYear ?? profileQuery.data?.tax_year ?? "2025_26",
  );

  const snapshotQuery = useQuery({
    queryKey: ["profile-tax-snapshot", profileId, assessmentYear],
    queryFn: () => getLatestTaxComputationSnapshot(profileId!, assessmentYear),
    enabled: !!profileId && variant === "oe-engine",
    retry: false,
  });

  const calcQuery = useQuery({
    queryKey: ["profile-tax-live", profileId, assessmentYear, variant],
    queryFn: async () => {
      const profile = profileQuery.data!;
      if (variant === "oe-engine") {
        const session = snapshotQuery.data
          ? sessionFromSnapshot(snapshotQuery.data)
          : buildSessionFromProfile(profile, assessmentYear);
        return postOeEngineCalculate(buildOeEngineRequest(session));
      }
      const session = buildSessionFromProfile(profile, assessmentYear);
      return postOeRagCalculate(buildOeRagRequest(session));
    },
    enabled: !!profileId && !!profileQuery.data && (variant !== "oe-engine" || !snapshotQuery.isLoading),
    retry: false,
  });

  const snapshotResult = parseSnapshotCalculateResult(snapshotQuery.data?.calculate_result ?? null);
  const liveSummary: ProfileTaxSummary | null = (() => {
    if (variant === "oe-engine" && snapshotResult) {
      return summaryFromOeEngineResult(snapshotResult, "snapshot", snapshotQuery.data?.status);
    }
    if (calcQuery.data) {
      return variant === "oe-engine"
        ? summaryFromOeEngineResult(calcQuery.data, "live")
        : summaryFromOeRagResult(calcQuery.data, "live");
    }
    return null;
  })();

  const fallbackSummary = derivedFeatures ? summaryFromDerivedFeatures(derivedFeatures) : null;
  const usingFallback = !liveSummary && calcQuery.isError && !!fallbackSummary;
  const summary = liveSummary ?? (usingFallback ? fallbackSummary : null);

  const loading =
    profileQuery.isLoading ||
    (variant === "oe-engine" && snapshotQuery.isLoading) ||
    (calcQuery.isLoading && !usingFallback);

  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{meta.title}</CardTitle>
            <CardDescription className="mt-1">{meta.description}</CardDescription>
          </div>
          {profileId && (
            <Link
              to={meta.interviewPath}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              {meta.linkLabel}
              <ExternalLink className="h-3 w-3" />
            </Link>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {!profileId && (
          <p className="text-sm text-muted-foreground">
            Select a profile to load tax context used alongside recommendations.
          </p>
        )}
        {profileId && loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading tax computation…
          </div>
        )}
        {profileId && calcQuery.isError && !summary && (
          <p className="text-sm text-muted-foreground">
            {(calcQuery.error as Error).message}
            {!derivedFeatures && " Select a profile with derived features, or start the service and retry."}
          </p>
        )}
        {usingFallback && (
          <p className="mb-4 rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            {serviceOfflineNotice(variant)}
          </p>
        )}
        {summary && <TaxSummaryBody summary={summary} />}
      </CardContent>
    </Card>
  );
}
