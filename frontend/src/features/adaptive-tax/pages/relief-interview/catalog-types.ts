/**
 * Approved relief catalog schema (Phase 3 UI).
 * Live rows arrive via extract → verify → review (Phase 4–5); files may be empty.
 */

export type ReliefInputKind = "notice" | "yes_no_amount" | "amount" | "boolean";

export type ReliefEngineBinding = {
  kind:
    | "solar_panel_relief"
    | "rent_relief"
    | "senior_citizen_interest_relief"
    | "qualifying_payments"
    | "donations"
    | "filing_line"
    | "none";
  /** When kind === filing_line */
  component_id?: string;
};

export type ApprovedEntry = {
  entry_id: string;
  compare_group_id: string;
  display_name: string;
  question_prompt: string;
  sort_order: number;
  input_kind: ReliefInputKind;
  /** Personal relief etc. — shown but not asked for an amount */
  auto_applied?: boolean;
  /** Cap / statutory amount as LKR string when known */
  cap_amount?: string | null;
  unit?: "lkr" | "percent" | "text";
  engine_binding?: ReliefEngineBinding;
  act_name: string;
  section_ref: string;
  quote: string;
  source_doc_id: string;
  needs_manual_verification?: boolean;
};

export type ApprovedYearFile = {
  spec_version?: string;
  assessment_year: string;
  phase1_empty_skeleton?: boolean;
  notes?: string | null;
  entries: ApprovedEntry[];
  entry_count?: number;
  catalog_path?: string;
};

export type ApprovedAllResponse = {
  assessment_years: string[];
  years: Array<{
    assessment_year: string;
    phase1_empty_skeleton?: boolean;
    entries: ApprovedEntry[];
    entry_count: number;
    missing?: boolean;
  }>;
};

export type YearDiffKind =
  | "Increased"
  | "Decreased"
  | "Unchanged"
  | "New"
  | "Not available"
  | "Limited verification";

export type YearDiff = {
  kind: YearDiffKind;
  summary: string;
  asOf?: ApprovedEntry | null;
  compare?: ApprovedEntry | null;
};

function parseCap(raw: string | null | undefined): number | null {
  if (raw == null || raw === "") return null;
  const n = Number(String(raw).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

export function findByGroup(
  entries: ApprovedEntry[],
  compareGroupId: string,
): ApprovedEntry | undefined {
  return entries.find((e) => e.compare_group_id === compareGroupId);
}

/** How the as-of-YA relief differs from the compare year (same compare_group_id). */
export function diffReliefAcrossYears(
  asOf: ApprovedEntry | null | undefined,
  compare: ApprovedEntry | null | undefined,
): YearDiff {
  if (!asOf && !compare) {
    return {
      kind: "Not available",
      summary: "This relief is not in either year’s approved catalog.",
      asOf: null,
      compare: null,
    };
  }
  if (asOf && !compare) {
    return {
      kind: "New",
      summary: "Present in the interview year; not listed in the compare year catalog.",
      asOf,
      compare: null,
    };
  }
  if (!asOf && compare) {
    return {
      kind: "Not available",
      summary: "Listed in the compare year, but not available in the interview year catalog.",
      asOf: null,
      compare,
    };
  }

  const a = asOf!;
  const c = compare!;
  if (a.needs_manual_verification || c.needs_manual_verification) {
    return {
      kind: "Limited verification",
      summary:
        "At least one year’s row is flagged needs_manual_verification — treat the diff as provisional.",
      asOf: a,
      compare: c,
    };
  }

  const aCap = parseCap(a.cap_amount);
  const cCap = parseCap(c.cap_amount);
  if (aCap != null && cCap != null) {
    if (aCap > cCap) {
      return {
        kind: "Increased",
        summary: `Cap rose from ${cCap.toLocaleString("en-LK")} to ${aCap.toLocaleString("en-LK")} LKR.`,
        asOf: a,
        compare: c,
      };
    }
    if (aCap < cCap) {
      return {
        kind: "Decreased",
        summary: `Cap fell from ${cCap.toLocaleString("en-LK")} to ${aCap.toLocaleString("en-LK")} LKR.`,
        asOf: a,
        compare: c,
      };
    }
    return {
      kind: "Unchanged",
      summary: `Cap unchanged at ${aCap.toLocaleString("en-LK")} LKR.`,
      asOf: a,
      compare: c,
    };
  }

  if ((a.quote || "") === (c.quote || "") && a.section_ref === c.section_ref) {
    return {
      kind: "Unchanged",
      summary: "Same section citation and quote in both years’ catalogs.",
      asOf: a,
      compare: c,
    };
  }

  return {
    kind: "Limited verification",
    summary: "Both years have an entry, but caps are missing — cannot assert a numeric change.",
    asOf: a,
    compare: c,
  };
}

export function sortEntries(entries: ApprovedEntry[]): ApprovedEntry[] {
  return [...entries].sort((a, b) => a.sort_order - b.sort_order || a.entry_id.localeCompare(b.entry_id));
}

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

/**
 * True when the catalog row's quote is explicitly sub-year / transitional, but
 * Rule 1 open-ended selection is showing it for a YA after the YA named in the
 * quote (e.g. Act 45 expenditure 900k for nine months of YA commencing 2022-04-01
 * still appearing in 2023/24+).
 */
export function isUnconfirmedTransitionalCarry(
  entry: Pick<ApprovedEntry, "quote">,
  assessmentYear: string,
): boolean {
  const quote = entry.quote || "";
  if (!quoteHasTransitionalScope(quote)) return false;
  const yaStart = yaStartUtc(assessmentYear);
  if (yaStart == null) return false;
  const named = YA_COMMENCING_APRIL_RE.exec(quote);
  if (!named) {
    // Transitional language without a named YA start — do not guess; leave Listed.
    return false;
  }
  const namedStart = aprilFirstUtc(Number(named[1]));
  return yaStart > namedStart;
}

export type CompareRowStatus =
  | "Not available"
  | "Limited verification"
  | "Listed"
  | "Removed"
  | "Last known figure — not confirmed for this year";

export function compareRowStatus(
  entry: ApprovedEntry | null | undefined,
  assessmentYear: string,
): CompareRowStatus {
  if (!entry) return "Not available";
  // Fifth Sch 2(f) expenditure relief ended w.e.f. 1 Jan 2023 (YA 2023/24+).
  if (
    entry.compare_group_id === "expenditure_relief" &&
    assessmentYear > "2022_23"
  ) {
    return "Removed";
  }
  // Fifth Sch 2(b) employment relief: only prior to 1 Jan 2020 (YA ≤ 2019/20).
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

export type ReliefAnswer = {
  entry_id: string;
  compare_group_id: string;
  /** For yes_no_amount / boolean */
  affirmed?: boolean;
  /** Amount claimed (LKR display/wire string) */
  amount?: string;
  /**
   * Optional ¶2(f) subcategory split (presentation only).
   * Sum of values is stored in ``amount`` for the engine filing line.
   */
  amount_breakdown?: Record<string, string>;
  skipped?: boolean;
};
