import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  getDocuments,
  getExtractFixtures,
  getMismatches,
  getReview,
  patchMismatchStatus,
  postFixtureApply,
  postGuideDisplayUpdate,
  postIngestExisting,
  postPromote,
  type ExtractFixtureRow,
  type ReviewResponse,
} from "../api";
import { yaDisplay } from "../format-lkr";

type TabId = "documents" | "act" | "guide" | "consolidated";

export function LoadNewActPage() {
  const [tab, setTab] = useState<TabId>("documents");
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Load new act</h2>
        <p className="text-sm text-muted-foreground">
          Protected admin upload runs quote-gated LLM extract, human review, impact
          preview, and activation. Fixture tools below remain $0 for development.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label="Load new act">
        <Button type="button" size="sm" asChild>
          <Link to="/optimization-explainable-engine/act-admin">Open Act admin</Link>
        </Button>
        {(
          [
            ["documents", "Documents"],
            ["act", "Act review"],
            ["guide", "Guide"],
            ["consolidated", "Consolidated"],
          ] as const
        ).map(([id, label]) => (
          <Button
            key={id}
            type="button"
            size="sm"
            variant={tab === id ? "default" : "outline"}
            onClick={() => setTab(id)}
          >
            {label}
          </Button>
        ))}
      </div>
      {tab === "documents" ? <DocumentsTab /> : null}
      {tab === "act" ? <ActReviewTab /> : null}
      {tab === "guide" ? <GuideTab /> : null}
      {tab === "consolidated" ? <ConsolidatedTab /> : null}
      <Button type="button" variant="outline" asChild>
        <Link to="/optimization-explainable-engine/home">Back to home</Link>
      </Button>
    </div>
  );
}

function DocumentsTab() {
  const docsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "documents"],
    queryFn: getDocuments,
    retry: false,
  });
  const ingest = useMutation({
    mutationFn: postIngestExisting,
  });
  const rows = docsQuery.data?.documents ?? [];
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Already ingested PDFs. Re-ingest is hash-skip ($0) when the file is
        unchanged. Uploading a new PDF would spend embedding budget — skip that
        until Phase 6.
      </p>
      {docsQuery.isError ? (
        <p className="text-sm text-destructive" role="alert">
          Could not list documents. Start the engine on port 8009.
        </p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((doc) => (
          <li key={doc.source_doc_id} className="rounded-md border p-3 text-sm">
            <p className="font-medium">{doc.title}</p>
            <p className="text-xs text-muted-foreground">
              {doc.source_doc_id} · {doc.tier} · {doc.chunk_count} chunks
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-2"
              disabled={ingest.isPending}
              onClick={() => ingest.mutate(doc.source_doc_id)}
            >
              Re-ingest
            </Button>
          </li>
        ))}
      </ul>
      {ingest.data ? (
        <p className="text-xs text-muted-foreground">
          {ingest.data.status} · usd {ingest.data.embedding_usd}{" "}
          {ingest.data.detail ? `· ${ingest.data.detail}` : ""}
        </p>
      ) : null}
      {ingest.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {ingest.error instanceof Error ? ingest.error.message : "Ingest failed"}
        </p>
      ) : null}
    </div>
  );
}

function useFixtures(tier: string) {
  const query = useQuery({
    queryKey: ["optimization-explainable-engine", "extract-fixtures"],
    queryFn: getExtractFixtures,
    retry: false,
  });
  const rows = useMemo(
    () => (query.data?.fixtures ?? []).filter((row) => row.tier === tier),
    [query.data, tier],
  );
  return { query, rows };
}

function FixturePicker({
  rows,
  value,
  onChange,
}: {
  rows: ExtractFixtureRow[];
  value: string;
  onChange: (sourceDocId: string) => void;
}) {
  return (
    <div className="max-w-md space-y-1">
      <Label htmlFor="oe-engine-fixture">Fixture extract</Label>
      <Select id="oe-engine-fixture" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select…</option>
        {rows.map((row) => (
          <option key={row.source_doc_id} value={row.source_doc_id}>
            {row.source_doc_id} ({row.entity_count} entities)
          </option>
        ))}
      </Select>
    </div>
  );
}

