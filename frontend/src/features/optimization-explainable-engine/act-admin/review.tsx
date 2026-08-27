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
  RateBandReviewSection,
  LiveCatalogPreviewPanel,
  ReliefReviewCard,
  ReviewProgressStrip,
  YearKindBanner,
} from "./review-ui";

export function ActAdminReviewPage() {
  const { sourceDocId = "" } = useParams();
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [previewYear, setPreviewYear] = useState("");

  const reviewQuery = useQuery({
    queryKey: ["oe-act-admin", "review", sourceDocId],
    queryFn: () => getActAdminReview(sourceDocId),
    enabled: Boolean(sourceDocId),
    retry: false,
  });

  const review = reviewQuery.data;
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
  const latestPreviewYear = previewYears[previewYears.length - 1] || "";
  const effectivePreviewYear =
    previewYear && previewYears.includes(previewYear) ? previewYear : latestPreviewYear;

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
    },
  });

  const reliefs = useMemo(() => review?.reliefs ?? [], [review]);
  const rates = useMemo(() => review?.rates ?? [], [review]);
  const reliefCounts = useMemo(() => countReviewRows(reliefs), [reliefs]);
  const rateCounts = useMemo(() => countReviewRows(rates), [rates]);
  const reliefSections = useMemo(() => groupReliefsBySection(reliefs), [reliefs]);
  const rateSections = useMemo(() => groupRatesBySection(rates), [rates]);
  const needsNewYearChoice = [...reliefs, ...rates].some(
    (row) => String(row.year_kind_suggested ?? "") === "NEW_YEAR",
  );
  const yearKindSample = [...reliefs, ...rates].find(
    (row) => String(row.year_kind_suggested ?? "") === "NEW_YEAR",
  );

  function applyReview(updated: typeof review, resetYear = false): void {
    queryClient.setQueryData(["oe-act-admin", "review", sourceDocId], updated);
    if (resetYear) setPreviewYear("");
    void queryClient.invalidateQueries({ queryKey: ["oe-act-admin", "catalog-preview-years"] });
    void queryClient.invalidateQueries({ queryKey: ["oe-act-admin", "catalog-preview-year"] });
  }

  async function patchRow(entryId: string, body: Record<string, unknown>): Promise<void> {
    setBusyId(entryId);
    try {
      const updated = await patchActAdminRow(sourceDocId, entryId, body);
      applyReview(updated, "year_kind" in body);
    } finally {
      setBusyId(null);
    }
  }

  async function patchYearKindRows(entryIds: string[], kind: YearKind): Promise<void> {
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
    setBusyId("year-kind");
    try {
      const updated = await setActAdminYearKindAll(sourceDocId, kind);
      applyReview(updated, true);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">{review?.act_title ?? "Review extract"}</h2>
        <p className="text-sm text-muted-foreground">
          {review?.entity_count ?? 0} individual income tax rows to review before activate.
        </p>
      </div>

      {reviewQuery.isError ? (
        <p className="text-sm text-destructive">Could not load draft review.</p>
      ) : null}

      {review ? (
        <>
          <ReviewProgressStrip relief={reliefCounts} rates={rateCounts} />
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
          />
        </>
      ) : null}

      {reliefSections.length ? (
        <section className="space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-semibold">Reliefs extracted from this Act</h3>
            <p className="text-sm text-muted-foreground">
              Skim the interview preview and Act quote, then Quick approve each row you accept.
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
              One row per band — compare against the Act, then Quick approve each row.
            </p>
          </div>
          {rateSections.map(([section, rows]) => (
            <RateBandReviewSection
              key={section}
              title={section}
              rows={rows}
              busyId={busyId}
              onApprove={(entryId) => {
                const entity = rows.find((row) => String(row.entry_id) === entryId);
                const body: Record<string, unknown> = { review_status: "accepted" };
                if (entity?.included === false) body.included = true;
                void patchRow(entryId, body);
              }}
              onReject={(entryId) => void patchRow(entryId, { review_status: "rejected" })}
              onSetYearKind={(kind) =>
                void patchYearKindRows(
                  rows.map((row) => String(row.entry_id ?? "")),
                  kind,
                )
              }
            />
          ))}
        </section>
      ) : null}

      <LiveCatalogPreviewPanel
        preview={catalogPreviewForYearQuery.data}
        selectedYear={effectivePreviewYear}
        onYearChange={setPreviewYear}
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={!review?.activate_allowed || activate.isPending}
          onClick={() => activate.mutate()}
        >
          Activate into year views
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/act-admin">Back to queue</Link>
        </Button>
      </div>

      {review?.ingest_note ? (
        <p className="text-sm text-muted-foreground">{review.ingest_note}</p>
      ) : null}
      {!review?.activate_allowed && review?.activate_block_reason ? (
        <p className="text-sm text-muted-foreground">{review.activate_block_reason}</p>
      ) : null}

      {activate.isSuccess ? (
        <p className="text-sm text-muted-foreground">
          Activated. Interview year views and RAG catalog are updated — open Reliefs or Compare in
          the main OE Engine flow.
        </p>
      ) : null}
      {activate.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {activate.error instanceof Error ? activate.error.message : "Activation failed"}
        </p>
      ) : null}
    </div>
  );
}
