import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  approveAmendment,
  getAmendment,
  rejectAmendment,
  type ExtractRunItem,
  type RuleSourceItem,
} from "../api";

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-LK").format(value);
}

function GptAuditPanel({ run }: { run: ExtractRunItem }) {
  const audit = run.audit_payload ?? null;
  const structured = audit?.structured_rules ?? null;
  const focused =
    typeof audit?.focused_text === "string" ? audit.focused_text : null;
  const rawCompletion = audit?.raw_completion ?? null;
  const userPrompt =
    typeof audit?.user_prompt === "string" ? audit.user_prompt : null;
  const systemPrompt =
    typeof audit?.system_prompt === "string" ? audit.system_prompt : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">GPT audit</CardTitle>
        <CardDescription>
          Original PDF focus window → model prompts / raw completion → structured
          rules. Mode:{" "}
          <span className="font-medium text-foreground">
            {run.mode ?? "—"}
          </span>
          {" · "}
          model{" "}
          <code className="text-xs">{run.model_name}</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!audit ? (
          <p className="text-muted-foreground">
            No audit_payload on this extract run (re-extract after Phase 2 to
            capture prompts and raw GPT output).
          </p>
        ) : (
          <>
            <details className="rounded-md border bg-muted/30 p-3">
              <summary className="cursor-pointer font-medium">
                Structured rules (JSON)
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {JSON.stringify(structured, null, 2)}
              </pre>
            </details>
            <details className="rounded-md border bg-muted/30 p-3">
              <summary className="cursor-pointer font-medium">
                Focused PDF text
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {focused || "—"}
              </pre>
            </details>
            <details className="rounded-md border bg-muted/30 p-3">
              <summary className="cursor-pointer font-medium">
                System + user prompts
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {systemPrompt
                  ? `--- SYSTEM ---\n${systemPrompt}\n\n--- USER ---\n${userPrompt ?? ""}`
                  : (userPrompt ?? "—")}
              </pre>
            </details>
            <details className="rounded-md border bg-muted/30 p-3">
              <summary className="cursor-pointer font-medium">
                Raw GPT completion
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {rawCompletion
                  ? JSON.stringify(rawCompletion, null, 2)
                  : "— (fixture mode has no live completion)"}
              </pre>
            </details>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RuleReviewRow({ rule }: { rule: RuleSourceItem }) {
  return (
    <div className="grid gap-3 border-b py-4 last:border-b-0 md:grid-cols-2">
      <div className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">Section {rule.section}</span>
          <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{rule.rule_type}</span>
          <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{rule.status}</span>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
          <dt>amends</dt>
          <dd className="text-foreground">{rule.amends_section ?? "—"}</dd>
          <dt>concept</dt>
          <dd className="text-foreground">{rule.concept_id ?? "—"}</dd>
          <dt>threshold</dt>
          <dd className="text-foreground">{formatNumber(rule.threshold)}</dd>
          <dt>maximum</dt>
          <dd className="text-foreground">{formatNumber(rule.maximum)}</dd>
          <dt>effective</dt>
          <dd className="text-foreground">{rule.effective_date ?? "—"}</dd>
          <dt>formula</dt>
          <dd className="text-foreground break-words">{rule.formula ?? "—"}</dd>
          <dt>condition</dt>
          <dd className="text-foreground break-words">{rule.condition ?? "—"}</dd>
        </dl>
      </div>
      <div className="rounded-md border border-amber-200/80 bg-amber-50/80 p-3 text-sm dark:border-amber-900/50 dark:bg-amber-950/30">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Source quote
        </p>
        <blockquote className="border-l-2 border-amber-500/70 pl-3 text-foreground leading-relaxed">
          {rule.source_quote}
        </blockquote>
      </div>
    </div>
  );
}

export function AdaptiveTaxAdminReviewPage() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const queryClient = useQueryClient();
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const jobQuery = useQuery({
    queryKey: ["adaptive-tax", "amendment", jobId],
    queryFn: () => getAmendment(jobId),
    enabled: Boolean(jobId),
    retry: false,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveAmendment(jobId),
    onSuccess: (data) => {
      setActionError(null);
      setActionMessage(
        `Approved. ${data.rule_version_ids.length} rule version(s) stored. Merge stub: ${data.merge.reason}.`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["adaptive-tax", "amendment", jobId],
      });
    },
    onError: (err: Error) => {
      setActionMessage(null);
      setActionError(err.message);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectAmendment(jobId, rejectReason.trim()),
    onSuccess: (data) => {
      setShowReject(false);
      setRejectReason("");
      setActionError(null);
      setActionMessage(`Rejected: ${data.job.rejection_reason}`);
      void queryClient.invalidateQueries({
        queryKey: ["adaptive-tax", "amendment", jobId],
      });
    },
    onError: (err: Error) => {
      setActionMessage(null);
      setActionError(err.message);
    },
  });

  const job = jobQuery.data;
  const canReview = job?.status === "extracted";
  const busy = approveMutation.isPending || rejectMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Amendment review</h1>
          <p className="text-muted-foreground">
            Side-by-side structured rules and verbatim source quotes for admin
            approve/reject.
          </p>
        </div>
        <Button type="button" variant="outline" asChild>
          <Link to="/adaptive-tax/admin/upload">Back to upload</Link>
        </Button>
      </div>

      {!jobId ? (
        <p className="text-sm text-destructive">Missing job id in the URL.</p>
      ) : null}

      {jobQuery.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading amendment job…
        </div>
      ) : null}

      {jobQuery.isError ? (
        <p className="text-sm text-destructive">
          {jobQuery.error instanceof Error
            ? jobQuery.error.message
            : "Failed to load amendment job."}
        </p>
      ) : null}

      {job ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{job.original_filename}</CardTitle>
              <CardDescription>
                Job <code className="text-xs">{job.id}</code> · status{" "}
                <span className="font-medium text-foreground">{job.status}</span>
                {job.rejection_reason ? (
                  <> · reason: {job.rejection_reason}</>
                ) : null}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => approveMutation.mutate()}
                disabled={!canReview || busy}
              >
                {approveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Approve
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  setShowReject((open) => !open);
                  setActionError(null);
                }}
                disabled={!canReview || busy}
              >
                <XCircle className="h-4 w-4" />
                Reject
              </Button>
            </CardContent>
          </Card>

          {showReject ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Reject with reason</CardTitle>
                <CardDescription>
                  Required before the job is marked rejected.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="reject-reason">Reason</Label>
                  <Input
                    id="reject-reason"
                    value={rejectReason}
                    onChange={(event) => setRejectReason(event.target.value)}
                    placeholder="e.g. source quote does not match PDF"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={!rejectReason.trim() || busy}
                    onClick={() => rejectMutation.mutate()}
                  >
                    {rejectMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Confirm reject
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => setShowReject(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {actionMessage ? (
            <p className="text-sm text-emerald-700">{actionMessage}</p>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Extracted rules</CardTitle>
              <CardDescription>
                Left: structured fields. Right: mandatory source quote for viva
                traceability.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {job.rule_sources.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No rule_source rows yet. Run extract from the upload page.
                </p>
              ) : (
                <div>
                  {job.rule_sources.map((rule) => (
                    <RuleReviewRow key={rule.id} rule={rule} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {job.latest_extract_run ? (
            <GptAuditPanel run={job.latest_extract_run} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