function EntityPreview({ review }: { review: ReviewResponse | undefined }) {
  if (!review) return null;
  return (
    <div className="space-y-2 rounded-md border p-3 text-xs">
      <p>
        tier={review.tier} · terminus={review.terminus} · promote_allowed=
        {review.promote_allowed ? "yes" : "no"}
      </p>
      <ul className="max-h-64 space-y-1 overflow-auto">
        {review.entities.map((entity, index) => (
          <li key={String(entity.entry_id ?? index)}>
            {String(entity.entity_kind ?? "entity")} ·{" "}
            {String(entity.compare_group_id ?? entity.entry_id ?? "")}
            {entity.cap_amount != null ? ` · cap ${String(entity.cap_amount)}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ActReviewTab() {
  const queryClient = useQueryClient();
  const { query, rows } = useFixtures("act");
  const [sourceDocId, setSourceDocId] = useState("oee-fixture-act-2025");
  const reviewQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "review", sourceDocId],
    queryFn: () => getReview(sourceDocId),
    enabled: Boolean(sourceDocId),
    retry: false,
  });
  const promote = useMutation({
    mutationFn: () =>
      postPromote(sourceDocId, reviewQuery.data?.extraction_run_id ?? null),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["optimization-explainable-engine"] });
    },
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Review a fixture Act extract, then promote into year views. Chunk coverage
        is required. Guide and Consolidated cannot use this button.
      </p>
      {query.isError ? (
        <p className="text-sm text-destructive">Could not load fixtures.</p>
      ) : null}
      <FixturePicker rows={rows} value={sourceDocId} onChange={setSourceDocId} />
      <EntityPreview review={reviewQuery.data} />
      {reviewQuery.data && !reviewQuery.data.promote_allowed ? (
        <p className="text-sm text-destructive">Promote is Act-only.</p>
      ) : null}
      <Button
        type="button"
        disabled={!reviewQuery.data?.promote_allowed || promote.isPending}
        onClick={() => promote.mutate()}
      >
        Promote into year views
      </Button>
      {promote.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {promote.error instanceof Error ? promote.error.message : "Promote failed"}
        </p>
      ) : null}
      {promote.isSuccess ? (
        <p className="text-sm text-muted-foreground">
          Promoted. Years / Reliefs / Result now read the compiled year views.
        </p>
      ) : null}
    </div>
  );
}

function GuideTab() {
  const queryClient = useQueryClient();
  const { rows } = useFixtures("guide");
  const [sourceDocId, setSourceDocId] = useState("oee-fixture-guide");
  const reviewQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "review", sourceDocId],
    queryFn: () => getReview(sourceDocId),
    enabled: Boolean(sourceDocId),
    retry: false,
  });
  const apply = useMutation({
    mutationFn: () => postFixtureApply("guide_extract.json"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["optimization-explainable-engine"] });
    },
  });
  const update = useMutation({
    mutationFn: () => postGuideDisplayUpdate(sourceDocId),
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Guide is display + help only. Update display accepts the current Guide JSON.
        There is no Promote — caps stay on Acts.
      </p>
      <FixturePicker rows={rows} value={sourceDocId} onChange={setSourceDocId} />
      <EntityPreview review={reviewQuery.data} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={() => apply.mutate()}>
          Load Guide fixture
        </Button>
        <Button type="button" onClick={() => update.mutate()} disabled={update.isPending}>
          Update display
        </Button>
      </div>
      <p className="text-xs font-medium text-muted-foreground">Promote is not available for Guide.</p>
      {update.isSuccess ? (
        <p className="text-sm text-muted-foreground">
          Display accepted ({update.data.review_status}). Reliefs labelled Guide will
          show this help text.
        </p>
      ) : null}
      {apply.isError || update.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {(apply.error || update.error) instanceof Error
            ? ((apply.error || update.error) as Error).message
            : "Guide update failed"}
        </p>
      ) : null}
    </div>
  );
}

function ConsolidatedTab() {
  const queryClient = useQueryClient();
  const { rows } = useFixtures("consolidated");
  const [sourceDocId, setSourceDocId] = useState("oee-fixture-consolidated");
  const reviewQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "review", sourceDocId],
    queryFn: () => getReview(sourceDocId),
    enabled: Boolean(sourceDocId),
    retry: false,
  });
  const flagsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "mismatches"],
    queryFn: getMismatches,
    retry: false,
  });
  const apply = useMutation({
    mutationFn: () => postFixtureApply("consolidated_facts.json"),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["optimization-explainable-engine", "mismatches"],
      });
    },
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      patchMismatchStatus(id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["optimization-explainable-engine", "mismatches"],
      });
    },
  });
  const flags = flagsQuery.data?.flags ?? [];
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Consolidated facts compare to year views. Flags never write year tables.
        There is no Promote.
      </p>
      <FixturePicker rows={rows} value={sourceDocId} onChange={setSourceDocId} />
      <EntityPreview review={reviewQuery.data} />
      <Button type="button" variant="outline" onClick={() => apply.mutate()}>
        Load Consolidated fixture
      </Button>
      <p className="text-xs font-medium text-muted-foreground">
        Promote is not available for Consolidated.
      </p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead className="bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Group</th>
              <th className="px-3 py-2 font-medium">Year</th>
              <th className="px-3 py-2 font-medium">Consolidated</th>
              <th className="px-3 py-2 font-medium">Act</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {flags.map((flag) => (
              <tr key={flag.id} className="border-t">
                <td className="px-3 py-2">{flag.compare_group_id}</td>
                <td className="px-3 py-2">{yaDisplay(flag.year)}</td>
                <td className="px-3 py-2">{flag.value_consolidated}</td>
                <td className="px-3 py-2">{flag.value_act ?? "—"}</td>
                <td className="px-3 py-2">{flag.status}</td>
                <td className="px-3 py-2">
                  {flag.status === "open" || flag.status === "escalated" ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setStatus.mutate({ id: flag.id, status: "dismissed" })}
                    >
                      Dismiss
                    </Button>
                  ) : null}
                  {flag.status === "open" ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setStatus.mutate({ id: flag.id, status: "escalated" })}
                    >
                      Escalate
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {flags.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No mismatch rows yet. Promote a fixture Act, then load the Consolidated
          fixture.
        </p>
      ) : null}
    </div>
  );
}
