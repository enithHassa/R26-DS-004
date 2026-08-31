import { useCallback, useEffect, useState } from "react";

import {
  addIncomeDoc,
  listIncomeDocs,
  MAX_FILES_PER_SLOT,
  MAX_INCOME_DOC_BYTES,
  removeIncomeDoc,
  subscribeIncomeDocsChanges,
  type IncomeDocFile,
} from "./store";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `idoc-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

export function useIncomeDocsRevision(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => subscribeIncomeDocsChanges(() => setTick((n) => n + 1)), []);
  return tick;
}

export function useIncomeDocSlot(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  categoryId: string,
  slotId: string,
) {
  const [files, setFiles] = useState<IncomeDocFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setFiles(listIncomeDocs(profileId, assessmentYear, categoryId, slotId));
  }, [profileId, assessmentYear, categoryId, slotId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => subscribeIncomeDocsChanges(reload), [reload]);

  const addFiles = useCallback(
    async (incoming: FileList | File[]) => {
      if (!profileId || !assessmentYear) {
        setError("Select a taxpayer profile before uploading.");
        return;
      }
      setError(null);
      let current = files;
      for (const file of Array.from(incoming)) {
        if (current.length >= MAX_FILES_PER_SLOT) {
          setError(`You can attach up to ${MAX_FILES_PER_SLOT} files per document type.`);
          break;
        }
        if (file.size > MAX_INCOME_DOC_BYTES) {
          setError(`${file.name} is larger than 2 MB.`);
          continue;
        }
        const allowed = file.type.startsWith("image/") || file.type === "application/pdf";
        if (!allowed) {
          setError(`${file.name} must be an image or PDF.`);
          continue;
        }
        try {
          const dataUrl = await readFileAsDataUrl(file);
          current = addIncomeDoc(profileId, assessmentYear, categoryId, slotId, {
            id: newId(),
            fileName: file.name,
            mimeType: file.type || "application/octet-stream",
            dataUrl,
            uploadedAt: new Date().toISOString(),
          });
          setFiles(current);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Could not save the file.";
          setError(message);
        }
      }
    },
    [assessmentYear, categoryId, files, profileId, slotId],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      if (!profileId || !assessmentYear) return;
      setError(null);
      setFiles(removeIncomeDoc(profileId, assessmentYear, categoryId, slotId, fileId));
    },
    [assessmentYear, categoryId, profileId, slotId],
  );

  return { files, error, addFiles, removeFile };
}
