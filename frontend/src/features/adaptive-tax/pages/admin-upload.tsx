import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileUp, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  extractAmendment,
  uploadAmendment,
  type AmendmentUploadResponse,
} from "../api";

export function AdaptiveTaxAdminUploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<AmendmentUploadResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleUpload(): Promise<void> {
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    setIsUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const resp = await uploadAmendment(file);
      setUpload(resp);
      setSuccess(
        resp.duplicate_hash_warning
          ? `Uploaded. Warning: ${resp.duplicate_hash_warning}`
          : `Uploaded ${resp.original_filename}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleExtract(): Promise<void> {
    if (!upload?.id) {
      setError("Upload a PDF before extracting.");
      return;
    }
    setIsExtracting(true);
    setError(null);
    setSuccess(null);
    try {
      const resp = await extractAmendment(upload.id);
      setSuccess(`Extracted ${resp.rule_count} rule(s) via ${resp.mode}.`);
      navigate(`/adaptive-tax/admin/review/${upload.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed.");
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Amendment upload</h1>
        <p className="text-muted-foreground">
          Upload an Inland Revenue amendment PDF, run structured extraction, then
          review source quotes before approve/reject.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">PDF file</CardTitle>
          <CardDescription>
            Accepts Act PDFs such as No. 02/2025 or 11/2026. Extraction uses fixture
            or OpenAI depending on server{" "}
            <code className="rounded bg-muted px-1 text-xs">
              COMP_ADAPTIVE_TAX_EXTRACTION_MODE
            </code>
            .
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="amendment-pdf">Amendment PDF</Label>
            <Input
              id="amendment-pdf"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => {
                const next = event.target.files?.[0] ?? null;
                setFile(next);
                setUpload(null);
                setSuccess(null);
                setError(null);
              }}
            />
            {file ? (
              <p className="text-sm text-muted-foreground">
                Selected: <span className="text-foreground">{file.name}</span> (
                {(file.size / 1024).toFixed(1)} KB)
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleUpload()}
              disabled={!file || isUploading || isExtracting}
            >
              {isUploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileUp className="h-4 w-4" />
              )}
              Upload
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleExtract()}
              disabled={!upload?.id || isUploading || isExtracting}
            >
              {isExtracting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Extract
            </Button>
            {upload?.id ? (
              <Button type="button" variant="outline" asChild>
                <Link to={`/adaptive-tax/admin/review/${upload.id}`}>Open review</Link>
              </Button>
            ) : null}
          </div>

          {upload ? (
            <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
              <p>
                <span className="text-muted-foreground">Job ID:</span>{" "}
                <code className="text-xs">{upload.id}</code>
              </p>
              <p>
                <span className="text-muted-foreground">Hash:</span>{" "}
                <code className="text-xs">{upload.file_hash.slice(0, 16)}…</code>
              </p>
              <p>
                <span className="text-muted-foreground">Status:</span> {upload.status}
              </p>
            </div>
          ) : null}

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
