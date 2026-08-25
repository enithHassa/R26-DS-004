import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, CheckCircle2, CircleDashed, FileText, XCircle } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

import {
  approveCatalogAdminRow,
  confirmCatalogAdminNewYear,
  getCatalogAdminProposal,
  previewCatalogAdminPromote,
  promoteCatalogAdminNewYear,
  promoteCatalogAdminUpdate,
  rejectCatalogAdminRow,
  runCatalogAdminHarvest,
  setCatalogAdminClassification,
  setCatalogAdminEngineBinding,
  setCatalogAdminQuestionFields,
  type CatalogAdminEngineBindingKind,
  type CatalogAdminKind,
  type CatalogAdminPreviewGroup,
  type CatalogAdminPromotePreview,
  type CatalogAdminPromoteResult,
  type CatalogAdminProposalReview,
  type CatalogAdminProvision,
  type CatalogAdminReviewRow,
} from "./api";
import { formatLkr } from "../../format-lkr";

function catalogAdminActionError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Request failed.";
  if (/HTTP 404|Not Found/i.test(msg)) {
    return (
      `${msg} Adaptive Tax is still the old process (classification works, ` +
      `tax-effect / approve do not). Stop the :8006 uvicorn fully and start it again ΓÇö ` +
      `--reload does not pick up the new engine-binding routes.`
    );
  }
  return msg;
}

function promoteIndexRefreshNote(
  indexRefresh: NonNullable<CatalogAdminPromoteResult["promotion"]>["index_refresh"],
): string {
  if (!indexRefresh) return "";
  if (indexRefresh.ok) {
    const years = Array.isArray(indexRefresh.body?.years) ? indexRefresh.body.years : [];
    const latest = years.length ? years[years.length - 1] : null;
    if (latest) {
      return ` OE index updated ΓÇö YA ${yearLabel(latest)} is now available in the interview, reliefs, and compare.`;
    }
    return " OE index updated ΓÇö taxpayer Reliefs and Compare will use the latest catalog.";
  }
  const detail =
    typeof indexRefresh.error === "string"
      ? indexRefresh.error
      : "Optimization and Explainable was not reachable.";
  return ` Promote saved, but OE index was not refreshed (${detail}). Start :8008 and restart OE or POST /index/refresh.`;
}

const RATE_KINDS = new Set(["rate_band", "surcharge", "special_formula", "rule"]);

function isReliefKind(kind: string | undefined): boolean {
  const value = kind || "";
  return value === "relief" || value.startsWith("qp_");
}

function provisionAsRow(provision: CatalogAdminProvision): CatalogAdminReviewRow {
  const kind = provision.row_kind || "";
  return {
    entry_id: provision.row_id,
    row_kind: kind,
    display_name: provision.display_name || provision.row_id,
    effective_from: provision.effective_from,
    section_ref: provision.section_ref,
    quote: provision.row_quote,
    included: true,
    gate_ok: true,
    classification: provision,
    engine_binding: provision.engine_binding,
    tax_effect: isReliefKind(kind)
      ? "Calculator rule not chosen ΓÇö approve is blocked until you pick Step 1 below."
      : null,
    can_approve: false,
    approve_label: RATE_KINDS.has(kind)
      ? "I have read the Act text and accept this rate without an independent check"
      : "Approve",
    sole_check: RATE_KINDS.has(kind),
    panel: RATE_KINDS.has(kind) ? "rate" : isReliefKind(kind) ? "relief" : "other",
  };
}

const BINDING_OPTIONS: Array<{ value: CatalogAdminEngineBindingKind; label: string }> = [
  {
    value: "none",
    label: "Standard relief (default ΓÇö personal, claims, auto-applied caps)",
  },
  { value: "solar_panel_relief", label: "Solar panel relief" },
  { value: "rent_relief", label: "Rental income relief" },
  { value: "senior_citizen_interest_relief", label: "Senior citizen interest relief" },
  { value: "qualifying_payments", label: "Qualifying payments" },
  { value: "donations", label: "Donations" },
  { value: "filing_line", label: "Calculator filing line (advanced)" },
];

const STANDARD_BINDING_GROUPS = new Set([
  "personal_relief",
  "employment_income_relief",
  "expenditure_relief",
  "digital_productivity_equipment_relief",
]);

function recommendedBindingKind(row: CatalogAdminReviewRow): CatalogAdminEngineBindingKind {
  const group = (row.catalog_compare_group_id || row.compare_group_id || "").trim();
  if (group === "solar_panel_relief") return "solar_panel_relief";
  if (group === "rental_income_relief" || group === "rent_relief") return "rent_relief";
  if (group === "senior_citizen_interest_relief") return "senior_citizen_interest_relief";
  return "none";
}

function bindingOptionLabel(kind: string | undefined): string {
  const match = BINDING_OPTIONS.find((option) => option.value === kind);
  if (!match) return "Standard relief";
  return match.label.split("ΓÇö")[0]?.trim() || match.label;
}

function bindingRecommendation(row: CatalogAdminReviewRow): string | null {
  const group = (row.catalog_compare_group_id || row.compare_group_id || "").trim();
  const inputKind = row.input_kind || "";
  if (STANDARD_BINDING_GROUPS.has(group) || inputKind === "notice") {
    return "Quick approve picks Standard relief ΓÇö fine for personal relief and most Fifth Schedule items.";
  }
  if (inputKind === "yes_no_amount" || inputKind === "amount") {
    return "Quick approve picks Standard relief for yes/no + amount reliefs like this one.";
  }
  if (group === "solar_panel_relief") return "Quick approve picks Solar panel relief.";
  if (group === "rental_income_relief" || group === "rent_relief") {
    return "Quick approve picks Rental income relief.";
  }
  if (group === "senior_citizen_interest_relief") {
    return "Quick approve picks Senior citizen interest relief.";
  }
  return "Expand optional edits below only if you need a non-default calculator rule.";
}

function friendlyTaxEffectCopy(raw: string | null | undefined): string {
  if (!raw) return "";
  if (raw.includes("cannot be approved until you pick")) {
    return "Choose a calculator rule below before you can approve this row.";
  }
  if (raw.includes("will NOT affect") && raw.includes("kind: none")) {
    return "Standard rule saved. The calculator uses the cap plus the taxpayer's answers from Step 2.";
  }
  if (raw.includes("WILL reduce calculated tax")) {
    return raw.replace(
      "This relief WILL reduce calculated tax",
      "Special rule saved ΓÇö this relief will reduce calculated tax",
    );
  }
  return raw;
}

const QUESTION_INPUT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "notice", label: "Notice (auto-applied, no claim)" },
  { value: "yes_no_amount", label: "Yes/no + amount" },
  { value: "amount", label: "Amount only" },
  { value: "boolean", label: "Yes/no" },
];

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatRowCap(row: CatalogAdminReviewRow): string {
  const raw = row.cap_amount;
  if (raw == null || raw === "") return "ΓÇö";
  const text = String(raw).trim();
  if (/%$/.test(text)) return text;
  const group = `${row.catalog_compare_group_id || ""} ${row.compare_group_id || ""}`.toLowerCase();
  if (group.includes("rental") || group.includes("percent")) {
    return `${text.replace(/%$/, "")}%`;
  }
  const n = Number(text.replace(/,/g, ""));
  if (Number.isFinite(n) && n >= 1000) return formatLkr(n);
  if (Number.isFinite(n) && n > 0 && n <= 100 && Number.isInteger(n)) return `${n}%`;
  return text;
}

function rowPanelKind(row: CatalogAdminReviewRow): "relief" | "rate" | "other" {
  if (row.panel) return row.panel;
  const kind = row.row_kind || row.classification?.row_kind || "";
  if (RATE_KINDS.has(kind)) return "rate";
  if (isReliefKind(kind)) return "relief";
  return "other";
}

function rowKindLabel(kind?: string | null): string {
  switch (kind) {
    case "rate_band":
      return "Income tax band";
    case "special_formula":
      return "Special formula";
    case "rule":
      return "Rate rule";
    case "surcharge":
      return "Surcharge";
    default:
      return humanId(kind);
  }
}

function formatRowExtractedValue(row: CatalogAdminReviewRow): string {
  const panel = rowPanelKind(row);
  if (panel === "relief") {
    const cap = formatRowCap(row);
    if (cap !== "ΓÇö") return cap;
  }
  if (panel === "rate") {
    const parts: string[] = [];
    if (row.rate_percent != null) parts.push(`${row.rate_percent}%`);
    else if (row.value != null && row.value !== "") parts.push(String(row.value));
    if (row.lower != null || row.upper != null) {
      parts.push(`${row.lower ?? "0"} ΓÇô ${row.upper ?? "Γê₧"}`);
    }
    if (parts.length) return parts.join(" ┬╖ ");
  }
  if (row.description?.trim()) {
    const text = row.description.trim();
    return text.length > 96 ? `${text.slice(0, 93)}ΓÇª` : text;
  }
  if (row.value != null && row.value !== "") return String(row.value);
  return "ΓÇö";
}

function formatRowTaxEngineLabel(row: CatalogAdminReviewRow): string {
  const panel = rowPanelKind(row);
  if (panel === "relief") {
    const binding = row.engine_binding?.kind ?? row.classification?.engine_binding?.kind;
    if (binding === "none") return "Interview only";
    if (binding) return bindingOptionLabel(binding);
    return "ΓÇö";
  }
  if (panel === "rate") return rowKindLabel(row.row_kind);
  return "Catalog note";
}

function rowSummarySubLabel(row: CatalogAdminReviewRow): string {
  return (
    humanId(row.compare_group_id || row.catalog_compare_group_id) ||
    rowKindLabel(row.row_kind) ||
    row.section_ref ||
    ""
  );
}

type PromoteIncludedRowView = {
  row: CatalogAdminReviewRow;
  sections: string[];
  mergedCount: number;
};

