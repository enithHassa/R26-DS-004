import type { ReliefEntry } from "./types";

/**
 * Interview sidebar order for well-known reliefs.
 * Display-only — does not change act ingest, year views, or catalog sort_order.
 * Unknown / newly loaded reliefs keep their API sort_order after these.
 */
const KNOWN_RELIEF_ORDER: string[] = [
  "personal_relief",
  "solar_panel_relief",
  "rental_income_relief",
  "rent_relief",
  "donation_to_charitable_institution",
  "donation_to_government_or_approved_fund",
];

type ReliefSortable = {
  compare_group_id?: string | null;
  display_name?: string | null;
  sort_order?: number | null;
  entry_id?: string | null;
};

export function reliefDisplayRank(entry: ReliefSortable): number {
  const group = (entry.compare_group_id ?? "").toLowerCase().trim();
  const name = (entry.display_name ?? "").toLowerCase();

  if (group === "personal_relief" || name.includes("personal relief")) return 0;
  if (group === "solar_panel_relief" || name.includes("solar panel")) return 1;
  if (
    group === "rental_income_relief" ||
    group === "rent_relief" ||
    name.includes("rental income relief") ||
    name.includes("rent relief")
  ) {
    return 2;
  }
  if (
    group === "donation_to_charitable_institution" ||
    (name.includes("donation") && name.includes("charitable"))
  ) {
    return 3;
  }
  if (
    group === "donation_to_government_or_approved_fund" ||
    (name.includes("donation") &&
      (name.includes("government") || name.includes("approved fund")))
  ) {
    return 4;
  }
  return KNOWN_RELIEF_ORDER.length;
}

function compareReliefSortables(a: ReliefSortable, b: ReliefSortable): number {
  const rankA = reliefDisplayRank(a);
  const rankB = reliefDisplayRank(b);
  if (rankA !== rankB) return rankA - rankB;
  const orderA = a.sort_order ?? 0;
  const orderB = b.sort_order ?? 0;
  if (orderA !== orderB) return orderA - orderB;
  return String(a.entry_id ?? a.display_name ?? "").localeCompare(
    String(b.entry_id ?? b.display_name ?? ""),
  );
}

/** Stable interview ordering: known reliefs first, then catalog sort_order. */
export function sortReliefsForInterview(entries: ReliefEntry[]): ReliefEntry[] {
  return [...entries].sort(compareReliefSortables);
}

/** Same known-first order for applied relief lines on Result / plain English. */
export function sortReliefLinesForDisplay<T extends ReliefSortable>(lines: T[]): T[] {
  return [...lines].sort(compareReliefSortables);
}
