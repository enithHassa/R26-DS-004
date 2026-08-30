import { useCallback, useRef, useState } from "react";
import { FileUp, Upload, X } from "lucide-react";

import { submitDocumentToAuditor } from "@/features/transaction-semantic/api";
import { cn } from "@/lib/utils";

interface StatementUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profileId: string;
  taxYear?: string | null;
  onSubmitted?: () => void;
}

export function StatementUploadModal({
  open,
  onOpenChange,
  profileId,
  taxYear,
  onSubmitted,
}: StatementUploadModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const reset = useCallback(() => {
    setFile(null);
    setError(null);
    setSuccess(null);
    setIsDragging(false);
  }, []);

  function close(): void {
    reset();
    onOpenChange(false);
  }

  function pickFile(next: File | null): void {
    setError(null);
    setSuccess(null);
    setFile(next);
  }

  async function handleSend(): Promise<void> {
    if (!file) {
      setError("Choose a bank statement file first.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await submitDocumentToAuditor(file, profileId, taxYear);
      setSuccess(response.message);
      onSubmitted?.();
      window.setTimeout(() => close(), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="statement-upload-title"
        className="w-full max-w-lg rounded-2xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-6 shadow-2xl"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="statement-upload-title" className="text-lg font-semibold text-[var(--uv-text)]">
              Upload Statement
            </h2>
            <p className="mt-1 text-sm text-[var(--uv-text-muted)]">
              Send your bank statement to your tax adviser. They will extract, classify, and load
              it to your profile before transactions appear here.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded-lg p-1.5 text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-text)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div
          className={cn(
            "rounded-xl border-2 border-dashed p-8 text-center transition-colors",
            isDragging
              ? "border-[var(--uv-accent)] bg-[var(--uv-accent)]/10"
              : "border-[var(--uv-border)] bg-[var(--uv-bg)]/40",
          )}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            const dropped = event.dataTransfer.files?.[0] ?? null;
            pickFile(dropped);
          }}
        >
          <Upload className="mx-auto h-8 w-8 text-[var(--uv-accent)]" />
          <p className="mt-3 text-sm text-[var(--uv-text)]">
            Drag and drop your statement, or{" "}
            <button
              type="button"
              className="font-medium text-[var(--uv-accent)] underline-offset-2 hover:underline"
              onClick={() => inputRef.current?.click()}
            >
              choose a file
            </button>
          </p>
          <p className="mt-1 text-xs text-[var(--uv-text-muted)]">PDF or CSV bank statements</p>
          {file ? (
            <p className="mt-4 rounded-lg bg-white/5 px-3 py-2 text-sm text-[var(--uv-text)]">
              {file.name}
            </p>
          ) : null}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.csv,application/pdf,text/csv"
            className="hidden"
            onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
          />
        </div>

        {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}
        {success ? <p className="mt-3 text-sm text-emerald-400">{success}</p> : null}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            className="rounded-lg px-4 py-2 text-sm text-[var(--uv-text-muted)] transition hover:bg-white/5 hover:text-[var(--uv-text)]"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!file || isSubmitting}
            onClick={() => void handleSend()}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileUp className="h-4 w-4" />
            {isSubmitting ? "Sending…" : "Send to adviser"}
          </button>
        </div>
      </div>
    </div>
  );
}
