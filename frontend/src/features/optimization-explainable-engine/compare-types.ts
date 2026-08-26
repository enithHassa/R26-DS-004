/**
 * Cross-year compare helpers — driven by RAG `compare_group_id`, not hardcoded filters.
 * Status rules mirror Adaptive Tax Relief Interview compare (catalog-types).
 */

import type { ReliefEntry } from "./types";

export type CompareGroupOption = {
  compare_group_id: string;
  display_name: string;
};

export type CompareYearBucket = {
  assessment_year: string;
  entries: ReliefEntry[];
  entry_count: number;
};

export type CompareSeriesRow = {
  assessment_year: string;
  entry: ReliefEntry | null;
  cap_amount: string | null;
  source_doc_id: string | null;
  section_ref: string | null;
  needs_manual_verification: boolean;
};

export type CompareResponse = {
  assessment_years: string[];
  exclude_source_doc_id?: string | null;
  compare_group_id?: string | null;
  years: CompareYearBucket[];
  groups: CompareGroupOption[];
  group_count: number;
  series: CompareSeriesRow[] | null;
};

export type CompareRowStatus =
  | "Not available"
  | "Limited verification"
  | "Listed"
  | "Removed"
  | "Last known figure — not confirmed for this year";

/** Sub-year / transitional wording that is not a standing full-YA cap. */
const TRANSITIONAL_SCOPE_RE =
  /first\s+nine\s+months|second\s+three\s+months|first\s+six\s+months|second\s+six\s+months|for\s+the\s+period\s+from/i;

const YA_COMMENCING_APRIL_RE =
  /year\s+of\s+assessment\s+commencing\s+on\s+April\s+1,?\s+(\d{4})/i;

function aprilFirstUtc(year: number): number {
  return Date.UTC(year, 3, 1);
}

function yaStartUtc(assessmentYear: string): number | null {
  const m = /^(\d{4})_\d{2}$/.exec(assessmentYear);
  if (!m) return null;
  return aprilFirstUtc(Number(m[1]));
}

export function quoteHasTransitionalScope(quote: string | null | undefined): boolean {
  return TRANSITIONAL_SCOPE_RE.test(quote || "");
}

export function isUnconfirmedTransitionalCarry(
  entry: Pick<ReliefEntry, "quote">,
  assessmentYear: string,
): boolean {
  const quote = entry.quote || "";
  if (!quoteHasTransitionalScope(quote)) return false;
  const yaStart = yaStartUtc(assessmentYear);
  if (yaStart == null) return false;
  const named = YA_COMMENCING_APRIL_RE.exec(quote);
  if (!named) return false;
  const namedStart = aprilFirstUtc(Number(named[1]));
  return yaStart > namedStart;
}

export function findByGroup(
  entries: ReliefEntry[],
  compareGroupId: string,
): ReliefEntry | undefined {
  return entries.find((e) => e.compare_group_id === compareGroupId);
}

export function compareRowStatus(
  entry: ReliefEntry | null | undefined,
  assessmentYear: string,
  compareGroupId?: string,
): CompareRowStatus {
  const group = compareGroupId ?? entry?.compare_group_id ?? "";
  if (
    group === "employment_income_relief" &&
    assessmentYear > "2019_20"
  ) {
    return "Removed";
  }
  if (
    group === "expenditure_relief" &&
    assessmentYear > "2022_23"
  ) {
    return "Removed";
  }
  if (!entry) return "Not available";
  if (
    entry.compare_group_id === "expenditure_relief" &&
    assessmentYear > "2022_23"
  ) {
    return "Removed";
  }
  if (
    entry.compare_group_id === "employment_income_relief" &&
    assessmentYear > "2019_20"
  ) {
    return "Removed";
  }
  if (entry.needs_manual_verification) return "Limited verification";
  if (isUnconfirmedTransitionalCarry(entry, assessmentYear)) {
    return "Last known figure — not confirmed for this year";
  }
  return "Listed";
}

export function formatCompareCap(entry: ReliefEntry | null | undefined): string {
  if (!entry?.cap_amount) return "—";
  const raw = String(entry.cap_amount);
  if (entry.unit === "percent") return `${raw.replace(/%$/, "")}%`;
  if (entry.unit === "text") return raw;
  const n = Number(raw.replace(/,/g, ""));
  if (!Number.isFinite(n)) return raw;
  return new Intl.NumberFormat("en-LK", { maximumFractionDigits: 0 }).format(n);
}
