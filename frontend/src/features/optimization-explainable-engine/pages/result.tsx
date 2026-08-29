import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";
import {
  getLatestTaxComputationSnapshot,
  saveTaxComputationSnapshot,
} from "@/features/personalized-recommendation/api/profiles";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";
import {
  auditorCommentsFromSnapshot,
  buildSnapshotPayload,
  sessionCalculationFingerprint,
  snapshotCalculationFingerprint,
} from "@/lib/profile-bridge/oe-snapshot";

import { postCalculate, postExplain, type CalculateResponse } from "../api";
import { buildCalculateRequest } from "../build-calculate-request";
import { buildPlainExplanation } from "../build-plain-explanation";
import { PlainExplanationView } from "../plain-explanation-view";
import { buildScenarioCitations } from "../build-scenario-citations";
import { formatLkr, yaDisplay } from "../format-lkr";
import { ResultRateTables } from "../result-rate-tables";
import { ResultSummaryBoard } from "../result-summary-board";
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
  const [auditorComments, setAuditorComments] = useState("");
  const commentsHydratedRef = useRef<string | null>(null);

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
    const snap = snapshotQuery.data;
    if (!snap) return;
    const key = `${snap.id}:${snap.updated_at ?? snap.created_at}`;
    if (commentsHydratedRef.current === key) return;
    commentsHydratedRef.current = key;
    const saved = auditorCommentsFromSnapshot(snap);
    if (saved) setAuditorComments(saved);
  }, [snapshotQuery.data]);

  useEffect(() => {
    if (!profileId || cachedResult || !calcQuery.data || calcQuery.isFetching) return;
    const key = `${fingerprint}:${calcQuery.dataUpdatedAt}`;
    if (savedRef.current === key) return;
    savedRef.current = key;
    // Prefer the textarea; fall back to any note already on this profile's snapshot.
    const commentsToSave =
      auditorComments.trim() || auditorCommentsFromSnapshot(snapshotQuery.data);
    void saveTaxComputationSnapshot(
      profileId,
      buildSnapshotPayload(session, {
        status: "calculated",
        calculateResult: calcQuery.data,
        explainNarrative: explainQuery.data?.narrative ?? null,
        auditorComments: commentsToSave,
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
    auditorComments,
    snapshotQuery.data,
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
          auditorComments,
          source: "auditor_manual",
        }),
      );
      setApproveState("done");
      setApproveMessage(
        auditorComments.trim()
          ? `Approved for taxpayer · YA ${yaDisplay(session.assessmentYear)}. Your comments are visible on that taxpayer’s TaxWise result.`
          : `Approved for taxpayer · YA ${yaDisplay(session.assessmentYear)}. Visible on TaxWise Optimization and Explainable.`,
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

      <ResultSummaryBoard result={result} />

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
                  <p className="font-medium text-foreground">Legal source</p>
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

      <PlainExplanationView explanation={plainExplanation} />

      <section className="space-y-2 rounded-xl border border-border/80 bg-card/40 p-3 shadow-sm">
        <div className="space-y-1">
          <Label htmlFor="oe-auditor-comments" className="text-sm font-semibold">
            Auditor comments for taxpayer
          </Label>
          <p className="text-xs text-muted-foreground">
            Optional note for this locked taxpayer only. Shown on their TaxWise result after you
            approve.
          </p>
        </div>
        <textarea
          id="oe-auditor-comments"
          value={auditorComments}
          onChange={(event) => setAuditorComments(event.target.value)}
          rows={4}
          placeholder="e.g. Confirm solar receipts before filing. Rental relief applied at 25% of rents."
          className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
        {!profileId ? (
          <p className="text-xs text-muted-foreground">
            Lock a taxpayer profile so comments can be saved with the approval.
          </p>
        ) : null}
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
