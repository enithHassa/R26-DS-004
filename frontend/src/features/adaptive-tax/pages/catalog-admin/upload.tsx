import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  refreshCatalogAdminHashes,
  startCatalogAdminExtract,
  treatCatalogAdminAsNewSource,
  uploadCatalogAdminPdf,
  type DuplicateCheckResponse,
} from "./api";

function actLabel(result: DuplicateCheckResponse): string {
  return (
    result.act_identity?.label ||
    (result.act_identity?.act_no
      ? `Act No. ${result.act_identity.act_no} of ${result.act_identity.act_year}`
      : result.filename || "this PDF")
  );
}

export function CatalogAdminUploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<DuplicateCheckResponse | null>(null);

  async function onRefreshIndex(): Promise<void> {
    setRefreshing(true);
    setError(null);
    setInfo(null);
    try {
      const body = await refreshCatalogAdminHashes();
      setInfo(
        body.path_errors && body.path_errors.length > 0
          ? `Hash index rebuilt (${body.document_count ?? 0} docs). Warnings: ${body.path_errors.join("; ")}`
          : `Hash index rebuilt (${body.document_count ?? 0} docs).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Index refresh failed.");
    } finally {
      setRefreshing(false);
    }
  }

  async function onUploadAndExtract(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    setBlocked(null);
    try {
      let upload = await uploadCatalogAdminPdf(file);

      if (upload.case === "b" && upload.review_path) {
        setBlocked(upload);
        setInfo(
          `${actLabel(upload)} is already waiting in review. Open that queue item instead of extracting again.`,
        );
        return;
      }
      if (upload.case === "b2" && upload.job_id) {
        setBlocked(upload);
        setInfo("Extraction is already running for this PDF.");
        return;
      }
      if (upload.case === "prior_failed" && upload.job_id) {
        setBlocked(upload);
        setInfo("A previous extract failed for this PDF — retry that job.");
        return;
      }

      if ((upload.case === "a" || upload.case === "d") && upload.job_id) {
        setInfo(
          upload.case === "a"
            ? `${actLabel(upload)} looks like an Act already in the catalog (${upload.matched_source_doc_id}). Starting a new draft extract for review — promote will show if caps already match live data.`
            : `Possible re-scan of ${upload.matched_source_doc_id}. Extracting as a new draft for review.`,
        );
        upload = await treatCatalogAdminAsNewSource(upload.job_id);
      }

      const jobId = upload.job_id;
      if (!jobId) {
        setError(upload.message || "Upload did not create an extract job.");
        return;
      }

      await startCatalogAdminExtract(jobId);
      void navigate(`/adaptive-tax/catalog-admin/jobs/${jobId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload or extract failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Add New Act</h2>
        <p className="text-sm text-muted-foreground">
          Upload an Inland Revenue Act PDF and run LLM extract. You review reliefs and
          rates on the next screen; promote shows whether caps already match what is live.
        </p>
      </div>

      <form className="space-y-4 rounded-xl border bg-card p-5 shadow-sm" onSubmit={(e) => void onUploadAndExtract(e)}>
        <div className="space-y-2">
          <Label htmlFor="catalog-admin-pdf">Inland Revenue Act PDF</Label>
          <Input
            id="catalog-admin-pdf"
            type="file"
            accept="application/pdf,.pdf"
            disabled={busy}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button type="submit" disabled={busy || !file}>
          {busy ? "Uploading and starting extract…" : "Upload and extract"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Extract runs in the background (GPT). Poll the job page, then open review when
          finished. Same PDF twice is OK for a demo — duplicate overlap is checked at promote.
        </p>
      </form>

      {info ? (
        <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-950 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-100" role="status">
          {info}
        </p>
      ) : null}

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {blocked ? (
        <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
          <p className="text-sm">{blocked.message}</p>
          <div className="flex flex-wrap gap-2">
            {blocked.review_path ? (
              <Button type="button" asChild>
                <Link to={blocked.review_path}>Open review</Link>
              </Button>
            ) : null}
            {blocked.job_id ? (
              <Button type="button" asChild variant="secondary">
                <Link to={`/adaptive-tax/catalog-admin/jobs/${blocked.job_id}`}>Open job</Link>
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      <details className="rounded-md border px-4 py-3 text-sm text-muted-foreground">
        <summary className="cursor-pointer font-medium text-foreground">Advanced (optional)</summary>
        <div className="mt-3 space-y-2">
          <p>
            Rebuild the hash index used behind the scenes for duplicate detection. Only
            needed if uploads behave oddly after manual file changes on disk.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={refreshing}
            onClick={() => void onRefreshIndex()}
          >
            {refreshing ? "Refreshing…" : "Refresh corpus hash index"}
          </Button>
        </div>
      </details>
    </div>
  );
}
