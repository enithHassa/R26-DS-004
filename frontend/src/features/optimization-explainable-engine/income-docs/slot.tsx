import { useEffect, useState } from "react";
import { FileImage, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { IncomeDocFile } from "./store";
import { useIncomeDocSlot } from "./use-income-docs";

type Mode = "upload" | "auditor";
type Surface = "default" | "trp";

function isImage(file: IncomeDocFile): boolean {
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

function Preview({ file, onClose }: { file: IncomeDocFile; onClose: () => void }) {
  const image = isImage(file);
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
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
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
            <iframe title={file.fileName} src={objectUrl} className="h-[75vh] w-full rounded bg-white" />
          ) : (
            <p className="text-sm text-muted-foreground">Opening…</p>
          )}
        </div>
      </div>
    </div>
  );
}

export function IncomeDocSlotRow({
  profileId,
  assessmentYear,
  categoryId,
  slotId,
  label,
  hint,
  mode,
  surface = "default",
}: {
  profileId: string | null | undefined;
  assessmentYear: string;
  categoryId: string;
  slotId: string;
  label: string;
  hint: string;
  mode: Mode;
  surface?: Surface;
}) {
  const { files, error, addFiles, removeFile } = useIncomeDocSlot(
    profileId,
    assessmentYear,
    categoryId,
    slotId,
  );
  const canUpload = mode === "upload" && Boolean(profileId);
  const [preview, setPreview] = useState<IncomeDocFile | null>(null);
  const loaded = files.length > 0;
  const isTrp = surface === "trp";

  const uploadInput = canUpload ? (
    <label className={isTrp ? "trp-income-docs-upload" : "mt-2 inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-3 py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-primary/10"}>
      <Upload className="h-3.5 w-3.5" size={14} aria-hidden />
      Add document
      <input
        type="file"
        accept="image/*,application/pdf"
        multiple
        className="sr-only"
        onChange={(e) => {
          const chosen = e.target.files;
          if (chosen && chosen.length > 0) void addFiles(chosen);
          e.target.value = "";
        }}
      />
    </label>
  ) : null;

  if (isTrp) {
    return (
      <div className={cn("trp-income-docs-slot", loaded && "is-loaded")}>
        <div className="trp-income-docs-slot-top">
          <div>
            <p className="trp-income-docs-slot-label">{label}</p>
            <p className="trp-income-docs-slot-hint">{hint}</p>
          </div>
          <span className={cn("trp-income-docs-slot-status", loaded && "is-ready")}>
            {loaded ? `${files.length} loaded` : "No file yet"}
          </span>
        </div>

        {error ? (
          <p className="trp-income-docs-error" role="alert">
            {error}
          </p>
        ) : null}

        {loaded ? (
          <ul className="trp-income-docs-files">
            {files.map((file) => (
              <li key={file.id} className="trp-income-docs-file">
                <button
                  type="button"
                  className="trp-income-docs-thumb"
                  onClick={() => setPreview(file)}
                  aria-label={`View ${file.fileName}`}
                >
                  {isImage(file) ? (
                    <img src={file.dataUrl} alt="" />
                  ) : (
                    <FileImage size={16} aria-hidden />
                  )}
                </button>
                <div className="trp-income-docs-file-meta">
                  <p className="trp-income-docs-file-name">{file.fileName}</p>
                  <button
                    type="button"
                    className="trp-income-docs-file-view"
                    onClick={() => setPreview(file)}
                  >
                    View
                  </button>
                </div>
                {canUpload ? (
                  <button
                    type="button"
                    className="trp-income-docs-remove"
                    onClick={() => removeFile(file.id)}
                    aria-label={`Remove ${file.fileName}`}
                  >
                    <X size={14} />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {uploadInput}

        {mode === "auditor" && !profileId ? (
          <p className="trp-income-docs-slot-hint" style={{ marginTop: 8 }}>
            Lock a taxpayer to load their uploaded documents.
          </p>
        ) : null}

        {preview ? <Preview file={preview} onClose={() => setPreview(null)} /> : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border p-3 transition-colors",
        loaded
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-border/80 bg-background/80",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{label}</p>
          <p className="text-[11px] text-muted-foreground">{hint}</p>
        </div>
        {loaded ? (
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
            {files.length} loaded
          </span>
        ) : (
          <span className="rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground">
            No file yet
          </span>
        )}
      </div>

      {error ? (
        <p className="mt-2 text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <ul className="mt-2 space-y-2">
        {files.map((file) => (
          <li
            key={file.id}
            className="flex items-start gap-2 rounded-lg border bg-background p-2 shadow-sm"
          >
            <button
              type="button"
              className="shrink-0"
              onClick={() => setPreview(file)}
              aria-label={`View ${file.fileName}`}
            >
              {isImage(file) ? (
                <img src={file.dataUrl} alt="" className="h-12 w-12 rounded-md object-cover" />
              ) : (
                <span className="flex h-12 w-12 items-center justify-center rounded-md border bg-muted/40">
                  <FileImage className="h-4 w-4 text-muted-foreground" aria-hidden />
                </span>
              )}
            </button>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">{file.fileName}</p>
              <button
                type="button"
                className="text-[11px] font-medium text-primary underline underline-offset-2"
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
        ))}
      </ul>

      {uploadInput}

      {mode === "auditor" && !profileId ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Lock a taxpayer to load their uploaded documents.
        </p>
      ) : null}

      {preview ? <Preview file={preview} onClose={() => setPreview(null)} /> : null}
    </div>
  );
}
