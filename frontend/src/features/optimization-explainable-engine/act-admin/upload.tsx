import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { startActAdminExtract, uploadActAdminPdf } from "./api";

export function ActAdminUploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function onUpload(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const upload = await uploadActAdminPdf(file);

      if (upload.case === "pending_review") {
        setInfo(
          upload.message ||
            "This PDF is already waiting in review. Open it from the queue.",
        );
        void navigate("/optimization-explainable-engine/act-admin");
        return;
      }

      if (upload.case === "in_flight") {
        setInfo(upload.message || "Extraction is already running for this PDF.");
        void navigate("/optimization-explainable-engine/act-admin");
        return;
      }

      if (upload.case === "prior_failed") {
        setInfo(upload.message || "A previous extract failed — retry from the queue.");
        void navigate("/optimization-explainable-engine/act-admin");
        return;
      }

      const jobId = upload.job_id ?? upload.job?.id;
      if (!jobId) {
        setError(upload.message || "Upload did not create a job.");
        return;
      }

      await startActAdminExtract(jobId);
      setInfo("Upload accepted. Extract is running — track progress on the review queue.");
      void navigate("/optimization-explainable-engine/act-admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Add New Act</h2>
        <p className="text-sm text-muted-foreground">
          Upload an Inland Revenue Act PDF. Extraction runs in the background — you return to the
          review queue immediately and can open review when the Act appears under Ready to review.
        </p>
      </div>
      <form className="space-y-4 rounded-xl border bg-card p-5" onSubmit={(e) => void onUpload(e)}>
        <div className="space-y-2">
          <Label htmlFor="oe-act-admin-pdf">Inland Revenue Act PDF</Label>
          <Input
            id="oe-act-admin-pdf"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        {info ? <p className="text-sm text-muted-foreground">{info}</p> : null}
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || !file}>
            {busy ? "Uploading…" : "Upload and extract"}
          </Button>
          <Button type="button" variant="outline" asChild>
            <Link to="/optimization-explainable-engine/act-admin">Back to queue</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
