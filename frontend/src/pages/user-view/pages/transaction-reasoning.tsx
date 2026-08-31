import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Flag,
  Scale,
  Sparkles,
} from "lucide-react";

import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import {
  flagUserPortalTransaction,
  getUserPortalTransactionDetail,
} from "@/pages/user-view/api/user-transactions";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";
import { TAXWISE_TRANSACTIONS } from "@/pages/user-view/paths";
import { cn } from "@/lib/utils";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-LK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function categoryLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function verdictLabel(status: string): string {
  switch (status) {
    case "taxable":
      return "Taxable";
    case "exempt":
      return "Non-taxable";
    case "partially_taxable":
      return "Partially taxable";
    case "unknown":
      return "Uncertain";
    default:
      return status;
  }
}

function verdictClass(status: string): string {
  switch (status) {
    case "taxable":
      return "border-red-500/30 bg-red-500/10 text-red-300";
    case "exempt":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "unknown":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    default:
      return "border-sky-500/30 bg-sky-500/10 text-sky-300";
  }
}

function shortTxnId(id: string): string {
  return `TXN-${id.replace(/-/g, "").slice(0, 4).toUpperCase()}`;
}

export function UserTransactionReasoningPage() {
  const profileId = useUserSessionStore((s) => s.profileId);
  const queryClient = useQueryClient();
  const { extractedTransactionId } = useParams<{ extractedTransactionId: string }>();
  const [flagOpen, setFlagOpen] = useState(false);
  const [flagMessage, setFlagMessage] = useState("");

  const detailQuery = useQuery({
    queryKey: ["user-transaction-detail", profileId, extractedTransactionId],
    queryFn: () => getUserPortalTransactionDetail(profileId!, extractedTransactionId!),
    enabled: !!profileId && !!extractedTransactionId,
  });

  const flagMutation = useMutation({
    mutationFn: (message: string) =>
      flagUserPortalTransaction(profileId!, extractedTransactionId!, message),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["user-transaction-detail", profileId, extractedTransactionId],
      });
      setFlagOpen(false);
    },
  });

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  if (!extractedTransactionId) {
    return <Navigate to={TAXWISE_TRANSACTIONS} replace />;
  }

  const detail = detailQuery.data;
  const confidencePct =
    detail?.confidence != null ? Math.round(detail.confidence * 100) : null;

  return (
    <UserViewShell
      title="Taxability Reasoning Detail"
      subtitle={
        detail
          ? `${shortTxnId(detail.extracted_transaction_id)} · ${detail.description.slice(0, 48)}${detail.description.length > 48 ? "…" : ""}`
          : "Loading transaction reasoning…"
      }
      actions={
        <Link
          to={TAXWISE_TRANSACTIONS}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--uv-border)] px-3 py-2 text-sm text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-text)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
      }
    >
      {detailQuery.isLoading ? (
        <p className="text-sm text-[var(--uv-text-muted)]">Loading reasoning detail…</p>
      ) : null}

      {detailQuery.isError ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-300">
          {(detailQuery.error as Error).message || "Transaction not found."}
          <div className="mt-3">
            <Link to={TAXWISE_TRANSACTIONS} className="text-[var(--uv-accent)] hover:underline">
              Return to transactions
            </Link>
          </div>
        </div>
      ) : null}

      {detail ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_minmax(0,18rem)]">
          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
            <h2 className="text-sm font-semibold text-[var(--uv-text)]">Transaction summary</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div>
                <dt className="text-[var(--uv-text-muted)]">Transaction ID</dt>
                <dd className="font-mono text-[var(--uv-text)]">
                  {shortTxnId(detail.extracted_transaction_id)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--uv-text-muted)]">Date</dt>
                <dd className="text-[var(--uv-text)]">{formatDate(detail.tx_date)}</dd>
              </div>
              <div>
                <dt className="text-[var(--uv-text-muted)]">Description</dt>
                <dd className="text-[var(--uv-text)]">{detail.description}</dd>
              </div>
              <div>
                <dt className="text-[var(--uv-text-muted)]">Amount</dt>
                <dd className="font-semibold text-[var(--uv-text)]">{formatLkr(detail.amount_lkr)}</dd>
              </div>
              <div>
                <dt className="text-[var(--uv-text-muted)]">Direction</dt>
                <dd>
                  <span className="rounded-full bg-[var(--uv-accent)]/15 px-2 py-0.5 text-xs font-medium text-[var(--uv-accent)]">
                    {detail.direction}
                  </span>
                </dd>
              </div>
              {detail.bank_detected ? (
                <div>
                  <dt className="text-[var(--uv-text-muted)]">Bank</dt>
                  <dd className="text-[var(--uv-text)]">{detail.bank_detected}</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-[var(--uv-text-muted)]">Final verdict</dt>
                <dd className="mt-1">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
                      verdictClass(detail.taxability_status),
                    )}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {verdictLabel(detail.taxability_status).toUpperCase()}
                  </span>
                </dd>
              </div>
            </dl>
          </section>

          <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
            <div className="mb-5 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[var(--uv-accent)]" />
              <h2 className="text-sm font-semibold text-[var(--uv-text)]">AI reasoning trace</h2>
            </div>

            <ol className="space-y-0">
              {detail.reasoning_steps.map((step, index) => {
                const isLast = index === detail.reasoning_steps.length - 1;
                const isDecision = step.is_decision || step.step_key === "tax_rule_mapping";
                return (
                  <li key={`${step.step_key}-${index}`} className="relative flex gap-4 pb-6">
                    {!isLast ? (
                      <span
                        className="absolute left-[11px] top-6 h-[calc(100%-12px)] w-px bg-[var(--uv-border)]"
                        aria-hidden
                      />
                    ) : null}
                    <span
                      className={cn(
                        "relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                        isDecision
                          ? "border-[var(--uv-accent)] bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]"
                          : "border-[var(--uv-border)] bg-[var(--uv-bg)] text-[var(--uv-text-muted)]",
                      )}
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--uv-text)]">{step.title}</p>
                      <p className="mt-1 text-sm leading-relaxed text-[var(--uv-text-muted)]">
                        {step.detail}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="mt-2 grid gap-3 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-4 sm:grid-cols-2">
              <div>
                <p className="text-xs text-[var(--uv-text-muted)]">Category applied</p>
                <p className="mt-1 text-sm font-medium text-[var(--uv-text)]">
                  {categoryLabel(detail.semantic_category)}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--uv-text-muted)]">Economic event</p>
                <p className="mt-1 text-sm font-medium text-[var(--uv-text)]">
                  {detail.economic_event ? categoryLabel(detail.economic_event) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--uv-text-muted)]">Tax rule</p>
                <p className="mt-1 text-sm font-medium text-[var(--uv-text)]">
                  {detail.rule_reference || detail.tax_rule_code || "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--uv-text-muted)]">Assessable amount</p>
                <p className="mt-1 text-sm font-semibold text-[var(--uv-text)]">
                  {formatLkr(detail.taxable_amount_lkr)}
                </p>
              </div>
            </div>

            {detail.explanation ? (
              <p className="mt-4 text-sm leading-relaxed text-[var(--uv-text-muted)]">
                {detail.explanation}
              </p>
            ) : null}
          </section>

          <aside className="space-y-4">
            {detail.narrative_hits.length > 0 ? (
              <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Scale className="h-4 w-4 text-[var(--uv-accent)]" />
                  <h2 className="text-sm font-semibold text-[var(--uv-text)]">
                    What influenced this
                  </h2>
                </div>
                <div className="space-y-3">
                  {detail.narrative_hits.map((hit) => {
                    const width = Math.max(8, Math.round(hit.score * 100));
                    return (
                      <div key={hit.class_key}>
                        <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                          <span className="text-[var(--uv-text)]">{categoryLabel(hit.class_key)}</span>
                          <span className="tabular-nums text-[var(--uv-text-muted)]">
                            {hit.score.toFixed(2)}
                          </span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                          <div
                            className="h-full rounded-full bg-[var(--uv-accent)]"
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <p className="mt-1 text-[11px] text-[var(--uv-text-muted)]">
                          {hit.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : null}

            <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-5">
              <h2 className="text-sm font-semibold text-[var(--uv-text)]">Your adviser</h2>
              {confidencePct != null ? (
                <p className="mt-2 text-sm text-[var(--uv-text-muted)]">
                  Model confidence is {confidencePct}%. Your tax adviser reviewed this
                  classification before it was released to you.
                </p>
              ) : (
                <p className="mt-2 text-sm text-[var(--uv-text-muted)]">
                  This classification was reviewed by your tax adviser before release.
                </p>
              )}

              {detail.review_reason || detail.evidence_needed ? (
                <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">
                  {detail.review_reason ? <p>{detail.review_reason}</p> : null}
                  {detail.evidence_needed ? (
                    <p className={detail.review_reason ? "mt-2" : ""}>
                      Evidence needed: {categoryLabel(detail.evidence_needed)}
                    </p>
                  ) : null}
                </div>
              ) : null}

              {detail.flagged_for_adviser ? (
                <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">
                  Flagged for your adviser
                  {detail.flag_message ? `: ${detail.flag_message}` : "."}
                </p>
              ) : null}

              <button
                type="button"
                onClick={() => {
                  setFlagMessage("");
                  setFlagOpen(true);
                }}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-amber-500/30 px-3 py-2 text-sm text-amber-300 transition hover:bg-amber-500/10"
              >
                <Flag className="h-4 w-4" />
                {detail.flagged_for_adviser ? "Update flag" : "Flag for adviser"}
              </button>
            </section>

            {(detail.taxonomy_version || detail.rulebook_version || detail.model_version) && (
              <p className="text-[11px] leading-relaxed text-[var(--uv-text-muted)]">
                {[
                  detail.taxonomy_version ? `Taxonomy ${detail.taxonomy_version}` : null,
                  detail.rulebook_version ? `Rules ${detail.rulebook_version}` : null,
                  detail.model_version ? `Model ${detail.model_version}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
          </aside>
        </div>
      ) : null}

      {flagOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-[var(--uv-text)]">Flag for adviser</h3>
            <p className="mt-1 text-sm text-[var(--uv-text-muted)]">
              Tell your tax adviser why this classification needs another look.
            </p>
            <textarea
              value={flagMessage}
              onChange={(event) => setFlagMessage(event.target.value)}
              rows={4}
              placeholder="Optional note…"
              className="mt-4 w-full rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)] px-3 py-2 text-sm text-[var(--uv-text)] outline-none focus:border-[var(--uv-accent)]/50"
            />
            {flagMutation.isError ? (
              <p className="mt-2 text-sm text-red-400">{(flagMutation.error as Error).message}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setFlagOpen(false)}
                className="rounded-lg px-4 py-2 text-sm text-[var(--uv-text-muted)] hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={flagMutation.isPending}
                onClick={() => flagMutation.mutate(flagMessage.trim())}
                className="rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)] disabled:opacity-50"
              >
                {flagMutation.isPending ? "Sending…" : "Send flag"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </UserViewShell>
  );
}
