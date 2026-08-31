import { useEffect, useState } from "react";
import { FileImage, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";

import { reliefRequiresReceipt } from "./needs-receipt";
import { useReliefEvidence } from "./use-relief-evidence";
import type { ReliefEvidenceFile } from "./store";
import type { ReliefEntry } from "../types";

type SlotMode = "upload" | "auditor";

type ReliefEvidenceSlotProps = {
  profileId: string | null | undefined;
  assessmentYear: string;
  compareGroupId: string;
  displayName: string;
  autoApplied?: boolean;
  inputKind?: string;
  mode: SlotMode;
};

function isImageEvidence(file: ReliefEvidenceFile): boolean {
  if (file.mimeType.startsWith("image/")) return true;
  if (file.dataUrl.startsWith("data:image/")) return true;
  return /\.(png|jpe?g|gif|webp|bmp)$/i.test(file.fileName);
}

function dataUrlToObjectUrl(dataUrl: string): string {
  const comma = dataUrl.indexOf(",");
  const header = comma >= 0 ? dataUrl.slice(0, comma) : "";
  const payload = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  const mime = /data:([^;]+)/.exec(header)?.[1] ?? "application/octet-stream";
  const binary = atob(payload);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

function EvidencePreview({
  file,
  onClose,
}: {
  file: ReliefEvidenceFile;
  onClose: () => void;
}) {
  const image = isImageEvidence(file);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    const url = dataUrlToObjectUrl(file.dataUrl);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file.dataUrl]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={file.fileName}
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border bg-background shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b px-4 py-2">
          <p className="truncate text-sm font-medium">{file.fileName}</p>
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="min-h-[50vh] flex-1 overflow-auto bg-muted/40 p-3">
          {image ? (
            <img
              src={objectUrl ?? file.dataUrl}
              alt={file.fileName}
              className="mx-auto max-h-[75vh] w-auto max-w-full rounded object-contain"
            />
          ) : objectUrl ? (
            <iframe
              title={file.fileName}
              src={objectUrl}
              className="h-[75vh] w-full rounded bg-white"
            />
          ) : (
            <p className="text-sm text-muted-foreground">Opening document…</p>
          )}
        </div>
      </div>
    </div>
  );
}

export function ReliefEvidenceSlot({
  profileId,
  assessmentYear,
  compareGroupId,
  displayName,
  autoApplied = false,
  inputKind,
  mode,
}: ReliefEvidenceSlotProps) {
  const requiresReceipt = reliefRequiresReceipt({
    compare_group_id: compareGroupId,
    display_name: displayName,
    auto_applied: autoApplied,
    input_kind: inputKind ?? "amount",
  });
  const { files, error, addFiles, removeFile } = useReliefEvidence(
    profileId,
    assessmentYear,
    compareGroupId,
    displayName,
  );
  const canUpload = mode === "upload" && Boolean(profileId);
  const [preview, setPreview] = useState<ReliefEvidenceFile | null>(null);

  if (!requiresReceipt) {
    return (
      <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        Personal relief is applied by statute — no receipt is required.
      </div>
    );
  }

  if (mode === "auditor" && !profileId) {
    return (
      <div className="rounded-md border p-3 text-xs text-muted-foreground">
        Select a taxpayer in the workspace to load receipts they uploaded for this year.
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium">Supporting documents</p>
          <p className="text-[11px] text-muted-foreground">
            {files.length > 0
              ? `${files.length} file${files.length === 1 ? "" : "s"} uploaded for this relief`
              : mode === "auditor"
                ? "This taxpayer has not uploaded a receipt for this relief yet."
                : "Upload a photo or PDF of the receipt for this year of assessment."}
          </p>
        </div>
        {files.length > 0 ? (
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-300">
            Receipt loaded
          </span>
        ) : (
          <span className="rounded-full border px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            No image yet
          </span>
        )}
      </div>

      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <ul className="space-y-2">
        {files.map((file) => {
          const image = isImageEvidence(file);
          return (
            <li
              key={file.id}
              className="flex items-start gap-3 rounded-md border bg-muted/30 p-2"
            >
              <button
                type="button"
                className="shrink-0"
                onClick={() => setPreview(file)}
                aria-label={`View ${file.fileName}`}
              >
                {image ? (
                  <img
                    src={file.dataUrl}
                    alt=""
                    className="h-16 w-16 rounded object-cover"
                  />
                ) : (
                  <span className="flex h-16 w-16 items-center justify-center rounded border bg-background">
                    <FileImage className="h-5 w-5 text-muted-foreground" aria-hidden />
                  </span>
                )}
              </button>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{file.fileName}</p>
                <p className="text-[11px] text-muted-foreground">
                  {new Date(file.uploadedAt).toLocaleString()}
                </p>
                <button
                  type="button"
                  className="text-[11px] underline"
                  onClick={() => setPreview(file)}
                >
                  View
                </button>
              </div>
              {canUpload ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => removeFile(file.id)}
                  aria-label={`Remove ${file.fileName}`}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>

      {canUpload ? (
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-xs">
          <Upload className="h-3.5 w-3.5" aria-hidden />
          Add receipt
          <input
            type="file"
            accept="image/*,application/pdf"
            multiple
            className="sr-only"
            onChange={(event) => {
              const chosen = event.target.files;
              if (chosen && chosen.length > 0) void addFiles(chosen);
              event.target.value = "";
            }}
          />
        </label>
      ) : null}

      {preview ? <EvidencePreview file={preview} onClose={() => setPreview(null)} /> : null}
    </div>
  );
}

export function ReliefEvidenceFromEntry({
  profileId,
  assessmentYear,
  entry,
  mode,
}: {
  profileId: string | null | undefined;
  assessmentYear: string;
  entry: Pick<
    ReliefEntry,
    "compare_group_id" | "display_name" | "auto_applied" | "input_kind"
  >;
  mode: SlotMode;
}) {
  return (
    <ReliefEvidenceSlot
      profileId={profileId}
      assessmentYear={assessmentYear}
      compareGroupId={entry.compare_group_id}
      displayName={entry.display_name}
      autoApplied={entry.auto_applied}
      inputKind={entry.input_kind}
      mode={mode}
    />
  );
}
