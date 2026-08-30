import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import {
  activateActAdminDraft,
  getActAdminCatalogPreview,
  getActAdminReview,
  patchActAdminRow,
  postActAdminImpactPreview,
  setActAdminYearKindAll,
  type YearKind,
} from "./api";
import {
  AboutUploadCard,
  countReviewRows,
  groupReliefsBySection,
  groupRatesBySection,
  isIndividualEngineRow,
  RateBandReviewSection,
  LiveCatalogPreviewPanel,
  RejectedNoiseSection,
  ReliefReviewCard,
  ReviewProgressStrip,
  YearKindBanner,
} from "./review-ui";

export function ActAdminReviewPage() {
  const { sourceDocId = "" } = useParams();
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [previewYear, setPreviewYear] = useState("");
  const [alreadyInSystemNotice, setAlreadyInSystemNotice] = useState<string | null>(null);

  const reviewQuery = useQuery({
    queryKey: ["oe-act-admin", "review", sourceDocId],
    queryFn: () => getActAdminReview(sourceDocId),
    enabled: Boolean(sourceDocId),
    retry: false,
  });

  const review = reviewQuery.data;
  // Corpus skip (same PDF hash) is not a live year-view promote. Only a promoted
  // run locks review as already-in-system.
  const alreadyInSystem = Boolean(review?.already_in_system);
  const yearKindStamp = useMemo(() => {
    const rows = [...(review?.reliefs ?? []), ...(review?.rates ?? [])];
    return rows.map((row) => `${row.entry_id}:${row.year_kind ?? ""}`).join("|");
  }, [review]);

  const previewYearsQuery = useQuery({
    queryKey: [
      "oe-act-admin",
      "catalog-preview-years",
      sourceDocId,
      review?.accepted_count,
      yearKindStamp,
    ],
    queryFn: () => getActAdminCatalogPreview(sourceDocId),
    enabled: Boolean(sourceDocId) && Boolean(review),
    retry: false,
  });

  const previewYears = previewYearsQuery.data?.preview_years ?? [];
  const actTargetYear = String(
    review?.year_context?.new_assessment_year ??
      review?.reliefs?.[0]?.derived_assessment_year ??
      review?.rates?.[0]?.derived_assessment_year ??
      "",
  ).trim();
  const preferredPreviewYear = (() => {
    if (actTargetYear && previewYears.includes(actTargetYear)) {
      return actTargetYear;
    }
    return previewYears[previewYears.length - 1] || "";
  })();
  const effectivePreviewYear =
    previewYear && previewYears.includes(previewYear) ? previewYear : preferredPreviewYear;

  const catalogPreviewForYearQuery = useQuery({
    queryKey: [
      "oe-act-admin",
      "catalog-preview-year",
      sourceDocId,
      effectivePreviewYear,
      review?.accepted_count,
      yearKindStamp,
    ],
    queryFn: () => getActAdminCatalogPreview(sourceDocId, effectivePreviewYear),
    enabled: Boolean(sourceDocId) && Boolean(effectivePreviewYear),
    retry: false,
    staleTime: 0,
  });

  const activate = useMutation({
    mutationFn: async () => {
      const impact = await postActAdminImpactPreview(sourceDocId);
      if (!impact.activate_allowed) {
        throw new Error(impact.activate_block_reason || "Resolve pending rows before activate.");
      }
      return activateActAdminDraft(sourceDocId, impact.fingerprint);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["optimization-explainable-engine"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-explainable-engine", "years"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-explainable-engine", "compare"] });
      void queryClient.invalidateQueries({ queryKey: ["oe-act-admin"] });
      // TaxWise taxpayer OE shares the same /years + reliefs catalog after activate.
      void queryClient.invalidateQueries({ queryKey: ["taxwise-oe"] });
    },
  });

  const reliefs = useMemo(() => review?.reliefs ?? [], [review]);
  const rates = useMemo(() => review?.rates ?? [], [review]);
  const reliefCounts = useMemo(() => countReviewRows(reliefs), [reliefs]);
  const rateCounts = useMemo(() => countReviewRows(rates), [rates]);
  const reliefSections = useMemo(() => groupReliefsBySection(reliefs), [reliefs]);
  const rateSections = useMemo(() => groupRatesBySection(rates), [rates]);
  const rejectedNoise = useMemo(() => review?.rejected_noise ?? [], [review]);
  const needsNewYearChoice =
    !alreadyInSystem &&
    [...reliefs, ...rates].some(
      (row) =>
        isIndividualEngineRow(row) && String(row.year_kind_suggested ?? "") === "NEW_YEAR",
    );
  const yearKindSample = [...reliefs, ...rates].find(
    (row) =>
      isIndividualEngineRow(row) && String(row.year_kind_suggested ?? "") === "NEW_YEAR",
  );

  function applyReview(updated: typeof review, resetYear = false): void {
    queryClient.setQueryData(["oe-act-admin", "review", sourceDocId], updated);
    if (resetYear) setPreviewYear("");
    void queryClient.invalidateQueries({ queryKey: ["oe-act-admin", "catalog-preview-years"] });
    void queryClient.invalidateQueries({ queryKey: ["oe-act-admin", "catalog-preview-year"] });
  }

  async function patchRow(entryId: string, body: Record<string, unknown>): Promise<void> {
    if (alreadyInSystem) {
      const row = [...reliefs, ...rates].find((entity) => String(entity.entry_id ?? "") === entryId);
      const status = String(row?.review_status ?? "pending");
      // Keep prior accept/reject locked; allow deciding brand-new pending rows only.
      if (status === "accepted" || status === "rejected") return;
    }
    setBusyId(entryId);
    try {
      const updated = await patchActAdminRow(sourceDocId, entryId, body);
      applyReview(updated, "year_kind" in body);
    } finally {
      setBusyId(null);
    }
  }

  async function patchYearKindRows(entryIds: string[], kind: YearKind): Promise<void> {
    if (alreadyInSystem) return;
    setBusyId("year-kind");
    try {
      let updated = review;
      for (const entryId of entryIds) {
        if (!entryId) continue;
        updated = await patchActAdminRow(sourceDocId, entryId, { year_kind: kind });
      }
      if (updated) applyReview(updated, true);
    } finally {
      setBusyId(null);
    }
  }

  async function applyYearKindAll(kind: YearKind): Promise<void> {
    if (alreadyInSystem) return;
    setBusyId("year-kind");
    try {
      const updated = await setActAdminYearKindAll(sourceDocId, kind);
      applyReview(updated, true);
    } finally {
      setBusyId(null);
    }
  }

  function handleActivateClick(): void {
    if (alreadyInSystem) {
      window.alert(
        "This Act is already live in year views.",
      );
      return;
    }
    const ok = window.confirm(
      "Publish YA 2027/28 into live year views?\n\nTaxWise and auditor year pickers will show 2027/28 with the approved slabs and reliefs. Rejected rows stay out.",
    );
    if (!ok) return;
    setAlreadyInSystemNotice(null);
    activate.mutate();
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">{review?.act_title ?? "Review extract"}</h2>
        <p className="text-sm text-muted-foreground">
          {alreadyInSystem
            ? `${review?.entity_count ?? 0} rules already live in the catalog (read-only demo).`
            : `${review?.entity_count ?? 0} rows to review before activate — including entity/other rules you must Accept or Reject.`}
        </p>
      </div>

      {reviewQuery.isError ? (
        <p className="text-sm text-destructive">Could not load draft review.</p>
      ) : null}

      {review ? (
        <>
          <ReviewProgressStrip
            relief={reliefCounts}
            rates={rateCounts}
            rejectedNoise={rejectedNoise.length}
            alreadyInSystem={alreadyInSystem}
          />
          {needsNewYearChoice && yearKindSample ? (
            <YearKindBanner
              sample={yearKindSample}
              busy={busyId === "year-kind"}
              onApplyAll={(kind) => void applyYearKindAll(kind)}
            />
          ) : null}
          <AboutUploadCard
            actTitle={review.act_title}
            sourceDocId={review.source_doc_id}
            pdfFileName={review.pdf_file_name}
            extractedAt={review.extracted_at}
            entityCount={review.entity_count}
            extractedEntityCount={review.extracted_entity_count}
            outOfScopeCount={review.out_of_scope_count}
            note={review.note}
            alreadyInSystem={alreadyInSystem}
          />
        </>
      ) : null}

      {reliefSections.length ? (
        <section className="space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-semibold">Reliefs extracted from this Act</h3>
            <p className="text-sm text-muted-foreground">
              {alreadyInSystem
            ? "Approved rows match the live catalog (read-only). Previously rejected rows stay rejected and out of year views."
            : "Skim the interview preview and Act quote, then Quick approve each row you accept."}
            </p>
          </div>
          {reliefSections.map(([section, rows]) => (
            <div key={section} className="space-y-3">
              <h4 className="text-sm font-semibold">
                {section}
                <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                  {rows.length}
                </span>
              </h4>
              <div className="grid gap-4">
                {rows.map((entity) => {
                  const entryId = String(entity.entry_id ?? "");
                  const approveBody: Record<string, unknown> = { review_status: "accepted" };
                  if (entity.included === false) approveBody.included = true;
                  return (
                    <ReliefReviewCard
                      key={entryId}
                      entity={entity}
                      busy={busyId === entryId || busyId === "year-kind"}
                      readOnlyApproved={alreadyInSystem}
                      onQuickApprove={() => void patchRow(entryId, approveBody)}
                      onReject={() => void patchRow(entryId, { review_status: "rejected" })}
                      onSaveQuestions={(fields) => void patchRow(entryId, fields)}
                      onSetYearKind={(kind) => void patchRow(entryId, { year_kind: kind })}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {rateSections.length ? (
        <section className="space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-semibold">Tax rates</h3>
            <p className="text-sm text-muted-foreground">
              {alreadyInSystem
                ? "Approved bands are read-only. Rejected bands stay out of year views."
                : "Review the exact Act quote on each band, then Quick approve or Reject. Entity / other taxpayer rates also need Accept or Reject — they stay out of year views."}
            </p>
          </div>
          {rateSections.map(([section, rows]) => (
            <RateBandReviewSection
              key={section}
              title={section}
              rows={rows}
              busyId={busyId}
              readOnlyApproved={alreadyInSystem}
              onApprove={(entryId) => {
                const entity = rows.find((row) => String(row.entry_id) === entryId);
                const body: Record<string, unknown> = { review_status: "accepted" };
                if (entity?.included === false) body.included = true;
                void patchRow(entryId, body);
              }}
              onReject={(entryId) => void patchRow(entryId, { review_status: "rejected" })}
              onSetYearKind={(kind) =>
                void patchYearKindRows(
                  rows
                    .filter((row) => isIndividualEngineRow(row))
                    .map((row) => String(row.entry_id ?? "")),
                  kind,
                )
              }
            />
          ))}
        </section>
      ) : null}

      <RejectedNoiseSection rows={rejectedNoise} />

      <LiveCatalogPreviewPanel
        preview={catalogPreviewForYearQuery.data}
        selectedYear={effectivePreviewYear}
        onYearChange={setPreviewYear}
        alreadyInSystem={alreadyInSystem}
      />

      {activate.isPending ? (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm" role="status">
          Publishing YA 2027/28 into year views…
        </p>
      ) : null}
      {activate.isSuccess ? (
        <p
          className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-950"
          role="status"
        >
          Done. YA 2027/28 is live for auditor OE Engine and TaxWise. Open Interview or TaxWise and
          pick 2027/28 — or use Past Acts to hide it after the demo.
        </p>
      ) : null}
      {activate.isError ? (
        <p
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {activate.error instanceof Error ? activate.error.message : "Activation failed"}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={!alreadyInSystem && (!review?.activate_allowed || activate.isPending)}
          aria-disabled={alreadyInSystem || undefined}
          title={
            alreadyInSystem
              ? "This document is already extracted and in the system"
              : undefined
          }
          onClick={handleActivateClick}
        >
          {activate.isPending
            ? "Activating…"
            : activate.isSuccess || alreadyInSystem
              ? "Activated"
              : "Activate into year views"}
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/act-admin">Back to queue</Link>
        </Button>
      </div>

      {alreadyInSystemNotice ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950" role="status">
          {alreadyInSystemNotice}
        </p>
      ) : null}

      {review?.ingest_note && !alreadyInSystem ? (
        <p className="text-sm text-muted-foreground">{review.ingest_note}</p>
      ) : null}
      {alreadyInSystem ? (
        <p className="text-sm text-muted-foreground">
          This PDF is already extracted and live in the engine. Activate stays available to click for
          the demo message only — it does not change year views again.
        </p>
      ) : null}
      {!alreadyInSystem ? (
        <p className="text-sm text-muted-foreground">
          Rejected rows never enter year views. After Activate, new assessment years and approved
          reliefs/rates are available in auditor OE Engine and TaxWise user views.
        </p>
      ) : null}
      {!alreadyInSystem && !review?.activate_allowed && review?.activate_block_reason ? (
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{review.activate_block_reason}</p>
          {(review.blocking_issues?.length ?? 0) > 0 ? (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-destructive">
              {review.blocking_issues.map((issue) => (
                <li key={`${issue.entry_id}-${issue.code}`}>{issue.message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
