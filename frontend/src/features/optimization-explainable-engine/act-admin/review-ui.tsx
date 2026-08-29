import { CheckCircle2, CircleDashed, FileText, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

import { formatLkr, yaDisplay } from "../format-lkr";
import type {
  CatalogPreviewResponse,
  ImpactPreviewGroup,
  ImpactPreviewResponse,
  ReviewEntity,
  YearKind,
} from "./api";

export type ReviewCounts = {
  total: number;
  approved: number;
  rejected: number;
  pending: number;
};

export function countReviewRows(rows: ReviewEntity[]): ReviewCounts {
  const approved = rows.filter((row) => row.review_status === "accepted").length;
  const rejected = rows.filter((row) => row.review_status === "rejected").length;
  const pending = rows.length - approved - rejected;
  return { total: rows.length, approved, rejected, pending };
}

export function yearLabel(ya?: string | null): string {
  if (!ya) return "";
  return yaDisplay(String(ya));
}

function kindDecisionLabel(kind: YearKind, entity: ReviewEntity): string {
  const newYa = yearLabel(
    String(entity.new_assessment_year ?? entity.derived_assessment_year ?? ""),
  );
  const updateYa = yearLabel(String(entity.update_assessment_year ?? ""));
  if (kind === "NEW_YEAR") {
    return newYa ? `Create a new year · YA ${newYa}` : "Create a new year";
  }
  return updateYa ? `Update existing year · YA ${updateYa}` : "Update existing year";
}

function derivedYearHint(entity: ReviewEntity): string | null {
  const suggested = String(entity.year_kind_suggested ?? "");
  const newYa = yearLabel(
    String(entity.new_assessment_year ?? entity.derived_assessment_year ?? ""),
  );
  const updateYa = yearLabel(String(entity.update_assessment_year ?? ""));
  if (suggested === "NEW_YEAR") {
    return updateYa && newYa && updateYa !== newYa
      ? `Act commencement creates YA ${newYa} (not in the live catalog yet). Choose Create a new year so it appears in the preview and taxpayer year list. Update existing year amends YA ${updateYa} instead.`
      : `Act commencement creates YA ${newYa}. Choose Create a new year so it appears in the preview and taxpayer year list.`;
  }
  if (newYa) {
    return `From the act date, this row updates YA ${newYa} in the live catalog on activate.`;
  }
  return null;
}

export function YearKindButtons({
  entity,
  busy,
  onSet,
}: {
  entity: ReviewEntity;
  busy: boolean;
  onSet: (kind: YearKind) => void;
}) {
  const selected = String(entity.year_kind ?? "") as YearKind | "";
  const hint = derivedYearHint(entity);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Year</p>
      <p className="text-xs text-muted-foreground">
        Does this Act create a new assessment year, or update a year already in the catalog?
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
          {kindDecisionLabel("UPDATE", entity)}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={selected === "NEW_YEAR" ? "default" : "outline"}
          disabled={busy}
          onClick={() => onSet("NEW_YEAR")}
        >
          {kindDecisionLabel("NEW_YEAR", entity)}
        </Button>
      </div>
      {selected ? (
        <p className="text-xs text-muted-foreground">
          Chosen: <strong>{kindDecisionLabel(selected, entity)}</strong>
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">Nothing is selected until you choose.</p>
      )}
    </div>
  );
}

export function YearKindBanner({
  sample,
  busy,
  onApplyAll,
}: {
  sample: ReviewEntity;
  busy: boolean;
  onApplyAll: (kind: YearKind) => void;
}) {
  const newYa = yearLabel(
    String(sample.new_assessment_year ?? sample.derived_assessment_year ?? ""),
  );
  const updateYa = yearLabel(String(sample.update_assessment_year ?? ""));
  return (
    <div className="space-y-3 rounded-xl border border-sky-300 bg-sky-50 p-4 text-sm text-sky-950">
      <p className="font-medium">
        This Act date is not in the live catalog yet
        {newYa ? ` (YA ${newYa})` : ""}.
      </p>
      <p className="text-xs">
        Apply to every in-scope row, then check Live RAG preview.{" "}
        <strong>Create a new year</strong> adds {newYa || "the new YA"} to the preview and to the
        taxpayer year dropdown after activate. <strong>Update existing year</strong> writes into YA{" "}
        {updateYa || "the latest live year"} instead.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={() => onApplyAll("NEW_YEAR")}>
          Apply to all rows: Create a new year{newYa ? ` · YA ${newYa}` : ""}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => onApplyAll("UPDATE")}
        >
          Apply to all rows: Update existing year{updateYa ? ` · YA ${updateYa}` : ""}
        </Button>
      </div>
    </div>
  );
}

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function reliefTitle(entity: ReviewEntity): string {
  return String(entity.display_name ?? "Untitled relief");
}

function reliefSectionTitle(entity: ReviewEntity): string {
  const label = String(entity.section_label ?? entity.section_ref ?? "").toLowerCase();
  if (label.includes("fifth")) return "Fifth Schedule qualifying payments";
  if (label.includes("first")) return "First Schedule rates";
  if (label.includes("rent")) return "Rental income";
  if (label.includes("personal")) return "Personal relief";
  if (label.includes("employment")) return "Employment relief";
  return String(entity.section_label ?? entity.section_ref ?? "Other reliefs");
}