function promoteRowDedupeKey(row: CatalogAdminReviewRow): string {
  const panel = rowPanelKind(row);
  if (panel === "rate" && row.row_kind === "rate_band") {
    return [
      "band",
      row.display_name || "",
      row.rate_percent ?? "",
      row.lower ?? "",
      row.upper ?? "",
      row.classification?.kind_human ?? "",
    ].join("|");
  }
  return `row|${row.entry_id}`;
}

function dedupePromoteIncludedRows(rows: CatalogAdminReviewRow[]): PromoteIncludedRowView[] {
  const map = new Map<string, PromoteIncludedRowView>();
  for (const row of rows) {
    const key = promoteRowDedupeKey(row);
    const section = row.section_ref?.trim() || "";
    const existing = map.get(key);
    if (existing) {
      existing.mergedCount += 1;
      if (section && !existing.sections.includes(section)) {
        existing.sections.push(section);
      }
    } else {
      map.set(key, {
        row,
        sections: section ? [section] : [],
        mergedCount: 1,
      });
    }
  }
  return [...map.values()];
}

function promoteIncludedSubLabel(view: PromoteIncludedRowView): string | null {
  if (view.sections.length > 1) {
    return `Same extract in ${view.sections.join(" ┬╖ ")}`;
  }
  if (view.sections.length === 1) {
    return view.sections[0];
  }
  return rowSummarySubLabel(view.row) || null;
}

function humanId(id?: string | null): string {
  if (!id) return "";
  return id.replaceAll("_", " ");
}

function yearLabel(ya?: string | null): string {
  if (!ya) return "";
  const match = ya.match(/(\d{4})_(\d{2})/);
  if (match) return `${match[1]}/${match[2]}`;
  return ya.replace("_", "/");
}

type CatalogYearContext = {
  liveYas: string[];
  maxInScopeYa?: string | null;
};

/** UPDATE writes to a year file that already exists (or max in-scope), not a future NEW year. */
function updateTargetYaSlug(
  provision: CatalogAdminProvision | null | undefined,
  ctx?: CatalogYearContext,
): string | null {
  if (!provision) return null;
  const derived = provision.derived_assessment_year?.trim() || null;
  const live = ctx?.liveYas ?? [];
  if (derived && live.includes(derived)) {
    return derived;
  }
  const max = ctx?.maxInScopeYa?.trim();
  if (max) return max;
  if (live.length) return live[live.length - 1];
  return null;
}

/** Human label for UPDATE vs NEW_YEAR ΓÇö NEW uses act-derived YA; UPDATE uses live catalog YA. */
function kindDecisionLabel(
  kind: CatalogAdminKind | null | undefined,
  provision?: CatalogAdminProvision | null,
  options?: { defaultSuffix?: boolean; yearCtx?: CatalogYearContext },
): string {
  const newYa = yearLabel(provision?.derived_assessment_year);
  const updateSlug = updateTargetYaSlug(provision, options?.yearCtx);
  const updateYa = yearLabel(updateSlug);
  if (kind === "NEW_YEAR") {
    return newYa ? `Create a new year ┬╖ YA ${newYa}` : "Create a new year";
  }
  if (kind === "UPDATE") {
    return updateYa ? `Update existing year ┬╖ YA ${updateYa}` : "Update existing year";
  }
  if (options?.defaultSuffix) {
    return updateYa
      ? `Update existing year ┬╖ YA ${updateYa} (default)`
      : "Update existing year (default)";
  }
  return updateYa ? `Update existing year ┬╖ YA ${updateYa}` : "Update existing year";
}

function derivedYearHint(
  provision: CatalogAdminProvision,
  yearCtx?: CatalogYearContext,
): string | null {
  const newYa = yearLabel(provision.derived_assessment_year);
  if (!newYa) return null;
  const updateYa = yearLabel(updateTargetYaSlug(provision, yearCtx));
  const newNotLive =
    provision.derived_assessment_year &&
    !(yearCtx?.liveYas ?? []).includes(provision.derived_assessment_year);
  if (provision.kind_suggested === "NEW_YEAR" || newNotLive) {
    return updateYa && updateYa !== newYa
      ? `Act commencement creates YA ${newYa} (not in catalog yet). Choose Create a new year, then confirm the year file below. Update existing year amends YA ${updateYa} instead.`
      : `Act commencement creates YA ${newYa}. Choose Create a new year, then confirm the year file below before promote.`;
  }
  if (provision.kind_suggested === "UPDATE") {
    return `From the act date, this row updates YA ${newYa} in the live catalog on promote.`;
  }
  return updateYa && updateYa !== newYa
    ? `Act date ΓåÆ YA ${newYa}. Update existing year ΓåÆ YA ${updateYa}; Create a new year ΓåÆ YA ${newYa}.`
    : `From the act date, this row targets YA ${newYa}.`;
}

function yearFileLabel(path: string): string {
  const match = path.match(/(approved|rates)\/(\d{4})_(\d{2})/);
  if (!match) return yearLabel(path) || path;
  const kind = match[1] === "approved" ? "reliefs" : "rates";
  return `${kind} ${match[2]}/${match[3]}`;
}

function bindingLabel(kind?: string | null): string {
  return BINDING_OPTIONS.find((option) => option.value === kind)?.label || kind || "Not chosen";
}

function groupLabel(row: CatalogAdminReviewRow): string {
  const id = row.catalog_compare_group_id || row.compare_group_id || "";
  if (!id) return "";
  if (id.includes("fifth_schedule")) return "Fifth Schedule";
  if (id === "rental_income_relief" || id === "rent_relief") return "Rental income";
  if (id === "solar_panel_relief") return "Solar panel";
  if (id === "personal_relief") return "Personal relief";
  if (id === "employment_income_relief") return "Employment relief";
  if (id === "expenditure_relief") return "Expenditure relief";
  if (id.startsWith("qp_")) return "Qualifying payment";
  return humanId(id);
}

function isTableActQuote(row: CatalogAdminReviewRow): boolean {
  const quote = (row.quote || "").trim();
  return row.quote_source === "table_render" || quote.includes("|");
}

function actQuoteDisplayText(row: CatalogAdminReviewRow): string {
  const quote = (row.quote || "").trim();
  if (!quote) return "";

  if (!isTableActQuote(row)) {
    return quote;
  }

  const lines = quote.split(/\n/).map((line) => line.trim()).filter(Boolean);
  const bodyLines = lines.filter((line) => {
    const firstCell = line.split("|")[0]?.trim().toLowerCase() || "";
    return !/^(taxable income|total income|tax payable)/.test(firstCell);
  });
  const dataLine = bodyLines[bodyLines.length - 1] || lines[lines.length - 1] || quote;
  const parts = dataLine.split("|").map((part) => part.trim()).filter(Boolean);
  const band =
    row.band_label?.trim() ||
    (parts.length >= 2 ? parts.slice(0, -1).join(" ") : parts[0] || "");
  const formula = parts.length >= 2 ? parts[parts.length - 1]! : "";

  if (band && formula && band !== formula) {
    const taxLine = /^rs\.|^tax payable/i.test(formula) ? formula : `Tax payable: ${formula}`;
    return `${band}\n${taxLine}`;
  }

  return quote.replace(/\s*\|\s*/g, "\n").trim();
}

function reflowToParagraphs(lines: string[]): string[] {
  const paragraphs: string[] = [];
  let buf = "";

  const flush = () => {
    const text = buf.replace(/\s+/g, " ").trim();
    if (text) paragraphs.push(text);
    buf = "";
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    const startsNew =
      /^(FIRST|FIFTH|SECOND|THIRD)\s+SCHEDULE/i.test(line) ||
      /^\(Section\s+\d+\)/i.test(line) ||
      /^TAX RATES/i.test(line) ||
      /^\(\d+\)\s/.test(line) ||
      /^\d+\.\s+[A-Z]/.test(line) ||
      (/^[A-Z][A-Z\s]{8,}$/.test(line) && !buf);

    if (startsNew && buf) flush();
    buf = buf ? `${buf} ${line}` : line;
    if (/[.:;!?]$/.test(line)) flush();
  }
  flush();
  return paragraphs;
}

function sectionIntroParagraphs(raw: string): string[] {
  const lines = raw.split(/\n/).map((line) => line.trim()).filter(Boolean);
  const cut = lines.findIndex(
    (line) =>
      /^Taxable Income$/i.test(line) ||
      /^Tax Payable$/i.test(line) ||
      /following rates:?$/i.test(line),
  );
  const introEnd =
    cut >= 0 && /following rates:?$/i.test(lines[cut] || "") ? cut + 1 : cut;
  const introLines = cut >= 0 ? lines.slice(0, introEnd) : lines.filter((line) => !/^(Not |Exceeding Rs\.)/i.test(line));
  return reflowToParagraphs(introLines);
}

function parseScheduleBands(raw: string): Array<{ band: string; formula: string }> {
  const lines = raw.split(/\n/).map((line) => line.trim()).filter(Boolean);
  const start = lines.findIndex((line) => /^Tax Payable$/i.test(line));
  if (start < 0) return [];

  const bands: Array<{ band: string; formula: string }> = [];
  let currentBand = "";
  let formulaParts: string[] = [];

  const flush = () => {
    if (!currentBand) return;
    bands.push({
      band: currentBand.replace(/\s+/g, " ").trim(),
      formula: formulaParts.join(" ").replace(/\s+/g, " ").trim(),
    });
    currentBand = "";
    formulaParts = [];
  };

  for (const line of lines.slice(start + 1)) {
    if (/^\(\d+\)/.test(line) || /^Where an individual/i.test(line) || /^Total Income from/i.test(line)) {
      flush();
      break;
    }
    if (/^(Not )?Exceeding Rs\./i.test(line)) {
      flush();
      currentBand = line;
      continue;
    }
    if (currentBand && /^(exceeding Rs\.|\d+%|Rs\. \d)/i.test(line) && !/^(Not )?Exceeding Rs\./i.test(line)) {
      formulaParts.push(line);
      continue;
    }
    if (currentBand && formulaParts.length === 0 && /but not$/i.test(currentBand)) {
      currentBand = `${currentBand} ${line}`;
      continue;
    }
    if (currentBand) formulaParts.push(line);
  }
  flush();
  return bands.filter((row) => row.band && row.formula);
}

