/**
 * Taxpayer supporting documents for reliefs, keyed by profile + year + relief.
 * Stored in the browser so TaxWise Profile and the auditor Interview share the
 * same origin without changing calculate / year views.
 */

import {
  canonicalEvidenceGroupId,
  canonicalEvidenceYear,
  evidenceGroupsMatch,
  evidenceYearKeys,
} from "./canonical-group";

export type ReliefEvidenceFile = {
  id: string;
  fileName: string;
  mimeType: string;
  dataUrl: string;
  uploadedAt: string;
};

type StoreShape = Record<
  string,
  Record<string, Record<string, ReliefEvidenceFile[]>>
>;

const STORAGE_KEY = "oe-relief-evidence-v1";
export const RELIEF_EVIDENCE_CHANGED = "oe-relief-evidence-changed";
const CHANNEL_NAME = "oe-relief-evidence";
export const MAX_EVIDENCE_BYTES = 2 * 1024 * 1024;
export const MAX_FILES_PER_RELIEF = 5;

let channel: BroadcastChannel | null = null;

function evidenceChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null;
  if (!channel) channel = new BroadcastChannel(CHANNEL_NAME);
  return channel;
}

function emptyStore(): StoreShape {
  return {};
}

function readStore(): StoreShape {
  if (typeof window === "undefined") return emptyStore();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as StoreShape;
    return parsed && typeof parsed === "object" ? parsed : emptyStore();
  } catch {
    return emptyStore();
  }
}

function writeStore(next: StoreShape): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

function emitChange(
  profileId: string,
  assessmentYear: string,
  compareGroupId: string,
): void {
  window.dispatchEvent(
    new CustomEvent(RELIEF_EVIDENCE_CHANGED, {
      detail: { profileId, assessmentYear, compareGroupId },
    }),
  );
  evidenceChannel()?.postMessage({
    type: "changed",
    profileId,
    assessmentYear,
    compareGroupId,
  });
}

export function subscribeEvidenceChanges(onChange: () => void): () => void {
  function onCustom() {
    onChange();
  }
  function onStorage(event: StorageEvent) {
    if (event.key && event.key !== STORAGE_KEY) return;
    onChange();
  }
  function onMessage() {
    onChange();
  }
  function onFocus() {
    onChange();
  }
  window.addEventListener(RELIEF_EVIDENCE_CHANGED, onCustom);
  window.addEventListener("storage", onStorage);
  window.addEventListener("focus", onFocus);
  const ch = evidenceChannel();
  ch?.addEventListener("message", onMessage);
  return () => {
    window.removeEventListener(RELIEF_EVIDENCE_CHANGED, onCustom);
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("focus", onFocus);
    ch?.removeEventListener("message", onMessage);
  };
}

function yearBuckets(
  store: StoreShape,
  profileId: string,
  assessmentYear: string,
): Record<string, ReliefEvidenceFile[]>[] {
  const wanted = new Set(evidenceYearKeys(assessmentYear));
  const byYear = store[profileId] ?? {};
  const buckets: Record<string, ReliefEvidenceFile[]>[] = [];
  for (const [year, groups] of Object.entries(byYear)) {
    const yearMatches = evidenceYearKeys(year).some((key) => wanted.has(key));
    if (yearMatches) buckets.push(groups);
  }
  return buckets;
}

function mergeFiles(items: ReliefEvidenceFile[]): ReliefEvidenceFile[] {
  const seen = new Set<string>();
  const merged: ReliefEvidenceFile[] = [];
  for (const file of items) {
    if (!file?.id || seen.has(file.id)) continue;
    seen.add(file.id);
    merged.push(file);
  }
  return merged.sort((a, b) => String(b.uploadedAt).localeCompare(String(a.uploadedAt)));
}

export function listReliefEvidence(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  compareGroupId: string | null | undefined,
  displayName?: string | null,
): ReliefEvidenceFile[] {
  if (!profileId || !assessmentYear || !compareGroupId) return [];
  const collected: ReliefEvidenceFile[] = [];
  for (const groups of yearBuckets(readStore(), profileId, assessmentYear)) {
    for (const [key, files] of Object.entries(groups)) {
      if (evidenceGroupsMatch(key, compareGroupId, displayName)) {
        collected.push(...(files ?? []));
      }
    }
  }
  return mergeFiles(collected);
}

export function countReliefEvidence(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  compareGroupId: string | null | undefined,
  displayName?: string | null,
): number {
  return listReliefEvidence(profileId, assessmentYear, compareGroupId, displayName).length;
}

function pruneOldestUntilWritable(store: StoreShape): void {
  const files: Array<{
    profileId: string;
    year: string;
    group: string;
    index: number;
    uploadedAt: string;
  }> = [];
  for (const [profileId, byYear] of Object.entries(store)) {
    for (const [year, groups] of Object.entries(byYear)) {
      for (const [group, list] of Object.entries(groups)) {
        list.forEach((file, index) => {
          files.push({
            profileId,
            year,
            group,
            index,
            uploadedAt: file.uploadedAt,
          });
        });
      }
    }
  }
  files.sort((a, b) => a.uploadedAt.localeCompare(b.uploadedAt));
  const drop = files[0];
  if (!drop) throw new Error("Browser storage is full.");
  const list = store[drop.profileId][drop.year][drop.group];
  list.splice(drop.index, 1);
}

