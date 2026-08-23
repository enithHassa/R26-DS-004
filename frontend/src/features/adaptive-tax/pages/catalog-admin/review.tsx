import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  approveCatalogAdminRow,
  confirmCatalogAdminNewYear,
  flagCatalogAdminRow,
  getCatalogAdminProposal,
  previewCatalogAdminPromote,
  promoteCatalogAdminNewYear,
  promoteCatalogAdminUpdate,
  rejectCatalogAdminRow,
  runCatalogAdminHarvest,
  setCatalogAdminClassification,
  setCatalogAdminEngineBinding,
  type CatalogAdminEngineBindingKind,
  type CatalogAdminKind,
  type CatalogAdminPromotePreview,
  type CatalogAdminPromoteResult,
  type CatalogAdminProposalReview,
  type CatalogAdminProvision,
  type CatalogAdminReviewRow,
} from "./api";
import { formatLkr } from "../../format-lkr";
import { CATALOG_HONESTY_COPY } from "../relief-interview/catalog-estimate-card";

function catalogAdminActionError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Request failed.";
  if (/HTTP 404|Not Found/i.test(msg)) {
    return (
      `${msg} Adaptive Tax is still the old process (classification works, ` +
      `tax-effect / approve do not). Stop the :8006 uvicorn fully and start it again — ` +
      `--reload does not pick up the new engine-binding routes.`
    );
  }
  return msg;
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
      ? "Tax effect not chosen — approve is blocked until you choose how this affects tax."
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
  { value: "none", label: "Show in interview, do not change tax" },
  { value: "solar_panel_relief", label: "Solar panel relief" },
  { value: "rent_relief", label: "Rental income relief" },
  { value: "senior_citizen_interest_relief", label: "Senior citizen interest relief" },
  { value: "qualifying_payments", label: "Qualifying payments" },
  { value: "donations", label: "Donations" },
  { value: "filing_line", label: "Calculator filing line" },
];

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatRowCap(row: CatalogAdminReviewRow): string {
  const raw = row.cap_amount;
  if (raw == null || raw === "") return "—";
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

function decisionLabel(status?: string | null): string {
  if (status === "approved") return "Approved";
  if (status === "rejected") return "Rejected";
  if (status === "flagged") return "Re-extract requested";
  return status ? humanId(status) : "";
}

function duplicateCopy(outcome?: string | null): string {
  if (!outcome || outcome === "clear") {
    return "Not a duplicate of an Act already in the catalog.";
  }
  return humanId(outcome);
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

function AttributionTrail({ provision }: { provision: CatalogAdminProvision | null | undefined }) {
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
          <dt className="inline">Year type · </dt>
          <dd className="inline">
            {provision.kind_human ? (
              <>
                <strong>
                  {provision.kind_human === "NEW_YEAR"
                    ? "Create a new year"
                    : "Update existing year"}
                </strong>
                {classifiedBy ? ` · ${classifiedBy}` : ""}
                {provision.kind_set_at ? ` · ${formatWhen(provision.kind_set_at)}` : ""}
              </>
            ) : (
              "Not chosen yet"
            )}
          </dd>
        </div>
        <div>
          <dt className="inline">Tax effect · </dt>
          <dd className="inline">
            {provision.engine_binding?.kind ? (
              <>
                <strong>{bindingLabel(provision.engine_binding.kind)}</strong>
                {boundBy ? ` · ${boundBy}` : ""}
                {provision.engine_binding_set_at
                  ? ` · ${formatWhen(provision.engine_binding_set_at)}`
                  : ""}
              </>
            ) : (
              "Not chosen yet"
            )}
          </dd>
        </div>
        <div>
          <dt className="inline">Approve or reject · </dt>
          <dd className="inline">
            {approvedBy ? (
              <>
                <strong>{approvedBy}</strong>
                {provision.provenance?.reviewed_at
                  ? ` · ${formatWhen(provision.provenance.reviewed_at)}`
                  : ""}
              </>
            ) : (
              "Not decided yet"
            )}
          </dd>
        </div>
        {differ ? (
          <p>Different people acted on year type, tax effect, and approve for this row.</p>
        ) : null}
      </dl>
    </details>
  );
}

function KindButtons({
  provision,
  busy,
  onSet,
}: {
  provision: CatalogAdminProvision;
  busy: boolean;
  onSet: (kind: CatalogAdminKind) => void;
}) {
  const selected = provision.kind_human;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Does this change an existing year, or start a new year?</p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={selected === "UPDATE" ? "default" : "outline"}
          disabled={busy}
          onClick={() => onSet("UPDATE")}
        >
          Update existing year
        </Button>
        <Button
          type="button"
          size="sm"
          variant={selected === "NEW_YEAR" ? "default" : "outline"}
          disabled={busy}
          onClick={() => onSet("NEW_YEAR")}
        >
          Create a new year
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
  return (
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <Label htmlFor={`binding-${row.entry_id}`}>How should this affect tax?</Label>
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
        <option value="">Choose tax effect…</option>
        {BINDING_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
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
      {row.tax_effect ? <p className="text-sm text-muted-foreground">{row.tax_effect}</p> : null}
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
              {ya ? ` for ${ya}` : ""} — that is not selected automatically).
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

function RowActions({
  row,
  busy,
  onApprove,
  onReject,
  onFlag,
}: {
  row: CatalogAdminReviewRow;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onFlag: () => void;
}) {
  const approved = row.decision_status === "approved";
  const rejected = row.decision_status === "rejected";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={approved ? "default" : "outline"}
          disabled={busy || !row.can_approve}
          onClick={onApprove}
        >
          {row.approve_label || "Approve"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={rejected ? "default" : "outline"}
          disabled={busy}
          onClick={onReject}
        >
          Reject
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onFlag}>
          Ask to re-extract
        </Button>
      </div>
      {row.decision_status ? (
        <p className="text-xs text-muted-foreground">
          Status: <strong>{decisionLabel(row.decision_status)}</strong>
          {row.reviewed_by ? ` · ${row.reviewed_by}` : ""}
        </p>
      ) : null}
      {!row.can_approve && row.approve_blocked_reason ? (
        <p className="text-xs text-amber-800 dark:text-amber-200">{row.approve_blocked_reason}</p>
      ) : null}
    </div>
  );
}

function ReliefCard({
  row,
  busyId,
  onClassify,
  onBind,
  onApprove,
  onReject,
  onFlag,
}: {
  row: CatalogAdminReviewRow;
  busyId: string | null;
  onClassify: (kind: CatalogAdminKind) => void;
  onBind: (kind: CatalogAdminEngineBindingKind, componentId?: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onFlag: () => void;
}) {
  const busy = busyId === row.entry_id;
  const provision = row.classification;
  const group = groupLabel(row);
  const meta = [
    row.section_ref,
    group,
    row.cap_amount != null && row.cap_amount !== "" ? `Cap ${formatRowCap(row)}` : null,
    row.effective_from ? `From ${row.effective_from}` : null,
  ].filter(Boolean);
  return (
    <article className="space-y-4 rounded-lg border bg-card p-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <h3 className="text-base font-semibold leading-snug">
              {row.display_name || "Untitled relief"}
            </h3>
            {meta.length ? (
              <p className="text-sm text-muted-foreground">{meta.join(" · ")}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            {gateChip(row.quote_ok_full_doc, "Quote checked", "Quote not found")}
            {gateChip(row.pass2_verbatim, "Matches Act text", "Wording differs")}
            {row.included ? (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Included
              </span>
            ) : (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Skipped
              </span>
            )}
            {row.decision_status ? (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">
                {decisionLabel(row.decision_status)}
              </span>
            ) : null}
          </div>
        </div>
        {row.quote ? (
          <blockquote className="rounded-md bg-muted/50 p-3 text-sm leading-relaxed">
            {row.quote}
          </blockquote>
        ) : (
          <p className="text-sm text-muted-foreground">No Act quote on this row.</p>
        )}
        {row.compare_group_mapped ? (
          <p className="text-xs text-muted-foreground">
            This updates the existing {group || "catalog"} card — it does not add a second relief.
          </p>
        ) : null}
      </div>
      <ClassificationBlock provision={provision} />
      {provision ? (
        <KindButtons provision={provision} busy={busy} onSet={onClassify} />
      ) : null}
      <BindingPicker
        key={`${row.entry_id}-${row.engine_binding?.kind || "unset"}`}
        row={row}
        busy={busy}
        onSet={onBind}
      />
      <RowActions
        row={row}
        busy={busy}
        onApprove={onApprove}
        onReject={onReject}
        onFlag={onFlag}
      />
      <AttributionTrail provision={provision} />
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technical ids</summary>
        <p className="mt-2 font-mono break-all">
          {row.entry_id}
          {row.catalog_compare_group_id ? ` · ${row.catalog_compare_group_id}` : ""}
          {row.extract_compare_group_id &&
          row.extract_compare_group_id !== row.catalog_compare_group_id
            ? ` · extracted as ${row.extract_compare_group_id}`
            : ""}
        </p>
      </details>
    </article>
  );
}

function RateCard({
  row,
  busyId,
  onClassify,
  onApprove,
  onReject,
  onFlag,
}: {
  row: CatalogAdminReviewRow;
  busyId: string | null;
  onClassify: (kind: CatalogAdminKind) => void;
  onApprove: () => void;
  onReject: () => void;
  onFlag: () => void;
}) {
  const busy = busyId === row.entry_id;
  const provision = row.classification;
  const band =
    row.lower != null || row.upper != null
      ? `${row.lower ?? "—"} to ${row.upper ?? "—"}`
      : null;
  const rate =
    row.rate_percent != null
      ? `${row.rate_percent}%`
      : row.value != null
        ? String(row.value)
        : null;
  return (
    <article className="space-y-4 rounded-lg border bg-card p-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <h3 className="text-base font-semibold leading-snug">
              {row.display_name || row.description || "Rate row"}
              {rate ? ` · ${rate}` : ""}
            </h3>
            <p className="text-sm text-muted-foreground">
              {[band, row.effective_from ? `From ${row.effective_from}` : null]
                .filter(Boolean)
                .join(" · ") || "No band dates on this row."}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            {gateChip(row.quote_ok_full_doc, "Quote checked", "Quote not found")}
            {gateChip(row.pass2_verbatim, "Matches Act text", "Wording differs")}
            {row.decision_status ? (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">
                {decisionLabel(row.decision_status)}
              </span>
            ) : null}
          </div>
        </div>
      </div>
      {row.sole_check ? (
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          <p>There is no independent check for this rate. Approval means you have read the Act text.</p>
          <p className="text-xs">{CATALOG_HONESTY_COPY}</p>
        </div>
      ) : null}
      <ClassificationBlock provision={provision} />
      {provision ? (
        <KindButtons provision={provision} busy={busy} onSet={onClassify} />
      ) : null}
      <RowActions
        row={row}
        busy={busy}
        onApprove={onApprove}
        onReject={onReject}
        onFlag={onFlag}
      />
      <AttributionTrail provision={provision} />
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technical ids</summary>
        <p className="mt-2 font-mono break-all">{row.entry_id}</p>
      </details>
    </article>
  );
}

function SelectionTable({
  label,
  rows,
}: {
  label: string;
  rows: CatalogAdminPromotePreview["groups"][number]["before"];
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium">{label}</p>
      <table className="w-full text-left text-xs">
        <thead>
          <tr>
            <th className="py-1 pr-2">Year</th>
            <th className="py-1 pr-2">Cap</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.assessment_year}>
              <td className="py-1 pr-2">{yearLabel(row.assessment_year)}</td>
              <td className="py-1 pr-2">{row.cap_amount ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
  const pendingKind = reliefRows.filter((row) => !row.classification?.kind_human).length;
  const pendingBind = reliefRows.filter(
    (row) => row.included && !row.engine_binding?.kind,
  ).length;
  const pendingDecision = reliefRows.filter(
    (row) =>
      row.included &&
      row.decision_status !== "approved" &&
      row.decision_status !== "rejected",
  ).length;

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
        <p className="text-sm text-muted-foreground">Loading this Act…</p>
      ) : data ? (
        <div className="space-y-6">
          <div className="space-y-1">
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
            {reliefRows.length > 0 ? (
              <p className="text-sm text-muted-foreground">
                {reliefRows.length} relief{reliefRows.length === 1 ? "" : "s"} to review
                {pendingKind || pendingBind || pendingDecision
                  ? ` · ${
                      pendingKind + pendingBind + pendingDecision
                    } still need a decision`
                  : " · ready to preview and save"}
              </p>
            ) : null}
          </div>

          <section className="space-y-2 rounded-lg border bg-card p-5 text-sm">
            {data.proposal.act_identity?.quote ? (
              <blockquote className="rounded-md bg-muted/50 p-3 text-sm leading-relaxed">
                {data.proposal.act_identity.quote}
              </blockquote>
            ) : null}
            <p className="text-muted-foreground">
              {duplicateCopy(data.proposal.duplicate_check?.outcome)}
              {data.proposal.duplicate_check?.corpus_hit
                ? " Kept as a new source — the existing catalog file was not replaced."
                : ""}{" "}
              Extracted {formatWhen(data.proposal.extracted_at) || "date unknown"}.
            </p>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">Technical details</summary>
              <div className="mt-2 space-y-1 break-all font-mono">
                <p>source {data.source_doc_id}</p>
                <p>text {data.proposal.text_sha256 || "—"}</p>
                {data.proposal.tables_sha256 ? (
                  <p>tables {data.proposal.tables_sha256}</p>
                ) : null}
                {data.proposal.pdf_sha256 ? <p>pdf {data.proposal.pdf_sha256}</p> : null}
                {data.proposal.job_id ? <p>job {data.proposal.job_id}</p> : null}
                {data.proposal.act_identity?.parsed_from || data.proposal.act_identity?.source ? (
                  <p>
                    parsed from{" "}
                    {data.proposal.act_identity.parsed_from || data.proposal.act_identity.source}
                  </p>
                ) : null}
              </div>
            </details>
          </section>

          {classification ? (
            <section className="space-y-2 rounded-lg border bg-card p-5 text-sm">
              <h3 className="font-semibold">When this Act’s rules take effect</h3>
              <p className="text-muted-foreground">
                These are commencement dates from the PDF (when each provision starts), not
                taxpayer income dates. They help suggest whether a relief updates an existing
                year or needs a new year — you still choose on each relief below.
              </p>
              <p>
                Found {classification.harvest_record_count ?? 0} commencement date
                {(classification.harvest_record_count ?? 0) === 1 ? "" : "s"} across{" "}
                {classification.pages_scanned ?? 0} page
                {(classification.pages_scanned ?? 0) === 1 ? "" : "s"}.
              </p>
              {(classification.harvest_notes ?? []).length > 0 ? (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Scan notes</summary>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {(classification.harvest_notes ?? []).map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={harvestBusy}
                onClick={() => void onHarvest()}
              >
                {harvestBusy ? "Re-reading…" : "Re-scan this PDF"}
              </Button>
            </section>
          ) : (
            <section className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
              <h3 className="font-semibold">When this Act’s rules take effect</h3>
              <p>
                Commencement dates have not been read yet. Without them, year-type suggestions
                on each relief may be missing.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={harvestBusy}
                onClick={() => void onHarvest()}
              >
                {harvestBusy ? "Reading dates…" : "Find commencement dates"}
              </Button>
            </section>
          )}

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <section className="space-y-4">
            <div className="space-y-1">
              <h3 className="text-base font-semibold">Reliefs extracted from this Act</h3>
              <p className="text-sm text-muted-foreground">
                Read the quote, then choose year type, tax effect, and approve or reject.
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
                  <h4 className="text-sm font-semibold text-muted-foreground">
                    {section.title}
                    <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                      {section.rows.length}
                    </span>
                  </h4>
                  {section.rows.map((row) => (
                    <ReliefCard
                      key={row.entry_id}
                      row={row}
                      busyId={busyId}
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
                      onApprove={() =>
                        void applyReview(
                          () =>
                            approveCatalogAdminRow(sourceDocId as string, row.entry_id, {
                              soleCheck: Boolean(row.sole_check),
                            }),
                          row.entry_id,
                        )
                      }
                      onReject={() =>
                        void applyReview(
                          () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                          row.entry_id,
                        )
                      }
                      onFlag={() =>
                        void applyReview(
                          () => flagCatalogAdminRow(sourceDocId as string, row.entry_id),
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
                  key={row.entry_id}
                  row={row}
                  busyId={busyId}
                  onClassify={(kind) =>
                    void applyReview(
                      () =>
                        setCatalogAdminClassification(sourceDocId as string, row.entry_id, kind),
                      row.entry_id,
                    )
                  }
                  onApprove={() =>
                    void applyReview(
                      () =>
                        approveCatalogAdminRow(sourceDocId as string, row.entry_id, {
                          soleCheck: Boolean(row.sole_check),
                        }),
                      row.entry_id,
                    )
                  }
                  onReject={() =>
                    void applyReview(
                      () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                      row.entry_id,
                    )
                  }
                  onFlag={() =>
                    void applyReview(
                      () => flagCatalogAdminRow(sourceDocId as string, row.entry_id),
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
                  key={row.entry_id}
                  row={row}
                  busyId={busyId}
                  onClassify={(kind) =>
                    void applyReview(
                      () =>
                        setCatalogAdminClassification(sourceDocId as string, row.entry_id, kind),
                      row.entry_id,
                    )
                  }
                  onApprove={() =>
                    void applyReview(
                      () =>
                        approveCatalogAdminRow(sourceDocId as string, row.entry_id, {
                          soleCheck: Boolean(row.sole_check),
                        }),
                      row.entry_id,
                    )
                  }
                  onReject={() =>
                    void applyReview(
                      () => rejectCatalogAdminRow(sourceDocId as string, row.entry_id),
                      row.entry_id,
                    )
                  }
                  onFlag={() =>
                    void applyReview(
                      () => flagCatalogAdminRow(sourceDocId as string, row.entry_id),
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
                This is separate from choosing “Create a new year” on a relief. It does not add
                the year to the taxpayer interview.
              </p>
              {data.new_year_confirmed ? (
                <p className="text-sm">
                  Confirmed year {yearLabel(data.proposal.proposed_for_assessment_year)}
                  {data.proposal.proposed_year_set_by
                    ? ` · ${data.proposal.proposed_year_set_by}`
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
                    {confirmBusy ? "Creating files…" : "Confirm new year file"}
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
              {previewBusy ? "Building preview…" : "Preview changes"}
            </Button>
            {!data.preview_ready ? (
              <p className="text-sm text-muted-foreground">{data.promote_blocked_reason}</p>
            ) : null}
            {preview ? (
              <div className="space-y-4">
                {(preview.engine_year_notes ?? []).length > 0
                  ? preview.engine_year_notes!.map((note) => (
                      <p key={note.assessment_year} className="text-sm">
                        {note.message}
                      </p>
                    ))
                  : preview.engine_year_note ? (
                      <p className="text-sm">{preview.engine_year_note}</p>
                    ) : null}
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40">
                  <p className="font-medium">Shown in interview, does not change tax</p>
                  {preview.tax_inert_rows.length === 0 ? (
                    <p>No included reliefs are set to “do not change tax”.</p>
                  ) : (
                    <ul className="mt-1 list-disc pl-5">
                      {preview.tax_inert_rows.map((row) => (
                        <li key={row.entry_id}>
                          {row.display_name || row.entry_id} — {row.note}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {preview.groups.map((group) => (
                  <article key={group.compare_group_id} className="space-y-2 rounded-md border p-3">
                    <h4 className="text-sm font-medium">{humanId(group.compare_group_id)}</h4>
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
                    <div className="grid gap-3 md:grid-cols-2">
                      <SelectionTable label="Before" rows={group.before} />
                      <SelectionTable label="After" rows={group.after} />
                    </div>
                  </article>
                ))}
                <div className="text-sm">
                  <p>
                    Years that would be updated:{" "}
                    {preview.year_files_that_would_be_written.map(yearFileLabel).join(", ") ||
                      "none"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Other years stay as they are
                    {preview.year_files_frozen.length
                      ? `: ${preview.year_files_frozen.slice(0, 8).map(yearFileLabel).join(", ")}${
                          preview.year_files_frozen.length > 8 ? "…" : ""
                        }`
                      : "."}
                  </p>
                </div>
              </div>
            ) : null}
          </section>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={promoteBusy || !canPromote}
              onClick={() => void onPromote()}
            >
              {promoteBusy ? "Saving…" : "Save updates to existing years"}
            </Button>
            {data.has_new_year_rows ? (
              <Button
                type="button"
                disabled={promoteBusy || !data.new_year_promote_enabled}
                onClick={() => void onPromoteNewYear()}
              >
                {promoteBusy ? "Saving…" : "Save as a new year"}
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
