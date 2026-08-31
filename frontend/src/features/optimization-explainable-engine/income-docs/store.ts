/**
 * Taxpayer additional income documents — profile + year + category + slot.
 * Shared via localStorage + tax_return_detail publish on Save / Mark Complete.
 */

import { canonicalEvidenceYear, evidenceYearKeys } from "../relief-evidence/canonical-group";

export type IncomeDocFile = {
  id: string;
  fileName: string;
  mimeType: string;
  dataUrl: string;
  uploadedAt: string;
};

/** year → category → slot → files */
export type IncomeDocsSnapshot = Record<
  string,
  Record<string, Record<string, IncomeDocFile[]>>
>;

type StoreShape = Record<string, IncomeDocsSnapshot>;

const STORAGE_KEY = "oe-income-docs-v1";
export const INCOME_DOCS_CHANGED = "oe-income-docs-changed";
const CHANNEL_NAME = "oe-income-docs";
export const MAX_INCOME_DOC_BYTES = 2 * 1024 * 1024;
export const MAX_FILES_PER_SLOT = 3;

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

function emitChange(profileId: string): void {
  window.dispatchEvent(
    new CustomEvent(INCOME_DOCS_CHANGED, { detail: { profileId } }),
  );
  evidenceChannel()?.postMessage({ type: "changed", profileId });
}

export function subscribeIncomeDocsChanges(onChange: () => void): () => void {
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
  window.addEventListener(INCOME_DOCS_CHANGED, onCustom);
  window.addEventListener("storage", onStorage);
  window.addEventListener("focus", onFocus);
  const ch = evidenceChannel();
  ch?.addEventListener("message", onMessage);
  return () => {
    window.removeEventListener(INCOME_DOCS_CHANGED, onCustom);
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("focus", onFocus);
    ch?.removeEventListener("message", onMessage);
  };
}

function mergeFiles(items: IncomeDocFile[]): IncomeDocFile[] {
  const seen = new Set<string>();
  const merged: IncomeDocFile[] = [];
  for (const file of items) {
    if (!file?.id || seen.has(file.id)) continue;
    seen.add(file.id);
    merged.push(file);
  }
  return merged.sort((a, b) => String(b.uploadedAt).localeCompare(String(a.uploadedAt)));
}

function yearBuckets(store: StoreShape, profileId: string, assessmentYear: string) {
  const wanted = new Set(evidenceYearKeys(assessmentYear));
  const byYear = store[profileId] ?? {};
  const out: Array<Record<string, Record<string, IncomeDocFile[]>>> = [];
  for (const [year, cats] of Object.entries(byYear)) {
    if (evidenceYearKeys(year).some((k) => wanted.has(k))) out.push(cats);
  }
  return out;
}

export function listIncomeDocs(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  categoryId: string,
  slotId: string,
): IncomeDocFile[] {
  if (!profileId || !assessmentYear) return [];
  const collected: IncomeDocFile[] = [];
  for (const cats of yearBuckets(readStore(), profileId, assessmentYear)) {
    collected.push(...(cats[categoryId]?.[slotId] ?? []));
  }
  return mergeFiles(collected);
}

export function countIncomeDocsForCategory(
  profileId: string | null | undefined,
  assessmentYear: string | null | undefined,
  categoryId: string,
): number {
  if (!profileId || !assessmentYear) return 0;
  let n = 0;
  for (const cats of yearBuckets(readStore(), profileId, assessmentYear)) {
    const slots = cats[categoryId] ?? {};
    for (const files of Object.values(slots)) n += files?.length ?? 0;
  }
  return n;
}

export function addIncomeDoc(
  profileId: string,
  assessmentYear: string,
  categoryId: string,
  slotId: string,
  file: IncomeDocFile,
): IncomeDocFile[] {
  const store = readStore();
  const year = canonicalEvidenceYear(assessmentYear);
  const existing = listIncomeDocs(profileId, assessmentYear, categoryId, slotId);
  const nextFiles = mergeFiles([...existing, file]).slice(0, MAX_FILES_PER_SLOT);
  const byYear = { ...(store[profileId] ?? {}) };
  for (const yearKey of Object.keys(byYear)) {
    if (!evidenceYearKeys(yearKey).some((k) => evidenceYearKeys(assessmentYear).includes(k))) {
      continue;
    }
    const cats = { ...byYear[yearKey] };
    const slots = { ...(cats[categoryId] ?? {}) };
    delete slots[slotId];
    if (Object.keys(slots).length > 0) cats[categoryId] = slots;
    else delete cats[categoryId];
    if (Object.keys(cats).length > 0) byYear[yearKey] = cats;
    else delete byYear[yearKey];
  }
  const cats = { ...(byYear[year] ?? {}) };
  const slots = { ...(cats[categoryId] ?? {}) };
  slots[slotId] = nextFiles;
  cats[categoryId] = slots;
  byYear[year] = cats;
  store[profileId] = byYear;
  try {
    writeStore(store);
  } catch {
    throw new Error("Browser storage is full. Remove an older document and try again.");
  }
  emitChange(profileId);
  return nextFiles;
}