function writeStoreResilient(store: StoreShape): void {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      writeStore(store);
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (!/quota|full/i.test(message) && !(err instanceof DOMException)) throw err;
      pruneOldestUntilWritable(store);
    }
  }
  writeStore(store);
}

export function addReliefEvidence(
  profileId: string,
  assessmentYear: string,
  compareGroupId: string,
  file: ReliefEvidenceFile,
  displayName?: string | null,
): ReliefEvidenceFile[] {
  const store = readStore();
  const year = canonicalEvidenceYear(assessmentYear);
  const group = canonicalEvidenceGroupId(compareGroupId);
  const existing = listReliefEvidence(profileId, assessmentYear, compareGroupId, displayName);
  const nextFiles = mergeFiles([...existing, file]).slice(0, MAX_FILES_PER_RELIEF);

  const byYear = store[profileId] ?? {};
  const byGroup = { ...(byYear[year] ?? {}) };
  for (const key of Object.keys(byGroup)) {
    if (key !== group && evidenceGroupsMatch(key, compareGroupId, displayName)) {
      delete byGroup[key];
    }
  }
  byGroup[group] = nextFiles;
  store[profileId] = {
    ...byYear,
    [year]: byGroup,
  };
  writeStoreResilient(store);
  emitChange(profileId, year, group);
  return nextFiles;
}

export function removeReliefEvidence(
  profileId: string,
  assessmentYear: string,
  compareGroupId: string,
  fileId: string,
  displayName?: string | null,
): ReliefEvidenceFile[] {
  const store = readStore();
  const year = canonicalEvidenceYear(assessmentYear);
  const group = canonicalEvidenceGroupId(compareGroupId);
  const nextFiles = listReliefEvidence(
    profileId,
    assessmentYear,
    compareGroupId,
    displayName,
  ).filter((item) => item.id !== fileId);

  const byYear = { ...(store[profileId] ?? {}) };
  for (const yearKey of Object.keys(byYear)) {
    if (!evidenceYearKeys(yearKey).some((key) => evidenceYearKeys(assessmentYear).includes(key))) {
      continue;
    }
    const groups = { ...byYear[yearKey] };
    for (const key of Object.keys(groups)) {
      if (evidenceGroupsMatch(key, compareGroupId, displayName)) {
        delete groups[key];
      }
    }
    if (canonicalEvidenceYear(yearKey) === year) {
      if (nextFiles.length > 0) groups[group] = nextFiles;
      else delete groups[group];
    }
    if (Object.keys(groups).length > 0) byYear[yearKey] = groups;
    else delete byYear[yearKey];
  }
  if (nextFiles.length > 0) {
    const groups = { ...(byYear[year] ?? {}) };
    groups[group] = nextFiles;
    byYear[year] = groups;
  }
  store[profileId] = byYear;
  writeStoreResilient(store);
  emitChange(profileId, year, group);
  return nextFiles;
}

export function exportProfileEvidence(
  profileId: string,
): Record<string, Record<string, ReliefEvidenceFile[]>> {
  const byYear = readStore()[profileId] ?? {};
  const out: Record<string, Record<string, ReliefEvidenceFile[]>> = {};
  for (const [year, groups] of Object.entries(byYear)) {
    const canonYear = canonicalEvidenceYear(year);
    const mergedGroups = { ...(out[canonYear] ?? {}) };
    for (const [group, files] of Object.entries(groups)) {
      const canonGroup = canonicalEvidenceGroupId(group);
      const combined = mergeFiles([...(mergedGroups[canonGroup] ?? []), ...(files ?? [])]);
      if (combined.length > 0) mergedGroups[canonGroup] = combined;
      else delete mergedGroups[canonGroup];
    }
    if (Object.keys(mergedGroups).length > 0) out[canonYear] = mergedGroups;
    else delete out[canonYear];
  }
  return out;
}

/** Replace this taxpayer's receipts with a published snapshot (empty = none). */
export function importProfileEvidence(
  profileId: string,
  snapshot: Record<string, Record<string, ReliefEvidenceFile[]>> | null | undefined,
): void {
  const store = readStore();
  const nextYears: Record<string, Record<string, ReliefEvidenceFile[]>> = {};
  for (const [year, groups] of Object.entries(snapshot ?? {})) {
    const canonYear = canonicalEvidenceYear(year);
    const nextGroups: Record<string, ReliefEvidenceFile[]> = {};
    for (const [group, files] of Object.entries(groups ?? {})) {
      const combined = mergeFiles(files ?? []);
      if (combined.length > 0) nextGroups[canonicalEvidenceGroupId(group)] = combined;
    }
    if (Object.keys(nextGroups).length > 0) nextYears[canonYear] = nextGroups;
  }
  store[profileId] = nextYears;
  writeStoreResilient(store);
  emitChange(profileId, "", "");
}

export function hasPublishedEvidenceSnapshot(
  snapshot: Record<string, Record<string, ReliefEvidenceFile[]>> | null | undefined,
): boolean {
  return snapshot != null && typeof snapshot === "object";
}
