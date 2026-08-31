import { useCallback, useEffect, useState } from "react";

import {
  addReliefEvidence,
  listReliefEvidence,
  MAX_EVIDENCE_BYTES,
  MAX_FILES_PER_RELIEF,
  removeReliefEvidence,
  subscribeEvidenceChanges,
  type ReliefEvidenceFile,
} from "./store";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `ev-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

/** Bumps when any receipt is added or removed so lists can refresh badges. */
export function useEvidenceRevision(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => subscribeEvidenceChanges(() => setTick((n) => n + 1)), []);
  return tick;
}

export function useReliefEvidence(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  compareGroupId: string | null | undefined,
  displayName?: string | null,
) {
  const [files, setFiles] = useState<ReliefEvidenceFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setFiles(listReliefEvidence(profileId, assessmentYear, compareGroupId, displayName));
  }, [profileId, assessmentYear, compareGroupId, displayName]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => subscribeEvidenceChanges(reload), [reload]);

  const addFiles = useCallback(
    async (incoming: FileList | File[]) => {
      if (!profileId || !assessmentYear || !compareGroupId) {
        setError("Select a taxpayer profile before uploading receipts.");
        return;
      }
      setError(null);
      const list = Array.from(incoming);
      for (const file of list) {
        if (files.length >= MAX_FILES_PER_RELIEF) {
          setError(`You can attach up to ${MAX_FILES_PER_RELIEF} files per relief.`);
          break;
        }
        if (file.size > MAX_EVIDENCE_BYTES) {
          setError(`${file.name} is larger than 2 MB. Compress the image and try again.`);
          continue;
        }
        const allowed = file.type.startsWith("image/") || file.type === "application/pdf";
        if (!allowed) {
          setError(`${file.name} is not an image or PDF.`);
          continue;
        }
        try {
          const dataUrl = await readFileAsDataUrl(file);
          const saved = addReliefEvidence(
            profileId,
            assessmentYear,
            compareGroupId,
            {
              id: newId(),
              fileName: file.name,
              mimeType: file.type || "application/octet-stream",
              dataUrl,
              uploadedAt: new Date().toISOString(),
            },
            displayName,
          );
          setFiles(saved);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Could not save the file.";
          setError(
            message.toLowerCase().includes("quota")
              ? "Browser storage is full. Remove an older receipt and try again."
              : message,
          );
        }
      }
    },
    [assessmentYear, compareGroupId, displayName, files.length, profileId],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      if (!profileId || !assessmentYear || !compareGroupId) return;
      setError(null);
      setFiles(
        removeReliefEvidence(
          profileId,
          assessmentYear,
          compareGroupId,
          fileId,
          displayName,
        ),
      );
    },
    [assessmentYear, compareGroupId, displayName, profileId],
  );

  return { files, error, addFiles, removeFile };
}
