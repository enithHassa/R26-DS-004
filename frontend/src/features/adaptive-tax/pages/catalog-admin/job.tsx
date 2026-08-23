import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";

import {
  deleteCatalogAdminJob,
  getCatalogAdminJob,
  retryCatalogAdminExtract,
  startCatalogAdminExtract,
} from "./api";

export function CatalogAdminJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const jobQuery = useQuery({
    queryKey: ["catalog-admin", "job", jobId],
    queryFn: () => getCatalogAdminJob(jobId as string),
    enabled: Boolean(jobId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "extracting" ? 2000 : false,
  });
  const job = jobQuery.data;

  async function onRetry(): Promise<void> {
    if (!jobId) return;
    await retryCatalogAdminExtract(jobId);
    await jobQuery.refetch();
  }

  async function onExtract(): Promise<void> {
    if (!jobId) return;
    await startCatalogAdminExtract(jobId);
    await jobQuery.refetch();
  }

  async function onDelete(): Promise<void> {
    if (!jobId) return;
    await deleteCatalogAdminJob(jobId);
    void navigate("/adaptive-tax/catalog-admin");
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Extract job</h2>
      {jobQuery.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {jobQuery.error instanceof Error ? jobQuery.error.message : "Job not found."}
        </p>
      ) : jobQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading job…</p>
      ) : job ? (
        <div className="space-y-3">
          <dl className="space-y-1 text-sm">
            <div>
              <dt className="inline text-muted-foreground">Status · </dt>
              <dd className="inline font-medium">{job.status}</dd>
            </div>
            <div>
              <dt className="inline text-muted-foreground">File · </dt>
              <dd className="inline">{job.original_filename || "—"}</dd>
            </div>
            <div>
              <dt className="inline text-muted-foreground">source_doc_id · </dt>
              <dd className="inline font-mono text-xs">{job.source_doc_id || "(unset)"}</dd>
            </div>
            <div>
              <dt className="inline text-muted-foreground">Text hash · </dt>
              <dd className="inline break-all font-mono text-xs">{job.text_sha256 || "—"}</dd>
            </div>
            {job.included_count != null ? (
              <div>
                <dt className="inline text-muted-foreground">Included rows · </dt>
                <dd className="inline">{job.included_count}</dd>
              </div>
            ) : null}
            {job.error ? (
              <div>
                <dt className="inline text-muted-foreground">Error · </dt>
                <dd className="inline text-destructive">{job.error}</dd>
              </div>
            ) : null}
          </dl>
          {job.status === "extracting" ? (
            <p className="text-sm text-muted-foreground">
              extract_proposal is running (Pass 1 / Pass 2 / quote gate). This page
              polls until it finishes. proposed/ is not written until the full run
              succeeds.
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {job.status === "uploaded" ? (
              <Button type="button" onClick={() => void onExtract()}>
                Start extract
              </Button>
            ) : null}
            {job.status === "failed" ? (
              <>
                <Button type="button" onClick={() => void onRetry()}>
                  Retry
                </Button>
                <Button type="button" variant="outline" onClick={() => void onDelete()}>
                  Delete
                </Button>
              </>
            ) : null}
            {job.status === "extracted" && (job.review_path || job.source_doc_id) ? (
              <Button type="button" asChild>
                <Link
                  to={
                    job.review_path ||
                    `/adaptive-tax/catalog-admin/review/${job.source_doc_id}`
                  }
                >
                  Open review
                </Link>
              </Button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Job <code className="text-xs">{jobId || "(missing)"}</code>.
        </p>
      )}
      <Link
        className="text-sm text-primary underline-offset-4 hover:underline"
        to="/adaptive-tax/catalog-admin"
      >
        Back to queue
      </Link>
    </div>
  );
}
