import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

import { getCatalogAdminQueue, type CatalogAdminQueueResponse } from "./api";

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

function titleFromSourceId(sid: string): string {
  const match = sid.match(/^ird-amend-(\d{4})-(\d+)/i);
  if (match) return `Act No. ${Number(match[2])} of ${match[1]}`;
  return sid;
}

function jobStatusLabel(status: string): string {
  if (status === "uploaded") return "Waiting to extract";
  if (status === "extracting") return "Extracting now";
  if (status === "paused_rescan") return "Waiting for your decision";
  if (status === "failed") return "Extract failed";
  return status.replaceAll("_", " ");
}

export function CatalogAdminQueuePage() {
  const queueQuery = useQuery({
    queryKey: ["catalog-admin", "queue"],
    queryFn: getCatalogAdminQueue,
    retry: false,
  });
  const data = queueQuery.data;
  const pending = data?.proposals ?? [];
  const processing = data?.in_flight_jobs ?? [];
  const failed = data?.failed_jobs ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Review queue</h2>
          <p className="max-w-xl text-sm text-muted-foreground">
            Acts you have uploaded. Open a finished extract to classify rows and
            promote. If extract failed, retry that job — do not upload the same
            PDF again.
          </p>
        </div>
        <Button type="button" asChild>
          <Link to="/adaptive-tax/catalog-admin/upload">Add New Act</Link>
        </Button>
      </div>

      {queueQuery.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {queueQuery.error instanceof Error
            ? queueQuery.error.message
            : "Could not load queue."}
        </p>
      ) : queueQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading queue…</p>
      ) : (
        <div className="space-y-6">
          <QueueSection
            title="Ready to review"
            count={pending.length}
            hint="Extraction finished. These are waiting for a human to classify and approve."
            empty="Nothing waiting for review."
          >
            {pending.map((row) => (
              <ProposalCard key={row.source_doc_id} row={row} />
            ))}
          </QueueSection>

          <QueueSection
            title="Still processing"
            count={processing.length}
            hint="Uploaded, but not finished extracting yet — not ready to review."
            empty="Nothing is extracting right now."
          >
            {processing.map((row) => (
              <JobCard
                key={row.id}
                title={row.act_label || displayPdfName(row.original_filename) || "Act PDF"}
                filename={row.original_filename}
                when={row.created_at}
                status={jobStatusLabel(row.status)}
                href={row.job_path || `/adaptive-tax/catalog-admin/jobs/${row.id}`}
                action="Open job"
              />
            ))}
          </QueueSection>

          <QueueSection
            title="Could not extract"
            count={failed.length}
            hint="Open the job and retry. A new upload of the same file is not the path."
            empty="No failed extracts."
          >
            {failed.map((row) => (
              <JobCard
                key={row.id}
                title={row.act_label || displayPdfName(row.original_filename) || "Act PDF"}
                filename={row.original_filename}
                when={row.created_at}
                status={row.error || "Extract failed"}
                href={row.job_path || `/adaptive-tax/catalog-admin/jobs/${row.id}`}
                action="Retry job"
                destructive
              />
            ))}
          </QueueSection>
        </div>
      )}
    </div>
  );
}

function QueueSection({
  title,
  count,
  hint,
  empty,
  children,
}: {
  title: string;
  count: number;
  hint: string;
  empty: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold">
          {title}
          <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {count}
          </span>
        </h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      {count ? (
        <div className="grid gap-3">{children}</div>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
          {empty}
        </p>
      )}
    </section>
  );
}

function ProposalCard({
  row,
}: {
  row: CatalogAdminQueueResponse["proposals"][number];
}) {
  const title = row.act_title?.trim() || titleFromSourceId(row.source_doc_id);
  const file = displayPdfName(row.pdf_file_name);
  const href =
    row.review_path || `/adaptive-tax/catalog-admin/review/${row.source_doc_id}`;
  const promoted = Boolean(row.promotion_status);

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 p-4">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          <p className="text-xs text-muted-foreground">
            {row.extracted_at ? `Extracted ${formatWhen(row.extracted_at)}` : "Extracted"}
            {row.included_count != null ? ` · ${row.included_count} rows to review` : ""}
            {promoted ? ` · ${row.promotion_status}` : ""}
          </p>
          {file ? (
            <p className="text-xs text-muted-foreground">{file}</p>
          ) : null}
        </div>
        <Button type="button" size="sm" asChild>
          <Link to={href}>Review</Link>
        </Button>
      </CardHeader>
    </Card>
  );
}

function JobCard({
  title,
  filename,
  when,
  status,
  href,
  action,
  destructive,
}: {
  title: string;
  filename?: string;
  when?: string;
  status: string;
  href: string;
  action: string;
  destructive?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 p-4">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          <p className={destructive ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
            {status}
            {when ? ` · ${formatWhen(when)}` : ""}
          </p>
          {filename ? (
            <p className="text-xs text-muted-foreground">{displayPdfName(filename)}</p>
          ) : null}
        </div>
        <Button type="button" size="sm" variant="outline" asChild>
          <Link to={href}>{action}</Link>
        </Button>
      </CardHeader>
    </Card>
  );
}
