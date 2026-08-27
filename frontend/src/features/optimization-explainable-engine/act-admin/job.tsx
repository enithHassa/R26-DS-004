import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";

import { getActAdminJob, retryActAdminJob } from "./api";

export function ActAdminJobPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<Awaited<ReturnType<typeof getActAdminJob>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!jobId) return;
    try {
      const next = await getActAdminJob(jobId);
      setJob(next);
      if (next.status === "extracted") {
        void navigate("/optimization-explainable-engine/act-admin", { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load job.");
    }
  }, [jobId, navigate]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Extract job</h2>
        <p className="text-sm text-muted-foreground">Job {jobId}</p>
      </div>
      {job ? (
        <div className="space-y-1 rounded-md border p-4 text-sm">
          <p>
            Status: <strong>{job.status}</strong>
          </p>
          {job.source_doc_id ? <p>source_doc_id: {job.source_doc_id}</p> : null}
          {job.entity_count != null ? <p>entities: {job.entity_count}</p> : null}
          {job.error ? (
            <p className="text-destructive" role="alert">
              {job.error}
            </p>
          ) : null}
        </div>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {job?.status === "failed" ||
        job?.status === "ingesting" ||
        job?.status === "extracting" ||
        job?.status === "uploaded" ? (
          <Button
            type="button"
            onClick={() => {
              void retryActAdminJob(jobId).then(() => {
                void navigate("/optimization-explainable-engine/act-admin");
              });
            }}
          >
            Retry extract
          </Button>
        ) : null}
        {job?.status === "extracted" && job.source_doc_id ? (
          <Button type="button" asChild>
            <Link to={`/optimization-explainable-engine/act-admin/review/${job.source_doc_id}`}>
              Open review
            </Link>
          </Button>
        ) : null}
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/act-admin">Back to queue</Link>
        </Button>
      </div>
    </div>
  );
}