export function removeIncomeDoc(
  profileId: string,
  assessmentYear: string,
  categoryId: string,
  slotId: string,
  fileId: string,
): IncomeDocFile[] {
  const nextFiles = listIncomeDocs(profileId, assessmentYear, categoryId, slotId).filter(
    (f) => f.id !== fileId,
  );
  const store = readStore();
  const year = canonicalEvidenceYear(assessmentYear);
  const byYear = { ...(store[profileId] ?? {}) };
  for (const yearKey of Object.keys(byYear)) {
    if (!evidenceYearKeys(yearKey).some((k) => evidenceYearKeys(assessmentYear).includes(k))) {
      continue;
    }
    const cats = { ...byYear[yearKey] };
    const slots = { ...(cats[categoryId] ?? {}) };
    if (canonicalEvidenceYear(yearKey) === year && nextFiles.length > 0) {
      slots[slotId] = nextFiles;
    } else {
      delete slots[slotId];
    }
    if (Object.keys(slots).length > 0) cats[categoryId] = slots;
    else delete cats[categoryId];
    if (Object.keys(cats).length > 0) byYear[yearKey] = cats;
    else delete byYear[yearKey];
  }
  if (nextFiles.length > 0) {
    const cats = { ...(byYear[year] ?? {}) };
    const slots = { ...(cats[categoryId] ?? {}) };
    slots[slotId] = nextFiles;
    cats[categoryId] = slots;
    byYear[year] = cats;
  }
  store[profileId] = byYear;
  writeStore(store);
  emitChange(profileId);
  return nextFiles;
}

export function exportIncomeDocs(profileId: string): IncomeDocsSnapshot {
  const byYear = readStore()[profileId] ?? {};
  const out: IncomeDocsSnapshot = {};
  for (const [year, cats] of Object.entries(byYear)) {
    const canonYear = canonicalEvidenceYear(year);
    const mergedCats = { ...(out[canonYear] ?? {}) };
    for (const [cat, slots] of Object.entries(cats)) {
      const mergedSlots = { ...(mergedCats[cat] ?? {}) };
      for (const [slot, files] of Object.entries(slots)) {
        mergedSlots[slot] = mergeFiles([...(mergedSlots[slot] ?? []), ...(files ?? [])]);
        if (mergedSlots[slot].length === 0) delete mergedSlots[slot];
      }
      if (Object.keys(mergedSlots).length > 0) mergedCats[cat] = mergedSlots;
      else delete mergedCats[cat];
    }
    if (Object.keys(mergedCats).length > 0) out[canonYear] = mergedCats;
  }
  return out;
}

export function importIncomeDocs(
  profileId: string,
  snapshot: IncomeDocsSnapshot | null | undefined,
): void {
  const store = readStore();
  const next: IncomeDocsSnapshot = {};
  for (const [year, cats] of Object.entries(snapshot ?? {})) {
    const canonYear = canonicalEvidenceYear(year);
    const nextCats: Record<string, Record<string, IncomeDocFile[]>> = {};
    for (const [cat, slots] of Object.entries(cats ?? {})) {
      const nextSlots: Record<string, IncomeDocFile[]> = {};
      for (const [slot, files] of Object.entries(slots ?? {})) {
        const combined = mergeFiles(files ?? []);
        if (combined.length > 0) nextSlots[slot] = combined;
      }
      if (Object.keys(nextSlots).length > 0) nextCats[cat] = nextSlots;
    }
    if (Object.keys(nextCats).length > 0) next[canonYear] = nextCats;
  }
  store[profileId] = next;
  writeStore(store);
  emitChange(profileId);
}

export function hasPublishedIncomeDocsSnapshot(
  snapshot: IncomeDocsSnapshot | null | undefined,
): boolean {
  return snapshot != null && typeof snapshot === "object";
}