function SectionActProseDisplay({ prose }: { prose: string }) {
  const paragraphs = sectionIntroParagraphs(prose);
  const bands = parseScheduleBands(prose);

  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {paragraphs.map((paragraph) => (
        <p key={paragraph.slice(0, 48)}>{paragraph}</p>
      ))}
      {bands.length > 0 ? (
        <div className="overflow-x-auto rounded-md border bg-background/80">
          <table className="w-full min-w-[420px] text-left text-xs">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Taxable income band</th>
                <th className="px-3 py-2 font-medium">Tax payable</th>
              </tr>
            </thead>
            <tbody>
              {bands.map((row) => (
                <tr key={row.band} className="border-t align-top">
                  <td className="px-3 py-2 pr-4">{row.band}</td>
                  <td className="px-3 py-2">{row.formula}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ActQuoteBlock({ row }: { row: CatalogAdminReviewRow }) {
  const text = actQuoteDisplayText(row);
  const tableQuote = isTableActQuote(row);
  const sectionProse = row.section_act_prose?.trim();

  if (!text && !sectionProse) {
    return <p className="text-sm text-muted-foreground">No Act quote on this row.</p>;
  }

  return (
    <div className="space-y-3">
      {sectionProse ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            From the Act (schedule text)
            {row.section_ref ? ` ┬╖ ${row.section_ref}` : ""}
          </p>
          <blockquote className="max-h-80 overflow-y-auto rounded-lg border-l-4 border-primary/30 bg-muted/40 px-4 py-3">
            <SectionActProseDisplay prose={sectionProse} />
          </blockquote>
        </div>
      ) : null}
      {text ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            {tableQuote ? "This band" : "Act quote"}
            {!sectionProse && row.section_ref ? ` ┬╖ ${row.section_ref}` : ""}
            {!sectionProse && row.applies_to ? ` ┬╖ ${row.applies_to}` : ""}
          </p>
          <blockquote className="rounded-lg border-l-4 border-primary/30 bg-muted/40 px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
            {text}
          </blockquote>
        </div>
      ) : null}
      {tableQuote && row.quote && row.quote !== text ? (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">Raw PDF table row</summary>
          <p className="mt-1 whitespace-pre-wrap font-mono text-[11px] leading-relaxed">{row.quote}</p>
        </details>
      ) : null}
    </div>
  );
}

function reliefSectionTitle(row: CatalogAdminReviewRow): string {
  const id = `${row.catalog_compare_group_id || ""} ${row.compare_group_id || ""} ${row.section_ref || ""}`.toLowerCase();
  if (id.includes("fifth")) return "Fifth Schedule qualifying payments";
  if (id.includes("rent")) return "Rental income";
  if (id.includes("solar")) return "Solar panel";
  if (id.includes("personal")) return "Personal relief";
  if (id.includes("employment")) return "Employment relief";
  if (id.includes("expenditure")) return "Expenditure relief";
  if (id.includes("qp_") || id.includes("qualifying") || id.includes("donation")) {
    return "Qualifying payments and donations";
  }
  return "Other reliefs";
}

function groupRowsBySection(
  rows: CatalogAdminReviewRow[],
): Array<{ title: string; rows: CatalogAdminReviewRow[] }> {
  const groups: Array<{ title: string; rows: CatalogAdminReviewRow[] }> = [];
  for (const row of rows) {
    const title = reliefSectionTitle(row);
    const last = groups[groups.length - 1];
    if (last && last.title === title) last.rows.push(row);
    else groups.push({ title, rows: [row] });
  }
  return groups;
}

function isReExtractStatus(status?: string | null): boolean {
  return status === "needs_manual_verification" || status === "flagged";
}

function decisionLabel(status?: string | null): string {
  if (status === "approved") return "Approved";
  if (status === "rejected") return "Rejected";
  if (isReExtractStatus(status)) return "Needs decision";
  return status ? humanId(status) : "";
}

type ReviewCounts = {
  total: number;
  approved: number;
  rejected: number;
  pending: number;
};

function countReviewRows(rows: CatalogAdminReviewRow[]): ReviewCounts {
  const included = rows.filter((row) => row.included);
  const approved = included.filter((row) => row.decision_status === "approved").length;
  const rejected = included.filter((row) => row.decision_status === "rejected").length;
  return {
    total: included.length,
    approved,
    rejected,
    pending: included.length - approved - rejected,
  };
}

function decisionBadge(status?: string | null) {
  if (status === "approved") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-900">
        <CheckCircle2 className="h-3 w-3" aria-hidden />
        Approved
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-[11px] font-medium text-rose-900">
        <XCircle className="h-3 w-3" aria-hidden />
        Rejected
      </span>
    );
  }
  if (isReExtractStatus(status)) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
        <CircleDashed className="h-3 w-3" aria-hidden />
        Needs decision
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
      <CircleDashed className="h-3 w-3" aria-hidden />
      Needs decision
    </span>
  );
}

function cardAccentClass(status?: string | null): string {
  if (status === "approved") return "border-l-4 border-l-emerald-500";
  if (status === "rejected") return "border-l-4 border-l-rose-400";
  return "border-l-4 border-l-amber-400/80";
}

function ReviewProgressStrip({ relief, rates }: { relief: ReviewCounts; rates: ReviewCounts }) {
  const total = relief.total + rates.total;
  const done = relief.approved + relief.rejected + rates.approved + rates.rejected;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Review progress</CardTitle>
        <CardDescription>
          {done} of {total} rows decided ┬╖ {pct}% complete
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          className="h-2 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Review progress"
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <p className="text-xs text-muted-foreground">Reliefs</p>
            <p className="font-medium">
              {relief.approved} approved ┬╖ {relief.rejected} rejected ┬╖ {relief.pending} left
            </p>
          </div>
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <p className="text-xs text-muted-foreground">Rates</p>
            <p className="font-medium">
              {rates.approved} approved ┬╖ {rates.rejected} rejected ┬╖ {rates.pending} left
            </p>
          </div>
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <p className="text-xs text-muted-foreground">Quick guide</p>
            <p className="text-muted-foreground">
              Reject if wrong. Otherwise use Quick approve ΓÇö defaults are fine for most demo rows.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function duplicateCopy(
  check?: { outcome?: string | null; corpus_hit?: string | null } | null,
): string {
  if (check?.corpus_hit) {
    return `Similar to ${humanId(check.corpus_hit)} already in catalog ΓÇö promote preview shows whether caps change.`;
  }
  if (!check?.outcome || check.outcome === "clear") {
    return "New draft extract.";
  }
  return humanId(check.outcome);
}

function previewMatchesLiveCatalog(preview: CatalogAdminPromotePreview): boolean {
  return preview.year_files_that_would_be_written.length === 0;
}

type PreviewSelectionRow = CatalogAdminPreviewGroup["before"][number];

function previewRowChanged(before: PreviewSelectionRow, after: PreviewSelectionRow): boolean {
  return (
    String(before.cap_amount ?? "") !== String(after.cap_amount ?? "") ||
    String(before.source_doc_id ?? "") !== String(after.source_doc_id ?? "") ||
    String(before.row_id ?? "") !== String(after.row_id ?? "")
  );
}

function formatPreviewCapValue(value: string | number | null | undefined): string {
  if (value == null || value === "") return "ΓÇö";
  const text = String(value).trim();
  if (/%$/.test(text)) return text;
  const n = Number(text.replace(/,/g, ""));
  if (Number.isFinite(n) && n >= 1000) return formatLkr(n);
  if (Number.isFinite(n) && n > 0 && n <= 100 && Number.isInteger(n)) return `${n}%`;
  return text;
}

function previewGroupHasChanges(group: CatalogAdminPreviewGroup): boolean {
  return group.before.some((before, index) => previewRowChanged(before, group.after[index]));
}

function countPreviewChangedYears(preview: CatalogAdminPromotePreview): number {
  const years = new Set<string>();
  for (const group of preview.groups) {
    group.before.forEach((before, index) => {
      if (previewRowChanged(before, group.after[index])) {
        years.add(before.assessment_year);
      }
    });
  }
  return years.size;
}

function gateChip(ok: boolean | undefined, yes: string, no: string) {
  return ok ? (
    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-900">
      {yes}
    </span>
  ) : (
    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-950">
      {no}
    </span>
  );
}

function AttributionTrail({
  provision,
  yearCtx,
}: {
  provision: CatalogAdminProvision | null | undefined;
  yearCtx?: CatalogYearContext;
}) {
  if (!provision) return null;
  const classifiedBy = provision.kind_set_by || null;
  const boundBy = provision.engine_binding_set_by || null;
  const approvedBy = provision.provenance?.reviewed_by || null;
  const names = [classifiedBy, boundBy, approvedBy].filter(Boolean);
  const differ = new Set(names).size > 1;
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer">Who decided this row</summary>
      <dl className="mt-2 space-y-1">
        <div>
          <dt className="inline">Year type ┬╖ </dt>
          <dd className="inline">
            {provision.kind_human ? (
              <>
                <strong>{kindDecisionLabel(provision.kind_human, provision, { yearCtx })}</strong>
                {classifiedBy ? ` ┬╖ ${classifiedBy}` : ""}
                {provision.kind_set_at ? ` ┬╖ ${formatWhen(provision.kind_set_at)}` : ""}
              </>
            ) : (
              "Not chosen yet"
            )}
          </dd>
        </div>
        <div>
          <dt className="inline">Tax effect ┬╖ </dt>
          <dd className="inline">
            {provision.engine_binding?.kind ? (
              <>
                <strong>{bindingLabel(provision.engine_binding.kind)}</strong>
                {boundBy ? ` ┬╖ ${boundBy}` : ""}
                {provision.engine_binding_set_at
                  ? ` ┬╖ ${formatWhen(provision.engine_binding_set_at)}`
                  : ""}
              </>
            ) : (
              "Not chosen yet"
            )}
          </dd>
        </div>
        <div>
          <dt className="inline">Approve or reject ┬╖ </dt>
          <dd className="inline">
            {approvedBy ? (
              <>
                <strong>{approvedBy}</strong>
                {provision.provenance?.reviewed_at
                  ? ` ┬╖ ${formatWhen(provision.provenance.reviewed_at)}`
                  : ""}
              </>
            ) : (
              "Not decided yet"
            )}
          </dd>
        </div>
        {differ ? (
          <p>Different people acted on year type, calculator rule, and approve for this row.</p>
        ) : null}
      </dl>
    </details>
  );
}

function KindButtons({
  provision,
  busy,
  onSet,
  yearCtx,
}: {
  provision: CatalogAdminProvision;
  busy: boolean;
  onSet: (kind: CatalogAdminKind) => void;
  yearCtx?: CatalogYearContext;
}) {
  const selected = provision.kind_human;
  const hint = derivedYearHint(provision, yearCtx);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Year</p>
      <p className="text-xs text-muted-foreground">
        Demo updates usually pick <strong>Update existing year</strong> (e.g. 2025/26). Quick
        approve uses that when nothing is selected yet.
      </p>
      {hint ? (
        <p className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-foreground">
          {hint}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={selected === "UPDATE" ? "default" : "outline"}
          disabled={busy}
          onClick={() => onSet("UPDATE")}
        >
          {kindDecisionLabel("UPDATE", provision, { yearCtx })}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={selected === "NEW_YEAR" ? "default" : "outline"}
          disabled={busy}
          onClick={() => onSet("NEW_YEAR")}
        >
          {kindDecisionLabel("NEW_YEAR", provision, { yearCtx })}
        </Button>
      </div>
    </div>
  );
}

function BindingPicker({
  row,
  busy,
  onSet,
}: {
  row: CatalogAdminReviewRow;
  busy: boolean;
  onSet: (kind: CatalogAdminEngineBindingKind, componentId?: string) => void;
}) {
  const current = row.engine_binding?.kind || "";
  const [pickingFiling, setPickingFiling] = useState(current === "filing_line");
  const [componentId, setComponentId] = useState(row.engine_binding?.component_id || "");
  const shown = pickingFiling ? "filing_line" : current;
  const recommendation = bindingRecommendation(row);
  return (
    <div className="space-y-2">
      <Label htmlFor={`binding-${row.entry_id}`}>Calculator rule</Label>
      <Select
        id={`binding-${row.entry_id}`}
        value={shown}
        disabled={busy || !row.included}
        onChange={(event) => {
          const next = event.target.value as CatalogAdminEngineBindingKind | "";
          if (next === "filing_line") {
            setPickingFiling(true);
            return;
          }
          setPickingFiling(false);
          if (next) onSet(next);
        }}
      >
        <option value="">Choose calculator ruleΓÇª</option>
        {BINDING_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      {recommendation && !current ? (
        <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          {recommendation}
        </p>
      ) : null}
      {pickingFiling ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[12rem] flex-1 space-y-1">
            <Label htmlFor={`component-${row.entry_id}`}>Calculator line</Label>
            <Input
              id={`component-${row.entry_id}`}
              value={componentId}
              disabled={busy}
              onChange={(event) => setComponentId(event.target.value)}
              placeholder="Required for a calculator filing line"
            />
          </div>
          <Button
            type="button"
            size="sm"
            disabled={busy || !componentId.trim()}
            onClick={() => onSet("filing_line", componentId.trim())}
          >
            Save calculator line
          </Button>
        </div>
      ) : null}
      {row.tax_effect ? (
        <p className="text-sm text-muted-foreground">{friendlyTaxEffectCopy(row.tax_effect)}</p>
      ) : null}
    </div>
  );
}

function QuestionFieldsEditor({
  row,
  busy,
  onSave,
}: {
  row: CatalogAdminReviewRow;
  busy: boolean;
  onSave: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
}) {
  const [displayName, setDisplayName] = useState(row.display_name || "");
  const [questionPrompt, setQuestionPrompt] = useState(row.question_prompt || "");
  const [inputKind, setInputKind] = useState(row.input_kind || "notice");
  const [helpText, setHelpText] = useState(row.help || "");
  const [groupId, setGroupId] = useState(
    row.catalog_compare_group_id ||
      row.suggested_compare_group_id ||
      row.compare_group_id ||
      "",
  );
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <p className="text-sm font-medium">Taxpayer-facing wording</p>
        <p className="text-xs text-muted-foreground">
          Edit before taxpayers see this relief. Cap and Act quote stay locked below.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor={`qn-name-${row.entry_id}`}>Display name</Label>
          <Input
            id={`qn-name-${row.entry_id}`}
            value={displayName}
            disabled={busy}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`qn-kind-${row.entry_id}`}>Input kind</Label>
          <Select
            id={`qn-kind-${row.entry_id}`}
            value={inputKind}
            disabled={busy}
            onChange={(event) => setInputKind(event.target.value)}
          >
            {QUESTION_INPUT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor={`qn-prompt-${row.entry_id}`}>Question shown to taxpayer</Label>
        <Input
          id={`qn-prompt-${row.entry_id}`}
          value={questionPrompt}
          disabled={busy}
          onChange={(event) => setQuestionPrompt(event.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`qn-help-${row.entry_id}`}>Help text</Label>
        <Input
          id={`qn-help-${row.entry_id}`}
          value={helpText}
          disabled={busy}
          onChange={(event) => setHelpText(event.target.value)}
          placeholder="Optional one-line help under the question"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`qn-group-${row.entry_id}`}>Suggested compare group</Label>
        <Input
          id={`qn-group-${row.entry_id}`}
          value={groupId}
          disabled={busy}
          onChange={(event) => setGroupId(event.target.value)}
          className="font-mono text-xs"
        />
        {row.suggested_compare_group_id &&
        row.suggested_compare_group_id !== (row.catalog_compare_group_id || "") ? (
          <p className="text-xs text-muted-foreground">
            Extract suggested {row.suggested_compare_group_id}
            {row.catalog_compare_group_id ? ` ΓåÆ maps to ${row.catalog_compare_group_id}` : ""}.
          </p>
        ) : null}
      </div>
      <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
        <p>
          Cap (verbatim): <span className="font-medium text-foreground">{formatRowCap(row)}</span>
        </p>
        <p className="mt-1">
          Quote locked. Reject the row if the quote or cap is wrong.
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        disabled={busy || !displayName.trim() || !questionPrompt.trim() || !groupId.trim()}
        onClick={() =>
          onSave({
            display_name: displayName.trim(),
            question_prompt: questionPrompt.trim(),
            input_kind: inputKind,
            help: helpText.trim(),
            compare_group_id: groupId.trim(),
          })
        }
      >
        Save taxpayer question
      </Button>
      {row.question_fields_set_by ? (
        <p className="text-xs text-muted-foreground">
          Saved by {row.question_fields_set_by}
          {row.question_fields_set_at ? ` ┬╖ ${formatWhen(row.question_fields_set_at)}` : ""}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          Showing the extract draft until you save an edit.
        </p>
      )}
    </div>
  );
}

function ClassificationBlock({ provision }: { provision: CatalogAdminProvision | null | undefined }) {
  if (!provision) {
    return (
      <p className="text-sm text-muted-foreground">This row is not included, so it cannot be classified.</p>
    );
  }
  const suggested =
    provision.kind_suggested === "NEW_YEAR"
      ? "create a new year"
      : provision.kind_suggested === "UPDATE"
        ? "update an existing year"
        : provision.kind_suggested
          ? humanId(provision.kind_suggested)
          : "no date was found";
  const ya = yearLabel(provision.derived_assessment_year);
  return (
    <div className="space-y-2">
      {provision.kind_human ? (
        <p className="text-sm">
          Chosen:{" "}
          <strong>
            {provision.kind_human === "NEW_YEAR" ? "Create a new year" : "Update existing year"}
          </strong>
          {provision.kind_suggested ? (
            <>
              {" "}
              (the extract suggested {suggested}
              {ya ? ` for ${ya}` : ""} ΓÇö that is not selected automatically).
            </>
          ) : null}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          Suggestion only: this looks like {suggested}
          {ya ? ` for ${ya}` : ""}. Nothing is selected until you choose.
        </p>
      )}
      {provision.commencement_quote ? (
        <blockquote className="border-l-2 pl-3 text-sm text-muted-foreground">
          {provision.commencement_quote}
          {provision.operation_date ? (
            <span className="mt-1 block text-xs">Starts {provision.operation_date}</span>
          ) : null}
        </blockquote>
      ) : null}
      {provision.note ? (
        <p className="text-sm text-amber-800 dark:text-amber-200">{provision.note}</p>
      ) : null}
    </div>
  );
}

function ReliefQuickActions({
  row,
  busy,
  provision,
  yearCtx,
  onReject,
  onClassify,
  onBind,
  onSaveQuestions,
  onQuickApprove,
}: {
  row: CatalogAdminReviewRow;
  busy: boolean;
  provision?: CatalogAdminProvision | null;
  yearCtx?: CatalogYearContext;
  onReject: () => void;
  onClassify: (kind: CatalogAdminKind) => void;
  onBind: (kind: CatalogAdminEngineBindingKind, componentId?: string) => void;
  onSaveQuestions: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
  onQuickApprove: () => void;
}) {
  const approved = row.decision_status === "approved";
  const rejected = row.decision_status === "rejected";
  const pending = !approved && !rejected;
  const kindLabel = kindDecisionLabel(provision?.kind_human, provision, {
    defaultSuffix: !provision?.kind_human,
    yearCtx,
  });
  const bindingKind = row.engine_binding?.kind || recommendedBindingKind(row);

  return (
    <div className="space-y-3 rounded-lg border bg-muted/25 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Your decision
      </p>
      {pending && provision ? (
        <KindButtons provision={provision} busy={busy} onSet={onClassify} yearCtx={yearCtx} />
      ) : null}
      {pending ? (
        <p className="rounded-md bg-background px-3 py-2 text-xs text-muted-foreground">
          <strong>Quick approve</strong> saves{" "}
          <strong>{kindLabel}</strong> ┬╖ <strong>{bindingOptionLabel(bindingKind)}</strong> ┬╖ keeps
          the LLM question draft as-is.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {!approved ? (
          <Button type="button" size="sm" variant={rejected ? "default" : "outline"} disabled={busy} onClick={onReject}>
            Reject
          </Button>
        ) : null}
        {pending ? (
          <Button type="button" size="sm" disabled={busy} onClick={onQuickApprove}>
            Quick approve
          </Button>
        ) : null}
      </div>
      {row.decision_status ? (
        <p className="text-xs text-muted-foreground">
          Status: <strong>{decisionLabel(row.decision_status)}</strong>
          {row.reviewed_by ? ` ┬╖ ${row.reviewed_by}` : ""}
        </p>
      ) : null}
      {pending ? (
        <details className="rounded-md border bg-background p-3 text-sm">
          <summary className="cursor-pointer font-medium">
            Optional: change calculator rule or taxpayer wording
          </summary>
          <div className="mt-3 space-y-4">
            <BindingPicker
              key={`${row.entry_id}-${row.engine_binding?.kind || "unset"}`}
              row={row}
              busy={busy}
              onSet={onBind}
            />
            <QuestionFieldsEditor
              key={`${row.entry_id}-${row.question_fields_set_at || "draft"}`}
              row={row}
              busy={busy}
              onSave={onSaveQuestions}
            />
          </div>
        </details>
      ) : approved ? (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium">What was saved for this row</summary>
          <div className="mt-2 space-y-1">
            <p>
              Year: <strong>{kindDecisionLabel(provision?.kind_human, provision, { yearCtx })}</strong>
            </p>
            <p>
              Calculator rule: <strong>{bindingOptionLabel(row.engine_binding?.kind)}</strong>
            </p>
            <p>
              Taxpayer question: <strong>{row.question_prompt || row.display_name}</strong>
            </p>
          </div>
        </details>
      ) : null}
    </div>
  );
}

function RateQuickActions({
  row,
  busy,
  provision,
  yearCtx,
  onReject,
  onClassify,
  onQuickApprove,
}: {
  row: CatalogAdminReviewRow;
  busy: boolean;
  provision?: CatalogAdminProvision | null;
  yearCtx?: CatalogYearContext;
  onReject: () => void;
  onClassify: (kind: CatalogAdminKind) => void;
  onQuickApprove: () => void;
}) {
  const approved = row.decision_status === "approved";
  const rejected = row.decision_status === "rejected";
  const pending = !approved && !rejected;
  const kindLabel = kindDecisionLabel(provision?.kind_human, provision, {
    defaultSuffix: !provision?.kind_human,
    yearCtx,
  });

  return (
    <div className="space-y-3 rounded-lg border bg-muted/25 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Your decision
      </p>
      {pending && provision ? (
        <KindButtons provision={provision} busy={busy} onSet={onClassify} yearCtx={yearCtx} />
      ) : null}
      {pending ? (
        <p className="rounded-md bg-background px-3 py-2 text-xs text-muted-foreground">
          <strong>Quick approve</strong> accepts this rate with <strong>{kindLabel}</strong>.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {!approved ? (
          <Button type="button" size="sm" variant={rejected ? "default" : "outline"} disabled={busy} onClick={onReject}>
            Reject
          </Button>
        ) : null}
        {pending ? (
          <Button type="button" size="sm" disabled={busy} onClick={onQuickApprove}>
            {row.approve_label?.includes("accept") ? "Quick accept" : "Quick approve"}
          </Button>
        ) : null}
      </div>
      {row.decision_status ? (
        <p className="text-xs text-muted-foreground">
          Status: <strong>{decisionLabel(row.decision_status)}</strong>
          {row.reviewed_by ? ` ┬╖ ${row.reviewed_by}` : ""}
        </p>
      ) : null}
    </div>
  );
}

function ReliefCard({
  row,
  busyId,
  yearCtx,
  onClassify,
  onBind,
  onSaveQuestions,
  onQuickApprove,
  onReject,
}: {
  row: CatalogAdminReviewRow;
  busyId: string | null;
  yearCtx?: CatalogYearContext;
  onClassify: (kind: CatalogAdminKind) => void;
  onBind: (kind: CatalogAdminEngineBindingKind, componentId?: string) => void;
  onSaveQuestions: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
  onQuickApprove: () => void;
  onReject: () => void;
}) {
  const busy = busyId === row.entry_id;
  const provision = row.classification;
  const rejected = row.decision_status === "rejected";
  const group = groupLabel(row);
  const capLabel =
    row.cap_amount != null && row.cap_amount !== "" ? formatRowCap(row) : null;
  const targetYa = yearLabel(provision?.derived_assessment_year);
  return (
    <article
      className={cn(
        "space-y-4 rounded-xl border bg-card p-5 shadow-sm",
        cardAccentClass(row.decision_status),
      )}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold leading-snug">
                {row.display_name || "Untitled relief"}
              </h3>
              {capLabel ? (
                <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  Cap {capLabel}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">
              {[
                row.section_ref,
                group,
                targetYa ? `Target YA ${targetYa}` : null,
                row.effective_from ? `From ${row.effective_from}` : null,
              ]
                .filter(Boolean)
                .join(" ┬╖ ") || "No section metadata"}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            {gateChip(row.quote_ok_full_doc, "Quote checked", "Quote not found")}
            {gateChip(row.pass2_verbatim, "Matches Act text", "Wording differs")}
            {decisionBadge(row.decision_status)}
          </div>
        </div>
        <ActQuoteBlock row={row} />
        {row.compare_group_mapped ? (
          <p className="text-xs text-muted-foreground">
            Updates the existing {group || "catalog"} card ΓÇö does not add a duplicate relief.
          </p>
        ) : null}
      </div>

      <ReliefQuickActions
        row={row}
        busy={busy}
        provision={provision}
        yearCtx={yearCtx}
        onReject={onReject}
        onClassify={onClassify}
        onBind={onBind}
        onSaveQuestions={onSaveQuestions}
        onQuickApprove={onQuickApprove}
      />

      {rejected ? (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-950 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-100">
          Rejected ΓÇö this relief will not be published. Use <strong>Quick approve</strong> to
          change your decision.
        </p>
      ) : null}

      <AttributionTrail provision={provision} yearCtx={yearCtx} />
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technical ids</summary>
        <p className="mt-2 font-mono break-all">
          {row.entry_id}
          {row.catalog_compare_group_id ? ` ┬╖ ${row.catalog_compare_group_id}` : ""}
          {row.extract_compare_group_id &&
          row.extract_compare_group_id !== row.catalog_compare_group_id
            ? ` ┬╖ extracted as ${row.extract_compare_group_id}`
            : ""}
        </p>
      </details>
    </article>
  );
}

function RateCard({
  row,
  busyId,
  yearCtx,
  onClassify,
  onQuickApprove,
  onReject,
}: {
  row: CatalogAdminReviewRow;
  busyId: string | null;
  yearCtx?: CatalogYearContext;
  onClassify: (kind: CatalogAdminKind) => void;
  onQuickApprove: () => void;
  onReject: () => void;
}) {
  const busy = busyId === row.entry_id;
  const provision = row.classification;
  const rejected = row.decision_status === "rejected";
  const band =
    row.lower != null || row.upper != null
      ? `${row.lower ?? "ΓÇö"} to ${row.upper ?? "ΓÇö"}`
      : null;
  const rate =
    row.rate_percent != null
      ? `${row.rate_percent}%`
      : row.value != null
        ? String(row.value)
        : null;
  const targetYa = yearLabel(provision?.derived_assessment_year);
  return (
    <article
      className={cn(
        "space-y-4 rounded-xl border bg-card p-5 shadow-sm",
        cardAccentClass(row.decision_status),
      )}
    >
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <h3 className="text-base font-semibold leading-snug">
              {row.display_name || row.description || "Rate row"}
              {rate ? (
                <span className="ml-2 rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  {rate}
                </span>
              ) : null}
            </h3>
            <p className="text-sm text-muted-foreground">
              {[
                row.section_ref,
                band,
                targetYa ? `Target YA ${targetYa}` : null,
                row.effective_from ? `From ${row.effective_from}` : null,
              ]
                .filter(Boolean)
                .join(" ┬╖ ") || "No band dates on this row."}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            {gateChip(row.quote_ok_full_doc, "Quote checked", "Quote not found")}
            {gateChip(row.pass2_verbatim, "Matches Act text", "Wording differs")}
            {decisionBadge(row.decision_status)}
          </div>
        </div>
        <ActQuoteBlock row={row} />
        {row.sole_check && row.decision_status !== "rejected" ? (
          <p className="text-xs text-muted-foreground">
            Check this band against the Act before quick approving.
          </p>
        ) : null}
      </div>
      <RateQuickActions
        row={row}
        busy={busy}
        provision={provision}
        yearCtx={yearCtx}
        onReject={onReject}
        onClassify={onClassify}
        onQuickApprove={onQuickApprove}
      />
      {rejected ? (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-950 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-100">
          Rejected ΓÇö this rate will not be published. Use <strong>Quick approve</strong> to change
          your decision.
        </p>
      ) : null}
      <AttributionTrail provision={provision} yearCtx={yearCtx} />
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technical ids</summary>
        <p className="mt-2 font-mono break-all">{row.entry_id}</p>
      </details>
    </article>
  );
}

function PromotePreviewSummary({ preview }: { preview: CatalogAdminPromotePreview }) {
  const writes = preview.year_files_that_would_be_written;
  const approvedWrites = writes.filter((path) => path.startsWith("approved/"));
  const rateWrites = writes.filter((path) => path.startsWith("rates/"));
  const changedGroups = preview.groups.filter(previewGroupHasChanges);
  const changedYears = countPreviewChangedYears(preview);
  const noFileWrites = writes.length === 0;

  return (
    <div className="space-y-3 rounded-md border bg-muted/30 p-4 text-sm">
      <p className="font-medium">Impact summary</p>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">Catalog files to write</dt>
          <dd className="font-medium">{writes.length || "none"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Relief groups with cap changes</dt>
          <dd className="font-medium">{changedGroups.length}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Assessment years affected</dt>
          <dd className="font-medium">{changedYears || "none"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Interview-only rows</dt>
          <dd className="font-medium">{preview.tax_inert_rows.length}</dd>
        </div>
      </dl>
      {preview.blocks_promote ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-destructive">
          Promote is blocked until known-table or rate ontology checks pass.
        </p>
      ) : null}
      {noFileWrites ? (
        <p className="text-muted-foreground">
          No approved/ or rates/ files would change on save. Review the per-year table below to
          confirm caps and winning acts match what you expect.
        </p>
      ) : (
        <div className="space-y-2">
          {approvedWrites.length ? (
            <div>
              <p className="text-xs font-medium text-muted-foreground">Relief catalog files</p>
              <ul className="mt-1 list-disc pl-5">
                {approvedWrites.map((path) => (
                  <li key={path}>{yearFileLabel(path)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {rateWrites.length ? (
            <div>
              <p className="text-xs font-medium text-muted-foreground">Rate rule files</p>
              <ul className="mt-1 list-disc pl-5">
                {rateWrites.map((path) => (
                  <li key={path}>{yearFileLabel(path)}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
      {preview.year_files_frozen.length ? (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium text-foreground">
            {preview.year_files_frozen.length} year file
            {preview.year_files_frozen.length === 1 ? "" : "s"} unchanged
          </summary>
          <p className="mt-2 break-words">
            {preview.year_files_frozen.map(yearFileLabel).join(" ┬╖ ")}
          </p>
        </details>
      ) : null}
    </div>
  );
}

function PromoteGroupDiffTable({ group }: { group: CatalogAdminPreviewGroup }) {
  const [showAllYears, setShowAllYears] = useState(false);
  const isRateRules = group.compare_group_id === "rate_rules";
  const rows = group.before.map((before, index) => ({
    assessment_year: before.assessment_year,
    before,
    after: group.after[index],
    changed: previewRowChanged(before, group.after[index]),
  }));
  const changedRows = rows.filter((row) => row.changed);
  const visibleRows = showAllYears || changedRows.length === 0 ? rows : changedRows;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {changedRows.length
            ? `${changedRows.length} year${changedRows.length === 1 ? "" : "s"} would change`
            : "No year-level changes for this group"}
        </p>
        {changedRows.length > 0 && changedRows.length < rows.length ? (
          <button
            type="button"
            className="text-xs font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => setShowAllYears((prev) => !prev)}
          >
            {showAllYears ? "Show changed years only" : `Show all ${rows.length} years`}
          </button>
        ) : null}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-xs">
          <thead>
            <tr className="border-b">
              <th className="py-1.5 pr-3 font-medium">Year</th>
              <th className="py-1.5 pr-3 font-medium">{isRateRules ? "Before act" : "Before cap"}</th>
              <th className="py-1.5 pr-3 font-medium">{isRateRules ? "After act" : "After cap"}</th>
              <th className="py-1.5 pr-3 font-medium">Winning row</th>
              <th className="py-1.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                key={row.assessment_year}
                className={row.changed ? "bg-amber-50/80 dark:bg-amber-950/20" : undefined}
              >
                <td className="py-1.5 pr-3 font-medium">{yearLabel(row.assessment_year)}</td>
                <td className="py-1.5 pr-3">
                  {isRateRules
                    ? humanId(row.before.source_doc_id) || "ΓÇö"
                    : formatPreviewCapValue(row.before.cap_amount)}
                </td>
                <td className="py-1.5 pr-3">
                  {isRateRules
                    ? humanId(row.after.source_doc_id) || "ΓÇö"
                    : formatPreviewCapValue(row.after.cap_amount)}
                </td>
                <td className="py-1.5 pr-3">{humanId(row.after.row_id) || "ΓÇö"}</td>
                <td className="py-1.5">
                  {row.changed ? (
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-medium text-amber-950 dark:bg-amber-900 dark:text-amber-50">
                      Changes
                    </span>
                  ) : (
                    <span className="text-muted-foreground">Same</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PromoteIncludedRowsSummary({
  rows,
  yearCtx,
}: {
  rows: CatalogAdminReviewRow[];
  yearCtx?: CatalogYearContext;
}) {
  const included = rows.filter((row) => row.included && row.decision_status === "approved");
  const views = dedupePromoteIncludedRows(included);
  const collapsedCount = included.length - views.length;
  if (!included.length) return null;

  return (
    <div className="space-y-2 rounded-md border p-3 text-sm">
      <p className="font-medium">Approved rows in this promote</p>
      {collapsedCount > 0 ? (
        <p className="text-xs text-muted-foreground">
          {collapsedCount} duplicate schedule row{collapsedCount === 1 ? "" : "s"} hidden ΓÇö the Act
          extract often repeats the same tax table under more than one schedule (e.g. First and
          Fifth).
        </p>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-left text-xs">
          <thead>
            <tr className="border-b">
              <th className="py-1.5 pr-3 font-medium">Relief / rate</th>
              <th className="py-1.5 pr-3 font-medium">Decision</th>
              <th className="py-1.5 pr-3 font-medium">Extracted value</th>
              <th className="py-1.5 font-medium">Role</th>
            </tr>
          </thead>
          <tbody>
            {views.map((view) => {
              const { row, mergedCount } = view;
              const kind = row.classification?.kind_human;
              const subLabel = promoteIncludedSubLabel(view);
              return (
                <tr key={row.entry_id} className="border-b border-border/50 last:border-0">
                  <td className="py-1.5 pr-3">
                    <span className="font-medium">{row.display_name || humanId(row.entry_id)}</span>
                    {mergedCount > 1 ? (
                      <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        ├ù{mergedCount} schedules
                      </span>
                    ) : null}
                    {subLabel ? (
                      <span className="mt-0.5 block text-muted-foreground">{subLabel}</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 pr-3">
                    {kindDecisionLabel(kind, row.classification, { yearCtx })}
                  </td>
                  <td className="py-1.5 pr-3">{formatRowExtractedValue(row)}</td>
                  <td className="py-1.5">{formatRowTaxEngineLabel(row)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NewYearPreviewNote({
  rows,
  suggestedNewYear,
  yearCtx,
}: {
  rows: CatalogAdminReviewRow[];
  suggestedNewYear?: string | null;
  yearCtx?: CatalogYearContext;
}) {
  const newYearRows = rows.filter(
    (row) =>
      row.included &&
      row.decision_status === "approved" &&
      row.classification?.kind_human === "NEW_YEAR",
  );
  if (!newYearRows.length && !suggestedNewYear) return null;

  return (
    <div className="rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-950 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-100">
      <p className="font-medium">Create a new year (separate from update preview)</p>
      <p className="mt-1">
        The table above simulates <strong>Save updates to existing years</strong> only. Rows marked
        Create a new year apply when you use <strong>Save as a new year</strong>
        {suggestedNewYear ? ` (YA ${yearLabel(suggestedNewYear)})` : ""}.
      </p>
      {newYearRows.length ? (
        <ul className="mt-2 list-disc pl-5">
          {newYearRows.map((row) => (
            <li key={row.entry_id}>
              {row.display_name || humanId(row.entry_id)} ΓÇö{" "}
              {kindDecisionLabel("NEW_YEAR", row.classification, { yearCtx })} ┬╖ cap{" "}
              {formatRowCap(row)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function RatePanelPreview({
  ratePanel,
}: {
  ratePanel: CatalogAdminPromotePreview["rate_panel"];
}) {
  const diffs = ratePanel?.ontology_diffs ?? [];
  if (!diffs.length) return null;

  return (
    <div className="space-y-2 rounded-md border p-3 text-sm">
      <p className="font-medium">Rate ontology changes</p>
      {ratePanel?.ontology_blocks ? (
        <p className="text-destructive">Ontology mismatch blocks promote until resolved.</p>
      ) : null}
      <ul className="space-y-2">
        {diffs.map((item) => (
          <li key={item.assessment_year} className="rounded-md border bg-muted/20 p-2 text-xs">
            <p className="font-medium">{yearLabel(item.assessment_year)}</p>
            {item.match ? (
              <p className="text-muted-foreground">Matches live rate ontology.</p>
            ) : (
              <ul className="mt-1 list-disc pl-5">
                {(item.diffs ?? []).map((diff) => (
                  <li key={diff}>{diff}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CatalogAdminReviewPage() {
  const { sourceDocId } = useParams<{ sourceDocId: string }>();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [harvestBusy, setHarvestBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [promoteBusy, setPromoteBusy] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [newYearAck, setNewYearAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<CatalogAdminPromotePreview | null>(null);
  const [gapAcks, setGapAcks] = useState<Record<string, boolean>>({});
  const [ackFingerprint, setAckFingerprint] = useState<string | null>(null);
  const [promoteResult, setPromoteResult] = useState<CatalogAdminPromoteResult | null>(null);
  const reviewQuery = useQuery({
    queryKey: ["catalog-admin", "proposed", sourceDocId],
    queryFn: () => getCatalogAdminProposal(sourceDocId as string),
    enabled: Boolean(sourceDocId),
    retry: false,
  });
  const data = reviewQuery.data;
  const classification = data?.proposal.classification;
  const provisions = classification?.provisions ?? [];
  const fallbackRows = provisions.map(provisionAsRow);
  const hasApiRows =
    (data?.relief_rows?.length ?? 0) +
      (data?.rate_rows?.length ?? 0) +
      (data?.other_rows?.length ?? 0) >
    0;
  const reliefRows = hasApiRows
    ? (data?.relief_rows ?? [])
    : fallbackRows.filter((row) => row.panel === "relief");
  const rateRows = hasApiRows
    ? (data?.rate_rows ?? [])
    : fallbackRows.filter((row) => row.panel === "rate");
  const otherRows = hasApiRows
    ? (data?.other_rows ?? [])
    : fallbackRows.filter((row) => row.panel === "other");
  const extractIncluded = data?.proposal.included_count;
  const reliefCounts = useMemo(() => countReviewRows(reliefRows), [reliefRows]);
  const rateCounts = useMemo(() => countReviewRows(rateRows), [rateRows]);
  const yearCtx = useMemo<CatalogYearContext>(
    () => ({
      liveYas: classification?.live_confirmed_yas ?? [],
      maxInScopeYa: classification?.max_in_scope_ya ?? null,
    }),
    [classification?.live_confirmed_yas, classification?.max_in_scope_ya],
  );

  const acksForPreview = useMemo(() => {
    if (!preview) return {};
    if (preview.preview_fingerprint !== ackFingerprint) return {};
    return gapAcks;
  }, [preview, ackFingerprint, gapAcks]);

  const gapGroups = preview
    ? (preview.needs_gap_ack_group_ids ??
      preview.groups.filter((group) => group.needs_gap_ack).map((group) => group.compare_group_id))
    : [];
  const canPromote = Boolean(
    data?.promote_enabled &&
      preview &&
      !preview.blocks_promote &&
      gapGroups.every((group) => acksForPreview[group]),
  );

  async function quickApproveReliefRow(row: CatalogAdminReviewRow): Promise<void> {
    if (!sourceDocId) return;
    setBusyId(row.entry_id);
    setError(null);
    try {
      if (!row.classification?.kind_human) {
        await setCatalogAdminClassification(sourceDocId, row.entry_id, "UPDATE");
      }
      if (!row.engine_binding?.kind) {
        await setCatalogAdminEngineBinding(
          sourceDocId,
          row.entry_id,
          recommendedBindingKind(row),
        );
      }
      await approveCatalogAdminRow(sourceDocId, row.entry_id);
      await reviewQuery.refetch();
      setPreview(null);
      setGapAcks({});
      setAckFingerprint(null);
      setPromoteResult(null);
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function quickApproveRateRow(row: CatalogAdminReviewRow): Promise<void> {
    if (!sourceDocId) return;
    setBusyId(row.entry_id);
    setError(null);
    try {
      if (!row.classification?.kind_human) {
        await setCatalogAdminClassification(sourceDocId, row.entry_id, "UPDATE");
      }
      await approveCatalogAdminRow(sourceDocId, row.entry_id, {
        soleCheck: Boolean(row.sole_check),
      });
      await reviewQuery.refetch();
      setPreview(null);
      setGapAcks({});
      setAckFingerprint(null);
      setPromoteResult(null);
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function applyReview(
    run: () => Promise<CatalogAdminProposalReview>,
    rowId?: string,
  ): Promise<void> {
    if (rowId) setBusyId(rowId);
    setError(null);
    try {
      await run();
      await reviewQuery.refetch();
      setPreview(null);
      setGapAcks({});
      setAckFingerprint(null);
      setPromoteResult(null);
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function onHarvest(): Promise<void> {
    if (!sourceDocId) return;
    setHarvestBusy(true);
    setError(null);
    try {
      await runCatalogAdminHarvest(sourceDocId);
      await reviewQuery.refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Harvest failed.");
    } finally {
      setHarvestBusy(false);
    }
  }

  async function onPreview(): Promise<void> {
    if (!sourceDocId) return;
    setPreviewBusy(true);
    setError(null);
    try {
      const next = await previewCatalogAdminPromote(sourceDocId);
      if (next.preview_fingerprint !== ackFingerprint) {
        setGapAcks({});
        setAckFingerprint(next.preview_fingerprint);
      }
      setPreview(next);
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function onPromote(): Promise<void> {
    if (!sourceDocId || !preview) return;
    setPromoteBusy(true);
    setError(null);
    try {
      const acked = Object.entries(acksForPreview)
        .filter(([, checked]) => checked)
        .map(([group]) => group);
      const result = await promoteCatalogAdminUpdate(
        sourceDocId,
        preview.preview_fingerprint,
        acked,
      );
      setPromoteResult(result);
      await reviewQuery.refetch();
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setPromoteBusy(false);
    }
  }

  async function onConfirmNewYear(): Promise<void> {
    if (!sourceDocId || !data?.suggested_new_year) return;
    setConfirmBusy(true);
    setError(null);
    try {
      await confirmCatalogAdminNewYear(sourceDocId, data.suggested_new_year);
      setNewYearAck(false);
      await reviewQuery.refetch();
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onPromoteNewYear(): Promise<void> {
    if (!sourceDocId) return;
    setPromoteBusy(true);
    setError(null);
    try {
      const result = await promoteCatalogAdminNewYear(sourceDocId);
      setPromoteResult(result);
      await reviewQuery.refetch();
    } catch (err) {
      setError(catalogAdminActionError(err));
    } finally {
      setPromoteBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {reviewQuery.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {reviewQuery.error instanceof Error
            ? reviewQuery.error.message
            : "This Act could not be loaded."}
        </p>
      ) : reviewQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading this ActΓÇª</p>
      ) : data ? (
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FileText className="h-5 w-5" aria-hidden />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <h2 className="text-xl font-semibold leading-snug">
                  {data.proposal.act_title?.trim() ||
                    data.proposal.act_identity?.label ||
                    (data.proposal.act_identity?.act_no
                      ? `Act No. ${data.proposal.act_identity.act_no} of ${data.proposal.act_identity.act_year}`
                      : "Review this Act")}
                </h2>
                {data.proposal.act_title?.trim() && data.proposal.act_identity?.act_no ? (
                  <p className="text-sm text-muted-foreground">
                    Act No. {data.proposal.act_identity.act_no} of{" "}
                    {data.proposal.act_identity.act_year}
                  </p>
                ) : null}
                <p className="text-sm text-muted-foreground">
                  {reliefCounts.total + rateCounts.total} rows extracted
                  {reliefCounts.pending + rateCounts.pending > 0
                    ? ` ┬╖ ${reliefCounts.pending + rateCounts.pending} still need a decision`
                    : " ┬╖ all rows decided"}
                </p>
              </div>
            </div>
          </div>

          <ReviewProgressStrip relief={reliefCounts} rates={rateCounts} />

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">About this upload</CardTitle>
              <CardDescription>
                Extracted {formatWhen(data.proposal.extracted_at) || "date unknown"} ┬╖{" "}
                {duplicateCopy(data.proposal.duplicate_check)}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.proposal.act_identity?.quote ? (
                <blockquote className="rounded-lg border-l-4 border-muted-foreground/30 bg-muted/40 px-4 py-3 text-sm leading-relaxed">
                  {data.proposal.act_identity.quote}
                </blockquote>
              ) : null}
              {data.proposal.duplicate_check?.corpus_hit ? (
                <p className="text-sm text-muted-foreground">
                  Extract ran as a new draft. The live catalog file is unchanged until you
                  promote ΓÇö preview below shows if caps already match.
                </p>
              ) : null}
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer font-medium">Technical details</summary>
                <div className="mt-2 space-y-1 break-all font-mono">
                  <p>source {data.source_doc_id}</p>
                  <p>text {data.proposal.text_sha256 || "ΓÇö"}</p>
                  {data.proposal.tables_sha256 ? (
                    <p>tables {data.proposal.tables_sha256}</p>
                  ) : null}
                  {data.proposal.pdf_sha256 ? <p>pdf {data.proposal.pdf_sha256}</p> : null}
                  {data.proposal.job_id ? <p>job {data.proposal.job_id}</p> : null}
                </div>
              </details>
            </CardContent>
          </Card>

          {classification ? (
            <details className="group rounded-xl border bg-card shadow-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
                <div className="flex items-start gap-3">
                  <Calendar className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div>
                    <p className="font-semibold">When this ActΓÇÖs rules take effect</p>
                    <p className="text-sm text-muted-foreground">
                      {classification.harvest_record_count ?? 0} commencement date
                      {(classification.harvest_record_count ?? 0) === 1 ? "" : "s"} found
                      {(classification.pages_scanned ?? 0) > 0
                        ? ` across ${classification.pages_scanned} pages`
                        : ""}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-muted-foreground group-open:hidden">Show</span>
              </summary>
              <div className="space-y-3 border-t px-5 py-4 text-sm">
                <p className="text-muted-foreground">
                  Commencement dates from the PDF ΓÇö not taxpayer income dates. They suggest
                  update vs new year; you still choose when you accept a row.
                </p>
                {(classification.harvest_notes ?? []).length > 0 ? (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                    {(classification.harvest_notes ?? []).map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={harvestBusy}
                  onClick={() => void onHarvest()}
                >
                  {harvestBusy ? "Re-readingΓÇª" : "Re-scan this PDF"}
                </Button>
              </div>
            </details>
          ) : (
            <Card className="border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Commencement dates not scanned yet</CardTitle>
                <CardDescription className="text-amber-950 dark:text-amber-100">
                  Year-type suggestions on each row may be missing until you scan the PDF.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={harvestBusy}
                  onClick={() => void onHarvest()}
                >
                  {harvestBusy ? "Reading datesΓÇª" : "Find commencement dates"}
                </Button>
              </CardContent>
            </Card>
          )}

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <section className="space-y-4">
            <div className="space-y-1 border-b border-border pb-3">
              <h3 className="text-lg font-semibold">Reliefs extracted from this Act</h3>
              <p className="text-sm text-muted-foreground">
                Skim the Act quote, pick the year if needed, then click{" "}
                <strong>Quick approve</strong> on each row you accept.
              </p>
            </div>
            {reliefRows.length === 0 ? (
              <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
                No relief rows were extracted from this PDF.
                {extractIncluded != null
                  ? ` The extract included ${extractIncluded} other row${
                      extractIncluded === 1 ? "" : "s"
                    }.`
                  : ""}
              </p>
            ) : (
              groupRowsBySection(reliefRows).map((section) => (
                <div key={section.title} className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="text-sm font-semibold">{section.title}</h4>
                    <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                      {section.rows.length} row{section.rows.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  {section.rows.map((row) => (
                    <ReliefCard
                      key={`${row.entry_id}-${row.decision_status ?? "open"}`}
                      row={row}
                      busyId={busyId}
                      yearCtx={yearCtx}
                      onClassify={(kind) =>
                        void applyReview(
                          () =>
                            setCatalogAdminClassification(
                              sourceDocId as string,
                              row.entry_id,
                              kind,
                            ),
                          row.entry_id,
                        )
                      }
                      onBind={(kind, componentId) =>
                        void applyReview(
                          () =>
                            setCatalogAdminEngineBinding(
                              sourceDocId as string,
                              row.entry_id,
                              kind,
                              componentId,
                            ),
                          row.entry_id,
                        )
                      }
                      onSaveQuestions={(fields) =>
                        void applyReview(
                          () =>
                            setCatalogAdminQuestionFields(
                              sourceDocId as string,
                              row.entry_id,
                              fields,
                            ),
                          row.entry_id,
                        )
                      }
                      onQuickApprove={() => void quickApproveReliefRow(row)}
                      onReject={() =>
                        void applyReview(
                          () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                          row.entry_id,
                        )
                      }
                    />
                  ))}
                </div>
              ))
            )}
          </section>

          <section className="space-y-3">
            <div className="space-y-1">
              <h3 className="text-base font-semibold">Tax rates</h3>
              <p className="text-sm text-muted-foreground">
                Rate bands and special rules extracted from this Act.
              </p>
            </div>
            {data.rate_panel?.banner ? (
              <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
                {data.rate_panel.banner}
              </p>
            ) : null}
            {(data.rate_panel?.ontology_diffs ?? []).map((diff) => (
              <p key={diff.assessment_year} className="text-sm">
                Ontology {yearLabel(diff.assessment_year)}:{" "}
                {diff.match ? "matches the known table" : (diff.diffs ?? []).join("; ")}
              </p>
            ))}
            {rateRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No tax-rate rows were extracted from this PDF.
              </p>
            ) : (
              rateRows.map((row) => (
                <RateCard
                  key={`${row.entry_id}-${row.decision_status ?? "open"}`}
                  row={row}
                  busyId={busyId}
                  yearCtx={yearCtx}
                  onClassify={(kind) =>
                    void applyReview(
                      () =>
                        setCatalogAdminClassification(sourceDocId as string, row.entry_id, kind),
                      row.entry_id,
                    )
                  }
                  onQuickApprove={() => void quickApproveRateRow(row)}
                  onReject={() =>
                    void applyReview(
                      () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                      row.entry_id,
                    )
                  }
                />
              ))
            )}
          </section>

          {otherRows.length > 0 ? (
            <section className="space-y-3">
              <h3 className="text-sm font-medium">Other extracted items</h3>
              {otherRows.map((row) => (
                <RateCard
                  key={`${row.entry_id}-${row.decision_status ?? "open"}`}
                  row={row}
                  busyId={busyId}
                  yearCtx={yearCtx}
                  onClassify={(kind) =>
                    void applyReview(
                      () =>
                        setCatalogAdminClassification(sourceDocId as string, row.entry_id, kind),
                      row.entry_id,
                    )
                  }
                  onQuickApprove={() => void quickApproveRateRow(row)}
                  onReject={() =>
                    void applyReview(
                      () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                      row.entry_id,
                    )
                  }
                />
              ))}
            </section>
          ) : null}

          {provisions.length === 0 && classification && reliefRows.length === 0 && rateRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing to classify on this extract yet.
            </p>
          ) : null}

          {data.has_new_year_rows ? (
            <section className="space-y-3 rounded-lg border bg-card p-5">
              <h3 className="text-base font-semibold">Create a new year file</h3>
              <p className="text-sm">
                {data.new_year_confirm_message ||
                  "This Act looks like it starts a new assessment year. Confirm before creating empty year files."}
              </p>
              <p className="text-xs text-muted-foreground">
                This is separate from choosing ΓÇ£Create a new yearΓÇ¥ on a relief. It does not add
                the year to the taxpayer interview.
              </p>
              {data.new_year_confirmed ? (
                <p className="text-sm">
                  Confirmed year {yearLabel(data.proposal.proposed_for_assessment_year)}
                  {data.proposal.proposed_year_set_by
                    ? ` ┬╖ ${data.proposal.proposed_year_set_by}`
                    : ""}
                  .
                </p>
              ) : (
                <>
                  <label className="flex items-start gap-2 text-sm">
                    <Checkbox
                      checked={newYearAck}
                      onChange={(event) => setNewYearAck(event.target.checked)}
                    />
                    <span>
                      I confirm creating empty year files for{" "}
                      {yearLabel(data.suggested_new_year) || data.suggested_new_year}.
                    </span>
                  </label>
                  <Button
                    type="button"
                    disabled={
                      confirmBusy || !newYearAck || !data.suggested_new_year
                    }
                    onClick={() => void onConfirmNewYear()}
                  >
                    {confirmBusy ? "Creating filesΓÇª" : "Confirm new year file"}
                  </Button>
                </>
              )}
            </section>
          ) : null}

          <section className="space-y-3 rounded-lg border bg-card p-5">
            <h3 className="text-base font-semibold">See what would change</h3>
            <p className="text-sm text-muted-foreground">
              Preview only. Nothing is written until you save below.
            </p>
            <Button
              type="button"
              variant="outline"
              disabled={previewBusy || !data.preview_ready}
              onClick={() => void onPreview()}
            >
              {previewBusy ? "Building previewΓÇª" : "Preview changes"}
            </Button>
            {!data.preview_ready ? (
              <p className="text-sm text-muted-foreground">{data.promote_blocked_reason}</p>
            ) : null}
            {preview ? (
              <div className="space-y-4">
                <PromotePreviewSummary preview={preview} />
                {previewMatchesLiveCatalog(preview) ? (
                  <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100">
                    <p className="font-medium">Already in the system</p>
                    <p className="mt-1">
                      Before and after caps match the live catalog. Extraction and review still
                      ran; saving would not change year files.
                    </p>
                  </div>
                ) : null}
                <PromoteIncludedRowsSummary
                  rows={[...reliefRows, ...rateRows]}
                  yearCtx={yearCtx}
                />
                <NewYearPreviewNote
                  rows={reliefRows}
                  suggestedNewYear={data.suggested_new_year}
                  yearCtx={yearCtx}
                />
                {(preview.engine_year_notes ?? []).length > 0
                  ? preview.engine_year_notes!.map((note) => (
                      <p key={note.assessment_year} className="text-sm">
                        {note.message}
                      </p>
                    ))
                  : preview.engine_year_note ? (
                      <p className="text-sm">{preview.engine_year_note}</p>
                    ) : null}
                {preview.tax_inert_rows.length ? (
                  <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40">
                    <p className="font-medium">Shown in interview, does not change tax</p>
                    <ul className="mt-1 list-disc pl-5">
                      {preview.tax_inert_rows.map((row) => (
                        <li key={row.entry_id}>
                          {row.display_name || row.entry_id} ΓÇö {row.note}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <RatePanelPreview ratePanel={preview.rate_panel} />
                {preview.groups.map((group) => (
                  <article key={group.compare_group_id} className="space-y-2 rounded-md border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-sm font-medium">{humanId(group.compare_group_id)}</h4>
                      {previewGroupHasChanges(group) ? (
                        <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-medium text-amber-950 dark:bg-amber-900 dark:text-amber-50">
                          Has changes
                        </span>
                      ) : (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                          Unchanged
                        </span>
                      )}
                    </div>
                    {group.compare_group_mapped ? (
                      <p className="text-xs text-muted-foreground">
                        This updates the existing catalog card, not a new relief.
                      </p>
                    ) : null}
                    {group.gap_banner ? <p className="text-sm">{group.gap_banner}</p> : null}
                    {group.needs_gap_ack ? (
                      <label className="flex items-start gap-2 text-sm">
                        <Checkbox
                          checked={Boolean(acksForPreview[group.compare_group_id])}
                          onChange={(event) => {
                            setAckFingerprint(preview.preview_fingerprint);
                            setGapAcks((prev) => ({
                              ...prev,
                              [group.compare_group_id]: event.target.checked,
                            }));
                          }}
                        />
                        <span>
                          I acknowledge there is no independent table check for{" "}
                          {humanId(group.compare_group_id)}.
                        </span>
                      </label>
                    ) : null}
                    <PromoteGroupDiffTable group={group} />
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={promoteBusy || !canPromote}
              onClick={() => void onPromote()}
            >
              {promoteBusy ? "SavingΓÇª" : "Save updates to existing years"}
            </Button>
            {data.has_new_year_rows ? (
              <Button
                type="button"
                disabled={promoteBusy || !data.new_year_promote_enabled}
                onClick={() => void onPromoteNewYear()}
              >
                {promoteBusy ? "SavingΓÇª" : "Save as a new year"}
              </Button>
            ) : null}
            {error ? (
              <p className="w-full text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : promoteResult?.promotion ? (
              <p className="w-full text-sm">
                Saved. Updated{" "}
                {(promoteResult.promotion.written ?? []).map(yearFileLabel).join(", ") || "no year files"}.
                {promoteIndexRefreshNote(promoteResult.promotion.index_refresh)}
              </p>
            ) : canPromote ? (
              <p className="text-sm text-muted-foreground">
                Ready. This writes the years listed in the preview.
              </p>
            ) : data.has_new_year_rows && !data.new_year_promote_enabled ? (
              <p className="text-sm text-muted-foreground">
                {data.new_year_promote_blocked_reason}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">{data.promote_blocked_reason}</p>
            )}
          </div>
        </div>
      ) : null}

      <Link
        className="inline-block text-sm text-primary underline-offset-4 hover:underline"
        to="/adaptive-tax/catalog-admin"
      >
        Back to queue
      </Link>
    </div>
  );
}
