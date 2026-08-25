import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  FileText,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  deleteCatalogAdminJob,
  getCatalogAdminJob,
  retryCatalogAdminExtract,
  startCatalogAdminExtract,
  type CatalogAdminJob,
} from "./api";

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function displayPdfName(name?: string | null): string {
  if (!name) return "";
  return name.replace(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i,
    "",
  );
}

function jobTitle(job: CatalogAdminJob): string {
  return job.act_identity?.label?.trim() || displayPdfName(job.original_filename) || "Act PDF";
}

function jobStatusMeta(status: string): {
  label: string;
  tone: "muted" | "info" | "success" | "warning" | "danger";
  hint: string;
} {
  switch (status) {
    case "uploaded":
      return {
        label: "Waiting to extract",
        tone: "info",
        hint: "The PDF passed duplicate checks. Start extract when you are ready.",
      };
    case "extracting":
      return {
        label: "Extracting now",
        tone: "warning",
        hint: "GPT is reading schedules, reliefs, and rate bands. This page refreshes every few seconds.",
      };
    case "extracted":
      return {
        label: "Extract complete",
        tone: "success",
        hint: "Staging files are ready. Open review to classify rows and promote.",
      };
    case "failed":
      return {
        label: "Extract failed",
        tone: "danger",
        hint: "Retry uses the same uploaded PDF. Do not upload the file again.",
      };
    case "paused_rescan":
      return {
        label: "Paused for rescan",
        tone: "warning",
        hint: "Resolve the duplicate/rescan decision on this job before extract continues.",
      };
    default:
      return {
        label: status.replaceAll("_", " "),
        tone: "muted",
        hint: "",
      };
  }
}

function StatusBadge({ status }: { status: string }) {
  const meta = jobStatusMeta(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        meta.tone === "success" && "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100",
        meta.tone === "warning" && "bg-amber-100 text-amber-950 dark:bg-amber-950/50 dark:text-amber-100",
        meta.tone === "danger" && "bg-destructive/10 text-destructive",
        meta.tone === "info" && "bg-sky-100 text-sky-950 dark:bg-sky-950/50 dark:text-sky-100",
        meta.tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      {status === "extracting" ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      ) : status === "extracted" ? (
        <CheckCircle2 className="size-3.5" aria-hidden />
      ) : status === "failed" ? (
        <XCircle className="size-3.5" aria-hidden />
      ) : (
        <Sparkles className="size-3.5" aria-hidden />
      )}
      {meta.label}
    </span>
  );
}

function ExtractProgress({ active }: { active: boolean }) {
  const steps = [
    "Read PDF text and tables",
    "Extract reliefs and rate bands",
    "Quote gate and staging write",
  ];
  return (
    <ol className="grid gap-2 sm:grid-cols-3">
      {steps.map((step, index) => (
        <li
          key={step}
          className={cn(
            "rounded-lg border px-3 py-2 text-xs",
            active
              ? "border-amber-300/80 bg-amber-50/80 dark:border-amber-800 dark:bg-amber-950/30"
              : "border-border bg-muted/30 text-muted-foreground",
          )}
        >
          <span className="mb-1 block font-medium text-foreground/80">Step {index + 1}</span>
          {step}
          {active ? (
            <span className="mt-1.5 flex items-center gap-1 text-amber-900 dark:text-amber-100">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              RunningΓÇª
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

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
  const meta = job ? jobStatusMeta(job.status) : null;

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
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/adaptive-tax/catalog-admin">
            <ArrowLeft className="mr-1.5 size-4" aria-hidden />
            Back to queue
          </Link>
        </Button>
      </div>

      <div className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight">Extract job</h2>
        <p className="text-sm text-muted-foreground">
          Live status for one uploaded Act PDF ΓÇö from duplicate check through GPT extract.
        </p>
      </div>

      {jobQuery.isError ? (
        <Card className="border-destructive/40">
          <CardContent className="p-5 text-sm text-destructive" role="alert">
            {jobQuery.error instanceof Error ? jobQuery.error.message : "Job not found."}
          </CardContent>
        </Card>
      ) : jobQuery.isLoading ? (
        <Card>
          <CardContent className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Loading jobΓÇª
          </CardContent>
        </Card>
      ) : job ? (
        <div className="space-y-4">
          <Card>
            <CardHeader className="space-y-3 pb-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <FileText className="size-4 shrink-0" aria-hidden />
                    <CardTitle className="text-lg">{jobTitle(job)}</CardTitle>
                  </div>
                  <StatusBadge status={job.status} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {job.status === "uploaded" ? (
                    <Button type="button" onClick={() => void onExtract()}>
                      Start extract
                    </Button>
                  ) : null}
                  {job.status === "failed" ? (
                    <>
                      <Button type="button" onClick={() => void onRetry()}>
                        Retry extract
                      </Button>
                      <Button type="button" variant="outline" onClick={() => void onDelete()}>
                        Delete job
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
              {meta?.hint ? <p className="text-sm text-muted-foreground">{meta.hint}</p> : null}
            </CardHeader>
            <CardContent className="space-y-4 pt-0">
              {job.status === "extracting" ? <ExtractProgress active /> : null}

              <dl className="grid gap-3 rounded-lg border bg-muted/20 p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    PDF file
                  </dt>
                  <dd className="mt-1 break-all">{displayPdfName(job.original_filename) || "ΓÇö"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Uploaded
                  </dt>
                  <dd className="mt-1">
                    {formatWhen(job.created_at) || "ΓÇö"}
                    {job.uploaded_by ? ` ┬╖ ${job.uploaded_by}` : ""}
                  </dd>
                </div>
                {job.extract_started_at ? (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Extract started
                    </dt>
                    <dd className="mt-1">
                      {formatWhen(job.extract_started_at)}
                      {job.extract_started_by ? ` ┬╖ ${job.extract_started_by}` : ""}
                    </dd>
                  </div>
                ) : null}
                {job.extract_finished_at ? (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Extract finished
                    </dt>
                    <dd className="mt-1">{formatWhen(job.extract_finished_at)}</dd>
                  </div>
                ) : null}
                {job.included_count != null ? (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Rows extracted
                    </dt>
                    <dd className="mt-1 font-medium">
                      {job.included_count}
                      {job.row_count != null && job.row_count !== job.included_count
                        ? ` of ${job.row_count} total`
                        : ""}
                    </dd>
                  </div>
                ) : null}
                {job.error ? (
                  <div className="sm:col-span-2">
                    <dt className="text-xs font-medium uppercase tracking-wide text-destructive">
                      Error
                    </dt>
                    <dd className="mt-1 text-destructive">{job.error}</dd>
                  </div>
                ) : null}
              </dl>

              <details className="rounded-lg border bg-card px-4 py-3 text-sm">
                <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
                  Technical ids and hashes
                </summary>
                <dl className="mt-3 space-y-2 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Job id</dt>
                    <dd className="font-mono break-all">{job.id}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">source_doc_id</dt>
                    <dd className="font-mono break-all">{job.source_doc_id || "(unset)"}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Text hash</dt>
                    <dd className="font-mono break-all">{job.text_sha256 || "ΓÇö"}</dd>
                  </div>
                  {job.pdf_sha256 ? (
                    <div>
                      <dt className="text-muted-foreground">PDF hash</dt>
                      <dd className="font-mono break-all">{job.pdf_sha256}</dd>
                    </div>
                  ) : null}
                </dl>
              </details>
            </CardContent>
          </Card>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Job <code className="text-xs">{jobId || "(missing)"}</code> not found.
        </p>
      )}
    </div>
  );
}
