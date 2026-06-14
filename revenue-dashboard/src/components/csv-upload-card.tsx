import { useCallback, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Download, FileSpreadsheet, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  description: string;
  sampleHref: string;
  sampleFileName: string;
  acceptedHint: string;
  fileName?: string | null;
  uploadedAt?: string | null;
  error?: string | null;
  onUpload: (file: File) => Promise<void>;
  onClear?: () => void;
};

export function CsvUploadCard({
  title,
  description,
  sampleHref,
  sampleFileName,
  acceptedHint,
  fileName,
  uploadedAt,
  error,
  onUpload,
  onClear,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        return;
      }
      setLoading(true);
      try {
        await onUpload(file);
      } finally {
        setLoading(false);
      }
    },
    [onUpload],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  return (
    <Card className="border-[var(--revenue-teal)]/20 bg-gradient-to-br from-white to-[var(--revenue-teal-light)]/40">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base text-[var(--revenue-slate)]">{title}</CardTitle>
            <CardDescription className="mt-1 max-w-xl">{description}</CardDescription>
          </div>
          <a
            href={sampleHref}
            download={sampleFileName}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--revenue-teal)]/30 bg-white px-3 py-1.5 text-xs font-medium text-[var(--revenue-teal)] transition hover:bg-[var(--revenue-teal-light)]"
          >
            <Download className="h-3.5 w-3.5" />
            Sample CSV
          </a>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 transition",
            dragOver
              ? "border-[var(--revenue-teal)] bg-[var(--revenue-teal-light)]"
              : "border-slate-200 bg-white/80 hover:border-[var(--revenue-teal)]/50",
            loading && "pointer-events-none opacity-60",
          )}
        >
          <Upload className="mb-2 h-8 w-8 text-[var(--revenue-teal)]" />
          <p className="text-sm font-medium text-[var(--revenue-slate)]">
            {loading ? "Processing…" : "Drop CSV here or click to browse"}
          </p>
          <p className="mt-1 text-xs text-[var(--revenue-muted)]">{acceptedHint}</p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
              e.target.value = "";
            }}
          />
        </div>

        {fileName ? (
          <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50/80 px-3 py-2 text-sm">
            <div className="flex items-center gap-2 text-emerald-900">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span className="flex items-center gap-1">
                <FileSpreadsheet className="h-3.5 w-3.5" />
                {fileName}
                {uploadedAt ? (
                  <span className="text-xs text-emerald-700">
                    · {new Date(uploadedAt).toLocaleString()}
                  </span>
                ) : null}
              </span>
            </div>
            {onClear ? (
              <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={onClear}>
                <X className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
