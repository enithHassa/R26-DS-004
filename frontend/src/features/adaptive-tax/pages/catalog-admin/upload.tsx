import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  discardCatalogAdminJob,
  refreshCatalogAdminHashes,
  setCatalogAdminSourceDocId,
  startCatalogAdminExtract,
  treatCatalogAdminAsNewSource,
  uploadCatalogAdminPdf,
  type DuplicateCheckResponse,
} from "./api";

function Fingerprints({ result }: { result: DuplicateCheckResponse }) {
  return (
    <dl className="grid gap-1 text-xs text-muted-foreground">
      <div>
        <dt className="inline font-medium text-foreground">Text hash </dt>
        <dd className="inline break-all font-mono">{result.text_sha256 || "—"}</dd>
      </div>
      <div>
        <dt className="inline font-medium text-foreground">PDF bytes </dt>
        <dd className="inline break-all font-mono">{result.pdf_sha256 || "—"}</dd>
      </div>
      {result.act_identity?.label ? (
        <div>
          <dt className="inline font-medium text-foreground">Identity </dt>
          <dd className="inline">
            {result.act_identity.label} ({result.act_identity.source})
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

export function CatalogAdminUploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DuplicateCheckResponse | null>(null);
  const [sourceDocId, setSourceDocId] = useState("");

  async function onCheck(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await uploadCatalogAdminPdf(file);
      setResult(next);
      setSourceDocId(next.suggested_source_doc_id || "");
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Duplicate check failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onRefreshIndex(): Promise<void> {
    setRefreshing(true);
    setError(null);
    try {
      const body = await refreshCatalogAdminHashes();
      setError(
        body.path_errors && body.path_errors.length > 0
          ? `Index rebuilt (${body.document_count ?? 0} docs). Path warnings: ${body.path_errors.join("; ")}`
          : `Index rebuilt (${body.document_count ?? 0} docs).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Index refresh failed.");
    } finally {
      setRefreshing(false);
    }
  }

  async function onTreatAsNew(): Promise<void> {
    if (!result?.job_id) return;
    setBusy(true);
    setError(null);
    try {
      const next = await treatCatalogAdminAsNewSource(result.job_id);
      setResult(next);
      setSourceDocId(next.suggested_source_doc_id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not treat as a new source.");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel(): Promise<void> {
    if (!result?.job_id) {
      setResult(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await discardCatalogAdminJob(result.job_id);
      setResult(null);
      setSourceDocId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel.");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveSourceId(): Promise<void> {
    if (!result?.job_id) return;
    setBusy(true);
    setError(null);
    try {
      const job = await setCatalogAdminSourceDocId(result.job_id, sourceDocId.trim());
      setResult({
        ...result,
        suggested_source_doc_id: job.source_doc_id,
        job,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save source_doc_id.");
    } finally {
      setBusy(false);
    }
  }

  async function onExtract(): Promise<void> {
    if (!result?.job_id) return;
    setBusy(true);
    setError(null);
    try {
      if (sourceDocId.trim() && sourceDocId.trim() !== result.suggested_source_doc_id) {
        await setCatalogAdminSourceDocId(result.job_id, sourceDocId.trim());
      }
      await startCatalogAdminExtract(result.job_id);
      void navigate(`/adaptive-tax/catalog-admin/jobs/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start extract.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Add New Act</h2>
        <p className="text-sm text-muted-foreground">
          Cheap PDF text read and hash-first duplicate check — before any LLM
          extract. Filename is a fallback only. This does not write{" "}
          <code className="text-xs">corpus_manifest.json</code>.
        </p>
      </div>

      <form className="space-y-4" onSubmit={(e) => void onCheck(e)}>
        <div className="space-y-2">
          <Label htmlFor="catalog-admin-pdf">Inland Revenue Act PDF</Label>
          <Input
            id="catalog-admin-pdf"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>
            {busy ? "Checking…" : "Check for duplicates"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={refreshing}
            onClick={() => void onRefreshIndex()}
          >
            {refreshing ? "Refreshing index…" : "Refresh corpus hash index"}
          </Button>
        </div>
      </form>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-4 rounded-md border p-4">
          {result.index_stale || (result.warnings && result.warnings.length > 0) ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
              <p className="font-medium">Index warning — duplicate check still ran.</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {(result.warnings ?? []).map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="text-sm">{result.message}</p>
          <Fingerprints result={result} />

          {result.case === "b" && result.review_path ? (
            <Button type="button" asChild>
              <Link to={result.review_path}>Open review queue item</Link>
            </Button>
          ) : null}

          {(result.case === "b2" || result.case === "prior_failed") &&
          result.job_id ? (
            <Button type="button" asChild>
              <Link to={`/adaptive-tax/catalog-admin/jobs/${result.job_id}`}>
                Open existing job
              </Link>
            </Button>
          ) : null}

          {(result.case === "d" || result.case === "a") && result.job_id ? (
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => void onCancel()}>
                Cancel
              </Button>
              <Button type="button" disabled={busy} onClick={() => void onTreatAsNew()}>
                Treat as a new source (do not replace {result.matched_source_doc_id})
              </Button>
            </div>
          ) : null}

          {result.case === "a" && !result.job_id ? (
            <p className="text-sm text-amber-800 dark:text-amber-200">
              This duplicate result has no job yet. Click <strong>Check for duplicates</strong> again
              so Cancel / Treat as a new source can appear.
            </p>
          ) : null}

          {result.case === "none" && result.job_id ? (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="catalog-admin-source-id">source_doc_id (editable before extract)</Label>
                <Input
                  id="catalog-admin-source-id"
                  value={sourceDocId}
                  onChange={(e) => setSourceDocId(e.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" disabled={busy} onClick={() => void onSaveSourceId()}>
                  Save id
                </Button>
                <Button type="button" disabled={busy} onClick={() => void onExtract()}>
                  {busy ? "Starting…" : "Start extract"}
                </Button>
                <Button type="button" asChild variant="secondary">
                  <Link to={`/adaptive-tax/catalog-admin/jobs/${result.job_id}`}>Open job</Link>
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                Starts Phase 6 extract_proposal in the background (full quote gate,
                every section). Poll the job page — this button does not wait on OpenAI.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
