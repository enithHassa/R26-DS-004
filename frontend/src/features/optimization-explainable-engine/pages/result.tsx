import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";
import {
  getLatestTaxComputationSnapshot,
  saveTaxComputationSnapshot,
} from "@/features/personalized-recommendation/api/profiles";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";
import {
  buildSnapshotPayload,
  sessionCalculationFingerprint,
  snapshotCalculationFingerprint,
} from "@/lib/profile-bridge/oe-snapshot";

import { postCalculate, postExplain, type CalculateResponse } from "../api";
import { buildCalculateRequest } from "../build-calculate-request";
import { buildPlainExplanation } from "../build-plain-explanation";
import { buildScenarioCitations } from "../build-scenario-citations";
import { formatLkr, yaDisplay } from "../format-lkr";
import { ResultRateTables } from "../result-rate-tables";
import { useInterview } from "../session";

export function InterviewResultPage() {
  const navigate = useNavigate();
  const { session } = useInterview();
  const profileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const request = buildCalculateRequest(session);
  const fingerprint = sessionCalculationFingerprint(session);
  const savedRef = useRef<string | null>(null);
  const [approveState, setApproveState] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [approveMessage, setApproveMessage] = useState<string | null>(null);

  const snapshotQuery = useQuery({
    queryKey: ["oe-snapshot", profileId, session.assessmentYear],
    queryFn: () => getLatestTaxComputationSnapshot(profileId!, session.assessmentYear),
    enabled: Boolean(profileId),
    retry: false,
  });

  const cachedResult = useMemo((): CalculateResponse | null => {
    const snap = snapshotQuery.data;
    if (!snap?.calculate_result) return null;
    if (snapshotCalculationFingerprint(snap) !== fingerprint) return null;
    return snap.calculate_result as unknown as CalculateResponse;
  }, [snapshotQuery.data, fingerprint]);

  const cachedExplainNarrative = useMemo(() => {
    const snap = snapshotQuery.data;
    if (!snap?.explain_narrative) return null;
    if (snapshotCalculationFingerprint(snap) !== fingerprint) return null;
    return snap.explain_narrative;
  }, [snapshotQuery.data, fingerprint]);

  const calcQuery = useQuery({
    queryKey: [
      "optimization-explainable-engine",
      "calculate",
      request.assessment_year,
      request.income,
      request.claims,
      request.exclude_source_doc_id,
      request.wht_already_paid,
    ],
    queryFn: () => postCalculate(request),
    enabled: !cachedResult,
    retry: false,
  });

  const explainQuery = useQuery({
    queryKey: [
      "optimization-explainable-engine",
      "explain",
      request.assessment_year,
      request.income,
      request.claims,
      request.exclude_source_doc_id,
      request.wht_already_paid,
    ],
    queryFn: () => postExplain(request),
    enabled: calcQuery.isSuccess,
    retry: false,
  });

  useEffect(() => {
    if (!profileId || cachedResult || !calcQuery.data || calcQuery.isFetching) return;
    const key = `${fingerprint}:${calcQuery.dataUpdatedAt}`;
    if (savedRef.current === key) return;
    savedRef.current = key;
    void saveTaxComputationSnapshot(
      profileId,
      buildSnapshotPayload(session, {
        status: "calculated",
        calculateResult: calcQuery.data,
        explainNarrative: explainQuery.data?.narrative ?? null,
      }),
    ).then(() => {
      void snapshotQuery.refetch();
    });
  }, [
    profileId,
    cachedResult,
    calcQuery.data,
    calcQuery.isFetching,
    calcQuery.dataUpdatedAt,
    explainQuery.data?.narrative,
    fingerprint,
    session,
    snapshotQuery.refetch,
  ]);

  if (snapshotQuery.isLoading && !cachedResult) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Checking for a saved calculation…
      </p>
    );
  }

  if (!cachedResult && calcQuery.isPending) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Calculating tax from RAG rules for YA {yaDisplay(session.assessmentYear)}…
      </p>
    );
  }

  const result = cachedResult ?? calcQuery.data;
  if (!result || calcQuery.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive" role="alert">
          Could not calculate. POST /calculate needs a promoted year view. Confirm
          the service on port 8009 is running and a fixture Act was promoted.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable-engine/reliefs")}
        >
          Back to reliefs
        </Button>
      </div>
    );
  }

  const usingSavedResult = Boolean(cachedResult);
  const reliefLines = (result.relief_lines ?? []).filter((line) => line.applied > 0);
  const plainExplanation = buildPlainExplanation(result);
  const narrativeSource =
    cachedExplainNarrative ??
    (explainQuery.data?.narrative ?? "");
  const narrativeParagraphs = narrativeSource
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  const legalCitations = buildScenarioCitations(result, session);

  async function approveForTaxpayer() {
    if (!profileId || !result) return;
    setApproveState("loading");
    setApproveMessage(null);
    try {
      await saveTaxComputationSnapshot(
        profileId,
        buildSnapshotPayload(session, {
          status: "finalized",
          calculateResult: result,
          explainNarrative:
            cachedExplainNarrative ?? explainQuery.data?.narrative ?? null,
          source: "auditor_manual",
        }),
      );
      setApproveState("done");
      setApproveMessage(
        `Approved for taxpayer · YA ${yaDisplay(session.assessmentYear)}. Visible on TaxWise Optimization and Explainable.`,
      );
      void snapshotQuery.refetch();
    } catch (err) {
      setApproveState("error");
      setApproveMessage(
        err instanceof Error ? err.message : "Could not approve snapshot for taxpayer.",
      );
    }
  }

  return (
    <div className="space-y-6">
      <ActiveProfileBanner moduleLabel="Optimization result" />
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Result</h2>
        <p className="text-sm text-muted-foreground">
          Tax for YA {yaDisplay(result.assessment_year)} uses this year’s RAG caps
          and First Schedule slabs — not a hardcoded table.
          {usingSavedResult ? " Loaded from the saved profile calculation." : ""}
          {result.exclude_source_doc_id
            ? ` ${result.exclude_source_doc_id} is excluded; remaining group rows apply.`
            : ""}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SummaryTile label="Assessable (gross)" value={result.gross_income} />
        <SummaryTile label="Reliefs applied" value={result.total_reliefs} />
        <SummaryTile label="Taxable income" value={result.taxable_income} />
        <SummaryTile label="Tax payable" value={result.tax_payable} />
        {(result.terminal_benefit_tax ?? 0) > 0 ? (
          <SummaryTile
            label="Ordinary income tax"
            value={result.tax_payable - (result.terminal_benefit_tax ?? 0)}
          />
        ) : null}
        {(result.terminal_benefit_tax ?? 0) > 0 ? (
          <SummaryTile
            label="Of which terminal-benefit tax"
            value={result.terminal_benefit_tax ?? 0}
          />
        ) : null}
        <SummaryTile label="WHT credit" value={result.wht_credit ?? 0} />
        <SummaryTile label="APIT credit" value={result.apit_credit ?? 0} />
        {(result.tax_refund ?? 0) > 0 ? (
          <SummaryTile label="Refund" value={result.tax_refund ?? 0} emphasize />
        ) : (
          <SummaryTile
            label="Balance payable"
            value={result.balance_payable ?? result.tax_payable}
            emphasize
          />
        )}
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
              <li key={line.entry_id} className="space-y-2 rounded-md border p-3 text-xs">
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
                <div className="space-y-1 rounded-md border bg-muted/30 p-2 text-[11px] text-muted-foreground">
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

      <ResultRateTables result={result} />

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
        {!usingSavedResult && explainQuery.isPending ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading a short legal summary…
          </p>
        ) : null}
        {!usingSavedResult && explainQuery.isError ? (
          <p className="text-sm text-muted-foreground">
            Retrieve is unavailable. The plain English summary above still matches
            POST /calculate.
          </p>
        ) : null}
        {!usingSavedResult && (explainQuery.data?.hits ?? []).length > 0 ? (
          <details className="rounded-md border bg-muted/30 p-3 text-xs">
            <summary className="cursor-pointer font-medium text-foreground">
              Retrieved chunks ({explainQuery.data?.hit_count ?? explainQuery.data?.hits?.length})
            </summary>
            <ul className="mt-3 space-y-2 text-muted-foreground">
              {(explainQuery.data?.hits ?? []).map((hit) => (
                <li key={hit.chunk_id} className="rounded-md border bg-background p-2">
                  <p className="font-medium text-foreground">
                    {hit.source_doc_id}
                    {hit.section_ref ? ` · ${hit.section_ref}` : ""}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap">{hit.text}</p>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {!usingSavedResult && explainQuery.data?.insufficient_evidence ? (
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
        {!usingSavedResult && explainQuery.data?.disclaimer ? (
          <p className="text-[11px] text-muted-foreground">{explainQuery.data.disclaimer}</p>
        ) : null}
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable-engine/reliefs")}
        >
          Back to reliefs
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable-engine/income")}
        >
          Back to income
        </Button>
        {profileId ? (
          <Button
            type="button"
            disabled={approveState === "loading"}
            onClick={() => void approveForTaxpayer()}
          >
            {approveState === "loading" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                Approving…
              </>
            ) : approveState === "done" ? (
              "Approved for taxpayer"
            ) : (
              "Approve for taxpayer"
            )}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">
            Lock a taxpayer profile to approve this result for TaxWise.
          </p>
        )}
      </div>
      {approveMessage ? (
        <p
          className={`text-sm ${approveState === "error" ? "text-destructive" : "text-muted-foreground"}`}
          role={approveState === "error" ? "alert" : undefined}
        >
          {approveMessage}
        </p>
      ) : null}
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