function reliefSubtitle(entity: ReviewEntity): string {
  const paragraph = String(entity.paragraph_ref ?? "").trim();
  const targetYa = yearLabel(String(entity.derived_assessment_year ?? ""));
  return [
    String(entity.section_label ?? ""),
    paragraph ? `¶${paragraph}` : null,
    targetYa ? `Target YA ${targetYa}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

const QUESTION_INPUT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "notice", label: "Notice (auto-applied, no claim)" },
  { value: "yes_no_amount", label: "Yes/no + amount" },
  { value: "amount", label: "Amount only" },
  { value: "boolean", label: "Yes/no" },
];

function interviewPreview(entity: ReviewEntity): ReviewEntity {
  const preview = entity.interview_preview;
  if (preview && typeof preview === "object") {
    return preview as ReviewEntity;
  }
  return entity;
}

function inputKindHint(kind: string): string {
  if (kind === "yes_no_amount") return "Yes/no + amount";
  if (kind === "amount") return "Amount only";
  if (kind === "boolean") return "Yes/no";
  return "Applies automatically — no claim amount";
}

function formatCap(entity: ReviewEntity): string | null {
  const cap = entity.cap_amount;
  if (cap == null || cap === "") return null;
  const raw = String(cap).trim();
  if (entity.unit === "percent") return `${raw.replace(/%$/, "")}% of written-down value`;
  if (entity.unit === "text") return null;
  return formatLkr(raw);
}

function cardAccentClass(status: string | undefined): string {
  if (status === "accepted") return "border-l-4 border-l-emerald-500";
  if (status === "rejected") return "border-l-4 border-l-rose-400";
  return "border-l-4 border-l-amber-400/80";
}

export function gateChip(ok: boolean | undefined, yes: string, no: string) {
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

function decisionBadge(status: string | undefined) {
  if (status === "accepted") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-900">
        <CheckCircle2 className="size-3" aria-hidden />
        Approved
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium text-rose-950">
        <XCircle className="size-3" aria-hidden />
        Rejected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
      <CircleDashed className="size-3" aria-hidden />
      Needs decision
    </span>
  );
}

function formatActQuoteText(raw: string): string {
  const text = raw.trim();
  if (!text.includes("|")) return text;
  return text
    .split("\n")
    .map((line) =>
      line
        .split("|")
        .map((part) => part.trim())
        .filter(Boolean)
        .join(" — "),
    )
    .filter(Boolean)
    .join("\n");
}

function ActQuoteBlock({
  entity,
}: {
  entity: ReviewEntity;
}) {
  const quote = String(entity.quote ?? "").trim();
  const section = String(entity.section_label ?? entity.section_ref ?? "Act quote");
  const paragraph = String(entity.paragraph_ref ?? "").trim();
  const applies = String(entity.applies_to ?? "").trim();
  if (!quote) {
    return (
      <div className="space-y-1 rounded-md border border-dashed bg-muted/10 p-3">
        <p className="text-xs font-medium text-muted-foreground">
          Act quote · {section}
          {paragraph ? ` · ¶${paragraph}` : ""}
        </p>
        <p className="text-sm text-muted-foreground">
          No verbatim Act quote was extracted for this row.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-md border bg-muted/20 p-3">
      <p className="text-xs font-medium text-muted-foreground">
        Act quote · {section}
        {paragraph ? ` · ¶${paragraph}` : ""}
        {applies ? ` · ${applies}` : ""}
      </p>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {formatActQuoteText(quote)}
      </p>
    </div>
  );
}

export function rateBandFormula(entity: ReviewEntity): string {
  const quote = String(entity.quote ?? "").trim();
  if (quote.includes("|")) {
    const lines = quote.split("\n").map((line) => line.trim()).filter(Boolean);
    const dataLine =
      lines.find((line) => /exceeding|not exceeding|rs\.?/i.test(line)) ??
      lines[lines.length - 1] ??
      "";
    const parts = dataLine.split("|").map((part) => part.trim()).filter(Boolean);
    if (parts.length >= 2) {
      return parts[parts.length - 1]!;
    }
  }
  if (entity.rate_percent != null && entity.rate_percent !== "") {
    return `${entity.rate_percent}%`;
  }
  return "";
}

const TERMINAL_RATE_GROUP_HINTS = [
  "terminal_benefit",
  "employment_income_tax",
  "employment_income",
];

export function isTerminalRateRow(entity: ReviewEntity): boolean {
  const group = String(entity.compare_group_id ?? "")
    .toLowerCase()
    .replace(/-/g, "_");
  const family = String(entity.rule_family ?? "")
    .toLowerCase()
    .replace(/-/g, "_");
  const quote = String(entity.quote ?? "").toLowerCase();
  if (TERMINAL_RATE_GROUP_HINTS.some((hint) => group.includes(hint) || family.includes(hint))) {
    return true;
  }
  return quote.includes("total income from employment");
}

function inferTerminalPeriodLabel(entity: ReviewEntity): string {
  const stated = String(entity.employment_period_condition ?? "").trim();
  if (stated === "over_20_years") return "Employment period over 20 years";
  if (stated === "upto_20_years") return "Employment period up to 20 years";
  if (stated === "not_applicable") return "Standard terminal ladder";
  const hay = `${entity.quote ?? ""} ${entity.band_label ?? ""} ${entity.applies_to ?? ""}`.toLowerCase();
  if (/more than twenty|exceeding twenty|>\s*20/.test(hay)) {
    return "Employment period over 20 years";
  }
  if (/not exceeding twenty|twenty years or less|<=\s*20/.test(hay)) {
    return "Employment period up to 20 years";
  }
  const upper = Number(String(entity.upper ?? "").replace(/,/g, ""));
  if (upper === 5_000_000) return "Employment period over 20 years";
  if (upper === 2_000_000) return "Employment period up to 20 years";
  return "Qualifying terminal / retirement benefits";
}

export function groupRatesBySection(
  rows: ReviewEntity[],
): Array<[string, ReviewEntity[]]> {
  const groups = new Map<string, ReviewEntity[]>();
  for (const row of rows) {
    const section = String(row.section_label ?? row.section_ref ?? "Tax rates");
    const groupId = String(row.compare_group_id ?? "");
    let title: string;
    if (isTerminalRateRow(row)) {
      title = `Retirement & terminal benefits · ${inferTerminalPeriodLabel(row)}`;
    } else if (groupId.includes("withholding")) {
      title = `${section} — Withholding`;
    } else if (groupId.includes("individual") || groupId.includes("first_schedule")) {
      title = `${section} — Ordinary individual income tax`;
    } else {
      title = section;
    }
    const bucket = groups.get(title) ?? [];
    bucket.push(row);
    groups.set(title, bucket);
  }
  const ordered = [...groups.entries()].sort(([a], [b]) => {
    const aTerm = a.startsWith("Retirement");
    const bTerm = b.startsWith("Retirement");
    if (aTerm !== bTerm) return aTerm ? 1 : -1;
    return a.localeCompare(b);
  });
  return ordered.map(([title, sectionRows]) => [
    title,
    [...sectionRows].sort(
      (a, b) => Number(a.band_index ?? 0) - Number(b.band_index ?? 0),
    ),
  ]);
}

export function ReviewProgressStrip({
  relief,
  rates,
  rejectedNoise = 0,
  alreadyInSystem = false,
}: {
  relief: ReviewCounts;
  rates: ReviewCounts;
  rejectedNoise?: number;
  alreadyInSystem?: boolean;
}) {
  const total = relief.total + rates.total;
  const done = relief.approved + relief.rejected + rates.approved + rates.rejected;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const reliefApproved = relief.approved;
  const ratesApproved = rates.approved;
  const reliefLeft = relief.pending;
  const ratesLeft = rates.pending;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Review progress</CardTitle>
        <CardDescription>
          {alreadyInSystem
            ? `${done} of ${total} decided · ${relief.rejected + rates.rejected} rejected kept out · ${rejectedNoise} entity/business noise`
            : `${done} of ${total} rows decided · ${pct}% complete`}
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
          <div className="rounded-lg border bg-muted/30 px-3 py-2">
            <p className="text-xs font-medium text-muted-foreground">Reliefs</p>
            <p className="mt-1 text-sm font-semibold">
              {reliefApproved} approved · {relief.rejected} rejected · {reliefLeft} left
            </p>
          </div>
          <div className="rounded-lg border bg-muted/30 px-3 py-2">
            <p className="text-xs font-medium text-muted-foreground">Rates</p>
            <p className="mt-1 text-sm font-semibold">
              {ratesApproved} approved · {rates.rejected} rejected · {ratesLeft} left
            </p>
          </div>
          <div className="rounded-lg border bg-muted/30 px-3 py-2">
            <p className="text-xs font-medium text-muted-foreground">
              {alreadyInSystem ? "Entity / business noise" : "Quick guide"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {alreadyInSystem
                ? `${rejectedNoise} rejected · kept out of individual year views`
                : "Reject if wrong. Otherwise use Quick approve — defaults are fine for most rows."}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InterviewQuestionPreview({
  entity,
  lockedInSystem = false,
}: {
  entity: ReviewEntity;
  lockedInSystem?: boolean;
}) {
  const preview = interviewPreview(entity);
  const prompt = String(preview.question_prompt ?? entity.question_prompt ?? "").trim();
  const help = String(preview.help ?? entity.help ?? "").trim();
  const kind = String(preview.input_kind ?? entity.input_kind ?? "notice");
  const fromPrior = Boolean(entity.has_prior_catalog) || lockedInSystem;
  return (
    <div className="space-y-2 rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {lockedInSystem ? "Rule on My Reliefs (from this Act)" : "Taxpayer interview preview"}
        </p>
        {fromPrior ? (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-800">
            {lockedInSystem ? "Live catalog · read-only" : "Reuses live catalog wording"}
          </span>
        ) : (
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            LLM draft
          </span>
        )}
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {reliefTitle(entity)}
      </p>
      <h4 className="text-base font-semibold leading-snug">
        {prompt || "No taxpayer question yet — edit below before approve."}
      </h4>
      {help ? <p className="text-sm text-muted-foreground">{help}</p> : null}
      <p className="text-xs text-muted-foreground">{inputKindHint(kind)}</p>
    </div>
  );
}

function QuestionFieldsEditor({
  entity,
  busy,
  onSave,
}: {
  entity: ReviewEntity;
  busy: boolean;
  onSave: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
}) {
  const preview = interviewPreview(entity);
  const [displayName, setDisplayName] = useState(String(entity.display_name ?? ""));
  const [questionPrompt, setQuestionPrompt] = useState(
    String(preview.question_prompt ?? entity.question_prompt ?? ""),
  );
  const [inputKind, setInputKind] = useState(String(preview.input_kind ?? entity.input_kind ?? "notice"));
  const [helpText, setHelpText] = useState(String(preview.help ?? entity.help ?? ""));
  const [groupId, setGroupId] = useState(String(entity.compare_group_id ?? ""));
  const entryId = String(entity.entry_id ?? "");
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
          <Label htmlFor={`qn-name-${entryId}`}>Display name</Label>
          <Input
            id={`qn-name-${entryId}`}
            value={displayName}
            disabled={busy}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`qn-kind-${entryId}`}>Input kind</Label>
          <Select
            id={`qn-kind-${entryId}`}
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
        <Label htmlFor={`qn-prompt-${entryId}`}>Question shown to taxpayer</Label>
        <Input
          id={`qn-prompt-${entryId}`}
          value={questionPrompt}
          disabled={busy}
          onChange={(event) => setQuestionPrompt(event.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`qn-help-${entryId}`}>Help text</Label>
        <Input
          id={`qn-help-${entryId}`}
          value={helpText}
          disabled={busy}
          onChange={(event) => setHelpText(event.target.value)}
          placeholder="Optional one-line help under the question"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`qn-group-${entryId}`}>Compare group</Label>
        <Input
          id={`qn-group-${entryId}`}
          value={groupId}
          disabled={busy}
          onChange={(event) => setGroupId(event.target.value)}
          className="font-mono text-xs"
        />
      </div>
      <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
        <p>
          Cap (verbatim):{" "}
          <span className="font-medium text-foreground">{formatCap(entity) ?? "—"}</span>
        </p>
        <p className="mt-1">Quote locked. Reject the row if the quote or cap is wrong.</p>
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
    </div>
  );
}

function DecisionPanel({
  entity,
  status,
  busy,
  onQuickApprove,
  onReject,
  onSaveQuestions,
  onSetYearKind,
}: {
  entity: ReviewEntity;
  status: string;
  busy: boolean;
  onQuickApprove: () => void;
  onReject: () => void;
  onSetYearKind: (kind: YearKind) => void;
  onSaveQuestions: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
}) {
  const rejected = status === "rejected";
  const accepted = status === "accepted";
  const pending = !accepted && !rejected;
  const reviewedBy = String(entity.reviewed_by ?? "").trim();
  const preview = interviewPreview(entity);
  const prompt = String(preview.question_prompt ?? entity.question_prompt ?? "").trim();
  const fromPrior = Boolean(entity.has_prior_catalog);
  const chosenKind = String(entity.year_kind ?? "") as YearKind | "";
  const editorKey = [
    String(entity.entry_id ?? ""),
    String(preview.question_prompt ?? entity.question_prompt ?? ""),
    String(preview.help ?? entity.help ?? ""),
    String(preview.input_kind ?? entity.input_kind ?? ""),
  ].join("-");
  return (
    <>
      <div className="space-y-3 rounded-lg border border-dashed bg-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Your decision
        </p>
        {!rejected ? (
          <YearKindButtons entity={entity} busy={busy} onSet={onSetYearKind} />
        ) : null}
        {pending ? (
          <p className="rounded-md bg-background px-3 py-2 text-xs text-muted-foreground">
            <strong>Quick approve</strong> keeps the
            {fromPrior ? " live catalog" : " LLM"} question as-is. Use the editor below to change it
            first.
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {!accepted ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy || rejected}
              onClick={onReject}
            >
              Reject
            </Button>
          ) : null}
          {!accepted ? (
            <Button type="button" size="sm" disabled={busy} onClick={onQuickApprove}>
              {rejected ? "Approve" : "Quick approve"}
            </Button>
          ) : (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onReject}>
              Reject
            </Button>
          )}
        </div>
        {status !== "pending" && reviewedBy ? (
          <p className="text-xs text-muted-foreground">
            Status: <strong>{status === "accepted" ? "Approved" : "Rejected"}</strong> · {reviewedBy}
          </p>
        ) : null}
        {accepted && chosenKind ? (
          <p className="text-xs text-muted-foreground">
            Year: <strong>{kindDecisionLabel(chosenKind, entity)}</strong>
          </p>
        ) : null}
        {accepted ? (
          <p className="text-xs text-muted-foreground">
            Taxpayer question: <strong>{prompt || reliefTitle(entity)}</strong>
            {fromPrior ? " (reused from live catalog)" : ""}
          </p>
        ) : null}
        {!rejected ? (
          <details className="rounded-md border bg-background p-3 text-sm">
            <summary className="cursor-pointer font-medium">
              {pending ? "Optional: edit taxpayer wording" : "Edit taxpayer wording"}
            </summary>
            <div className="mt-3">
              <QuestionFieldsEditor
                key={editorKey}
                entity={entity}
                busy={busy}
                onSave={onSaveQuestions}
              />
            </div>
          </details>
        ) : null}
      </div>
      {rejected ? (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-950">
          Rejected — will not be published. Use <strong>Quick approve</strong> to change your
          decision.
        </p>
      ) : null}
    </>
  );
}

export function RateBandReviewSection({
  title,
  rows,
  busyId,
  onApprove,
  onReject,
  onSetYearKind,
  readOnlyApproved = false,
}: {
  title: string;
  rows: ReviewEntity[];
  busyId: string | null;
  onApprove: (entryId: string) => void;
  onReject: (entryId: string) => void;
  onSetYearKind: (kind: YearKind) => void;
  readOnlyApproved?: boolean;
}) {
  const targetYa = yearLabel(String(rows[0]?.derived_assessment_year ?? ""));
  const appliesTo = String(rows[0]?.applies_to ?? "").trim();
  const sample = rows[0];
  const sectionBusy =
    rows.some((row) => busyId === String(row.entry_id ?? "")) || busyId === "year-kind";
  const scheduleProse = String(sample?.section_act_prose ?? "").trim();
  const isTerminalSection = rows.some((row) => isTerminalRateRow(row));
  const qualifyingTypes = Array.isArray(sample?.qualifying_income_types)
    ? (sample?.qualifying_income_types as unknown[])
        .map((item) => String(item).replace(/_/g, " "))
        .filter(Boolean)
    : [
        "commuted pension",
        "retiring gratuity",
        "compensation for loss of office",
        "ETF at or after retirement",
      ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold">
          {title}
          <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {rows.length}
          </span>
        </h4>
        <p className="text-xs text-muted-foreground">
          {[targetYa ? `Target YA ${targetYa}` : null, appliesTo || null].filter(Boolean).join(" · ")}
        </p>
      </div>
      {isTerminalSection ? (
        <p className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-foreground">
          Separate First Schedule ladder for Retirement & terminal benefits (not ordinary salary).
          Qualifying types: {qualifyingTypes.join("; ")}.
        </p>
      ) : null}
      {sample && !readOnlyApproved ? (
        <div className="rounded-xl border bg-muted/20 p-4">
          <YearKindButtons entity={sample} busy={sectionBusy} onSet={onSetYearKind} />
        </div>
      ) : null}
      {scheduleProse ? (
        <details className="rounded-xl border bg-muted/15 p-4">
          <summary className="cursor-pointer text-sm font-medium">
            Full schedule text from the Act (shared for these bands)
          </summary>
          <p className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {scheduleProse}
          </p>
        </details>
      ) : null}
      <div className="grid gap-3">
        {rows.map((entity) => {
          const entryId = String(entity.entry_id ?? "");
          const status = String(entity.review_status ?? "pending");
          const busy = busyId === entryId;
          const accepted = status === "accepted";
          const rejected = status === "rejected";
          const band = String(entity.band_label ?? entity.display_name ?? "Band");
          const formula = rateBandFormula(entity);
          const quoteOk =
            Boolean(entity.quote_ok_full_doc) && Boolean(entity.pass2_verbatim);
          const lockDecided = readOnlyApproved && (accepted || rejected);
          return (
            <article
              key={entryId}
              className={cn(
                "space-y-3 rounded-xl border bg-card p-4 shadow-sm",
                cardAccentClass(status),
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <h5 className="text-sm font-semibold leading-snug">{band}</h5>
                  <p className="text-sm text-muted-foreground">
                    Tax payable: {formula || "—"}
                  </p>
                </div>
                <div className="flex flex-wrap justify-end gap-1.5">
                  {gateChip(Boolean(entity.quote_ok_full_doc), "Quote checked", "Quote not found")}
                  {gateChip(Boolean(entity.pass2_verbatim), "Matches Act text", "Wording differs")}
                  {decisionBadge(status)}
                  {!quoteOk && !lockDecided ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-950">
                      Check quote
                    </span>
                  ) : null}
                </div>
              </div>
              <ActQuoteBlock entity={entity} />
              {lockDecided && accepted ? (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-sm text-emerald-950">
                  Already approved in the catalog — Act quote above is what the engine extracted for
                  this band.
                </p>
              ) : null}
              {lockDecided && rejected ? (
                <p className="rounded-lg border border-rose-200 bg-rose-50/60 px-3 py-2 text-sm text-rose-950">
                  Previously rejected — kept out of year views on activate.
                </p>
              ) : null}
              {!lockDecided ? (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {!accepted ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy || rejected}
                      onClick={() => onReject(entryId)}
                    >
                      Reject
                    </Button>
                  ) : null}
                  {!accepted ? (
                    <Button
                      type="button"
                      size="sm"
                      disabled={busy}
                      onClick={() => onApprove(entryId)}
                    >
                      {rejected ? "Approve" : "Quick approve"}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => onReject(entryId)}
                    >
                      Reject
                    </Button>
                  )}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

export function ReliefReviewCard({
  entity,
  busy,
  onQuickApprove,
  onReject,
  onSaveQuestions,
  onSetYearKind,
  readOnlyApproved = false,
}: {
  entity: ReviewEntity;
  busy: boolean;
  onQuickApprove: () => void;
  onReject: () => void;
  onSetYearKind: (kind: YearKind) => void;
  onSaveQuestions: (fields: {
    display_name: string;
    question_prompt: string;
    input_kind: string;
    help: string;
    compare_group_id: string;
  }) => void;
  readOnlyApproved?: boolean;
}) {
  const status = String(entity.review_status ?? "pending");
  const lockedReadOnly = readOnlyApproved;
  const capLabel = formatCap(entity);
  const title = reliefTitle(entity);
  const subtitle = reliefSubtitle(entity);
  const preview = interviewPreview(entity);
  const prompt = String(preview.question_prompt ?? entity.question_prompt ?? "").trim();
  return (
    <article
      className={cn(
        "space-y-4 rounded-xl border bg-card p-5 shadow-sm",
        cardAccentClass(status),
      )}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold leading-snug">{title}</h3>
              {capLabel ? (
                <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  Cap {capLabel}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">
              {subtitle || "No section metadata"}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            {gateChip(Boolean(entity.quote_ok_full_doc), "Quote checked", "Quote not found")}
            {gateChip(Boolean(entity.pass2_verbatim), "Matches Act text", "Wording differs")}
            {decisionBadge(status)}
          </div>
        </div>
        <InterviewQuestionPreview
          entity={entity}
          lockedInSystem={lockedReadOnly && status === "accepted"}
        />
        <ActQuoteBlock entity={entity} />
      </div>
      {lockedReadOnly && status === "accepted" ? (
        <div className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50/60 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">
            Already approved in the system
          </p>
          <p className="text-sm text-emerald-950">
            This rule is live in the catalog. The taxpayer interview question matches My Reliefs and
            cannot be edited from this demo review.
          </p>
          {prompt ? (
            <p className="rounded-md border border-emerald-200/80 bg-white/70 px-3 py-2 text-sm text-foreground">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Live relief question
              </span>
              <span className="mt-1 block font-medium">{prompt}</span>
            </p>
          ) : null}
        </div>
      ) : null}
      {lockedReadOnly && status === "rejected" ? (
        <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50/60 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-rose-900">
            Previously rejected
          </p>
          <p className="text-sm text-rose-950">
            Kept out of year views on activate. Re-extract restores this decision from the auditor
            ledger.
          </p>
        </div>
      ) : null}
      {!lockedReadOnly || status === "pending" ? (
        <DecisionPanel
          entity={entity}
          status={status}
          busy={busy}
          onQuickApprove={onQuickApprove}
          onReject={onReject}
          onSaveQuestions={onSaveQuestions}
          onSetYearKind={onSetYearKind}
        />
      ) : null}
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technical details</summary>
        <p className="mt-2 break-all font-mono">{String(entity.entry_id ?? "")}</p>
      </details>
    </article>
  );
}

function previewRowChanged(
  before: ImpactPreviewGroup["before"][number],
  after: ImpactPreviewGroup["after"][number],
): boolean {
  return (
    String(before.cap_amount ?? "") !== String(after.cap_amount ?? "") ||
    String(before.source_doc_id ?? "") !== String(after.source_doc_id ?? "") ||
    String(before.rate_percent ?? "") !== String(after.rate_percent ?? "")
  );
}

function formatPreviewValue(
  value: string | number | null | undefined,
  isRate?: boolean,
): string {
  if (value == null || value === "") return "—";
  if (isRate) return `${value}%`;
  const text = String(value).trim();
  if (/%$/.test(text)) return text;
  const n = Number(text.replace(/,/g, ""));
  if (Number.isFinite(n) && n >= 1000) return formatLkr(n);
  return text;
}

function ImpactGroupTable({ group }: { group: ImpactPreviewGroup }) {
  const [showAll, setShowAll] = useState(false);
  const isRate = group.entity_kind === "rate_band";
  const rows = group.before.map((before, index) => ({
    before,
    after: group.after[index],
    changed: previewRowChanged(before, group.after[index]),
  }));
  const changedRows = rows.filter((row) => row.changed);
  const visible = showAll || changedRows.length === 0 ? rows : changedRows;
  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">{group.display_name}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-left text-xs">
          <thead>
            <tr className="border-b">
              <th className="py-1.5 pr-3 font-medium">Year</th>
              <th className="py-1.5 pr-3 font-medium">{isRate ? "Before rate" : "Before cap"}</th>
              <th className="py-1.5 pr-3 font-medium">{isRate ? "After rate" : "After cap"}</th>
              <th className="py-1.5 font-medium">Winning act</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                key={row.before.assessment_year}
                className={cn("border-b border-muted/40", row.changed && "bg-amber-50/60")}
              >
                <td className="py-1.5 pr-3">{yearLabel(row.before.assessment_year)}</td>
                <td className="py-1.5 pr-3">
                  {formatPreviewValue(
                    isRate ? row.before.rate_percent : row.before.cap_amount,
                    isRate,
                  )}
                </td>
                <td className="py-1.5 pr-3">
                  {formatPreviewValue(
                    isRate ? row.after.rate_percent : row.after.cap_amount,
                    isRate,
                  )}
                </td>
                <td className="py-1.5">{row.after.source_doc_id ?? row.before.source_doc_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {changedRows.length > 0 && changedRows.length < rows.length ? (
        <button
          type="button"
          className="text-xs font-medium text-primary underline-offset-2 hover:underline"
          onClick={() => setShowAll((prev) => !prev)}
        >
          {showAll ? "Show changed years only" : `Show all ${rows.length} years`}
        </button>
      ) : null}
    </div>
  );
}

export function ImpactPreviewPanel({ preview }: { preview: ImpactPreviewResponse }) {
  const groups = preview.groups ?? [];
  const changedGroups = groups.filter((group) =>
    group.before.some((before, index) => previewRowChanged(before, group.after[index])),
  );
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">See what would change</CardTitle>
        <CardDescription>
          {preview.changed_group_count ?? changedGroups.length} group
          {(preview.changed_group_count ?? changedGroups.length) === 1 ? "" : "s"} with year-level
          changes · {preview.affected_years.map(yearLabel).join(", ") || "none yet"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {preview.blocking_issue_count > 0 ? (
          <ul className="space-y-1 text-sm text-destructive">
            {preview.blocking_issues.map((issue) => (
              <li key={`${issue.entry_id}-${issue.code}`}>{issue.message}</li>
            ))}
          </ul>
        ) : null}
        {changedGroups.length ? (
          changedGroups.map((group) => (
            <ImpactGroupTable key={`${group.compare_group_id}-${group.band_index ?? ""}`} group={group} />
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            Approve rows to see cap and rate changes per assessment year.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function RejectedNoiseSection({ rows }: { rows: ReviewEntity[] }) {
  if (!rows.length) return null;
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h3 className="text-base font-semibold">Rejected — entity &amp; business noise</h3>
        <p className="text-sm text-muted-foreground">
          These First Schedule / qualifying-payment rows apply to companies, trusts, partnerships,
          or funds. This engine keeps individual income tax only, so they stay rejected and never
          enter year views.
        </p>
      </div>
      <div className="grid gap-3">
        {rows.map((entity) => {
          const entryId = String(entity.entry_id ?? "");
          const title =
            String(entity.display_name ?? entity.band_label ?? entity.compare_group_id ?? "Rule").trim() ||
            "Rule";
          const applies = String(entity.applies_to ?? "").trim();
          const rate =
            entity.rate_percent != null && entity.rate_percent !== ""
              ? `${entity.rate_percent}%`
              : rateBandFormula(entity);
          const reason = String(entity.reject_reason ?? "").trim();
          return (
            <article
              key={entryId}
              className={cn(
                "space-y-3 rounded-xl border bg-card p-4 shadow-sm",
                cardAccentClass("rejected"),
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <h4 className="text-sm font-semibold leading-snug">{title}</h4>
                  <p className="text-sm text-muted-foreground">
                    {[applies ? `Applies to ${applies}` : null, rate ? `Rate ${rate}` : null]
                      .filter(Boolean)
                      .join(" · ") || "Entity / business taxpayer rule"}
                  </p>
                </div>
                <div className="flex flex-wrap justify-end gap-1.5">
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-950">
                    Entity / business
                  </span>
                  {decisionBadge("rejected")}
                </div>
              </div>
              <ActQuoteBlock entity={entity} />
              <p className="rounded-lg border border-rose-200 bg-rose-50/70 px-3 py-2 text-sm text-rose-950">
                {reason ||
                  "Rejected — out of scope for the individual engine (entity / business rule)."}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function LiveCatalogPreviewPanel({
  preview,
  selectedYear,
  onYearChange,
  alreadyInSystem = false,
}: {
  preview: CatalogPreviewResponse | undefined;
  selectedYear: string;
  onYearChange: (ya: string) => void;
  alreadyInSystem?: boolean;
}) {
  const years = preview?.preview_years ?? preview?.live_years ?? [];
  const useLive = alreadyInSystem || Boolean(preview?.already_in_system);
  const reliefs =
    useLive && (preview?.live_reliefs?.length ?? 0) > 0
      ? (preview?.live_reliefs ?? [])
      : (preview?.preview_reliefs ?? preview?.live_reliefs ?? []);
  const rates =
    useLive && (preview?.live_rates?.length ?? 0) > 0
      ? (preview?.live_rates ?? [])
      : (preview?.preview_rates ?? preview?.live_rates ?? []);
  const ordinaryRates = rates.filter((row) => !isTerminalRateRow(row));
  const terminalRates = rates.filter((row) => isTerminalRateRow(row));
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Live RAG preview</CardTitle>
        <CardDescription>
          {useLive
            ? `What is already live in the catalog for the selected year (${reliefs.length} reliefs · ${ordinaryRates.length} ordinary bands · ${terminalRates.length} terminal bands).`
            : `Approved rows only after activate (${preview?.accepted_count ?? 0} merged). Rejected rows stay out. New years here also appear for TaxWise users.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="oe-preview-ya">Assessment year</Label>
          <Select
            id="oe-preview-ya"
            value={selectedYear}
            onChange={(event) => onYearChange(event.target.value)}
          >
            {years.map((ya) => (
              <option key={ya} value={ya}>
                {yearLabel(ya)}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <PreviewList title={`Reliefs (${reliefs.length})`} empty="No reliefs for this year yet.">
            {reliefs.map((entry) => {
              const prompt = String(entry.question_prompt ?? "").trim();
              return (
                <li key={String(entry.entry_id ?? entry.compare_group_id)} className="rounded border p-2 text-xs">
                  <p className="font-medium">{prompt || reliefTitle(entry)}</p>
                  <p className="text-muted-foreground">
                    {reliefTitle(entry)} · {formatCap(entry) ?? "No cap"} ·{" "}
                    {inputKindHint(String(entry.input_kind ?? "notice"))}
                  </p>
                </li>
              );
            })}
          </PreviewList>
          <RatePreviewTable
            title={`Ordinary rate bands (${ordinaryRates.length})`}
            rates={ordinaryRates}
            empty="No ordinary rate bands for this year yet."
          />
        </div>
        <RatePreviewTable
          title={`Retirement & terminal benefits (${terminalRates.length})`}
          rates={terminalRates}
          empty="No terminal-benefit rate rules for this year yet."
        />
      </CardContent>
    </Card>
  );
}

function RatePreviewTable({
  title,
  rates,
  empty,
}: {
  title: string;
  rates: ReviewEntity[];
  empty: string;
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{title}</p>
      {rates.length === 0 ? (
        <p className="text-xs text-muted-foreground">{empty}</p>
      ) : (
        <div className="max-h-64 overflow-auto rounded border">
          <table className="w-full text-left text-xs">
            <thead className="border-b bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-2 py-1.5 font-medium">Band</th>
                <th className="px-2 py-1.5 font-medium">Rate</th>
                <th className="px-2 py-1.5 font-medium">Ladder</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((entry) => (
                <tr key={String(entry.entry_id ?? entry.band_index)} className="border-t">
                  <td className="px-2 py-1.5">
                    {String(entry.band_label ?? entry.display_name ?? "Band")}
                  </td>
                  <td className="px-2 py-1.5">{rateBandFormula(entry) || "—"}</td>
                  <td className="px-2 py-1.5 text-muted-foreground">
                    {isTerminalRateRow(entry)
                      ? inferTerminalPeriodLabel(entry)
                      : String(entry.applies_to ?? "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PreviewList({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: ReactNode;
}) {
  const items = Array.isArray(children) ? children : [children];
  const hasItems = items.some(Boolean);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{title}</p>
      {hasItems ? (
        <ul className="max-h-64 space-y-2 overflow-auto">{children}</ul>
      ) : (
        <p className="text-xs text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

export function AboutUploadCard({
  actTitle,
  sourceDocId,
  pdfFileName,
  extractedAt,
  outOfScopeCount,
  note,
  alreadyInSystem = false,
}: {
  actTitle?: string | null;
  sourceDocId: string;
  pdfFileName?: string | null;
  extractedAt?: string | null;
  entityCount?: number;
  extractedEntityCount?: number;
  outOfScopeCount?: number;
  note?: string | null;
  alreadyInSystem?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="size-4" aria-hidden />
          About this upload
        </CardTitle>
        <CardDescription>
          Extracted {formatWhen(extractedAt) || "date unknown"}
          {pdfFileName ? ` · ${pdfFileName}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {actTitle ? (
          <blockquote className="rounded-lg border-l-4 border-muted-foreground/30 bg-muted/40 px-4 py-3 leading-relaxed">
            {actTitle}
          </blockquote>
        ) : null}
        <p className="text-muted-foreground">
          {alreadyInSystem
            ? note?.toLowerCase().includes("already")
              ? note
              : "This Act is already in the live engine catalog. Rows below are read-only for demo — interview questions match what taxpayers see on My Reliefs."
            : note?.trim()
              ? note
              : "Extract ran as a new draft. Live year views are unchanged until you activate — preview below shows merged results."}
          {outOfScopeCount != null && outOfScopeCount > 0
            ? alreadyInSystem
              ? ` ${outOfScopeCount} entity/business rows shown as rejected below.`
              : ` ${outOfScopeCount} entity/other rows hidden from this review.`
            : ""}
        </p>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium">Technical details</summary>
          <p className="mt-2 break-all font-mono">source {sourceDocId}</p>
        </details>
      </CardContent>
    </Card>
  );
}

export function groupReliefsBySection(reliefs: ReviewEntity[]): Array<[string, ReviewEntity[]]> {
  const buckets = new Map<string, ReviewEntity[]>();
  for (const relief of reliefs) {
    const key = reliefSectionTitle(relief);
    const list = buckets.get(key) ?? [];
    list.push(relief);
    buckets.set(key, list);
  }
  return Array.from(buckets.entries());
}
