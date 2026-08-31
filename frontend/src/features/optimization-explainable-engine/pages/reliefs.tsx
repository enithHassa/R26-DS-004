import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import { getGuideNotes, getReliefs } from "../api";
import { reliefListedForInterview } from "../compare-types";
import { formatMoneyInput, parseLkr, yaDisplay } from "../format-lkr";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";
import { useOeSnapshotPersistence } from "@/hooks/use-oe-snapshot";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";
import { getProfile } from "@/features/personalized-recommendation/api/profiles";
import {
  countReliefEvidence,
  hasPublishedEvidenceSnapshot,
  importProfileEvidence,
  ReliefEvidenceFromEntry,
  reliefRequiresReceipt,
  useEvidenceRevision,
} from "../relief-evidence";
import { useInterview } from "../session";
import { sortReliefsForInterview } from "../sort-reliefs";
import {
  hasSubItems,
  incomeBaseLkr,
  parseCap,
  previewAppliedLkr,
  resolveMinQualifyingAmount,
  resolveReliefCapAmount,
  subItemTotalLkr,
  totalIncomeLkr,
  type InterviewIncomeState,
  type ReliefAnswer,
  type ReliefCovers,
  type ReliefDefinition,
  type ReliefEntry,
} from "../types";

function sortReliefs(entries: ReliefEntry[]): ReliefEntry[] {
  return sortReliefsForInterview(entries);
}

function capAndIncomeCopy(
  cap: number,
  income: number,
  applied: number,
): { summary: string; hint: string } {
  const capAmt = `${formatMoneyInput(String(cap))} LKR`;
  const incomeAmt = `${formatMoneyInput(String(income))} LKR`;
  const appliedAmt = `${formatMoneyInput(String(applied))} LKR`;
  const summary =
    income <= cap
      ? `Your income (${incomeAmt}) is within the yearly cap of ${capAmt}, so ${appliedAmt} applies.`
      : `Limited to the yearly cap of ${capAmt}. Your income is ${incomeAmt}, so ${appliedAmt} applies.`;
  return {
    summary,
    hint: "This is the lower of the yearly cap and your income. Change income on the Income step to update this.",
  };
}

function capLine(entry: ReliefEntry, assessmentYear: string): string | null {
  if (entry.unit === "percent") {
    const rate = parseCap(entry.cap_amount);
    if (rate == null) return null;
    return `Rate for YA ${yaDisplay(assessmentYear)}: ${rate}%`;
  }
  if (entry.unit === "text") return null;
  const cap = resolveReliefCapAmount(entry);
  if (cap == null) return null;
  return `Cap for YA ${yaDisplay(assessmentYear)}: ${formatMoneyInput(String(cap))} LKR`;
}

function minQualifyingLine(entry: ReliefEntry, assessmentYear: string): string | null {
  if (entry.unit === "percent" || entry.unit === "text") return null;
  const minQ = resolveMinQualifyingAmount(entry);
  if (minQ == null) return null;
  return `Minimum qualifying spend for YA ${yaDisplay(assessmentYear)}: ${formatMoneyInput(String(minQ))} LKR`;
}

function draftsForEntry(
  entry: ReliefEntry,
  existing: ReliefAnswer | undefined,
  income: InterviewIncomeState,
): { amount: string; affirmed: boolean; components: Record<string, string> } {
  const needsYesNo =
    entry.input_kind === "yes_no_amount" || entry.input_kind === "boolean";
  const affirmed = existing?.affirmed ?? !needsYesNo;
  const components: Record<string, string> = {};
  for (const item of entry.sub_items ?? []) {
    components[item.component_id] = existing?.components?.[item.component_id] ?? "0";
  }
  if (entry.input_kind === "notice") {
    return {
      amount: String(previewAppliedLkr(entry, income, 0, true)),
      affirmed: true,
      components,
    };
  }
  return { amount: existing?.amount ?? "0", affirmed, components };
}

function claimedAmount(entry: ReliefEntry, answer: ReliefAnswer): number {
  if (answer.components && Object.keys(answer.components).length > 0) {
    return subItemTotalLkr(entry, answer.components);
  }
  return parseLkr(answer.amount);
}

/** Placeholder 0 / auto-filled notice is not a user answer. */
function hasRealClaim(entry: ReliefEntry, answer: ReliefAnswer): boolean {
  if (answer.skipped) return false;
  const kind = entry.input_kind;
  if (kind === "boolean") return answer.affirmed === true;
  if (kind === "yes_no_amount") {
    return answer.affirmed === true && claimedAmount(entry, answer) > 0;
  }
  if (kind === "notice") return false;
  return claimedAmount(entry, answer) > 0;
}

export function InterviewReliefsPage() {
  const { session } = useInterview();
  return (
    <ReliefsStepper
      key={`${session.assessmentYear}:${session.excludeSourceDocId ?? ""}`}
    />
  );
}

function ReliefsStepper() {
  const navigate = useNavigate();
  const { session, upsertReliefAnswer, clearReliefAnswer, setEvidenceCheck, replaceSession } =
    useInterview();
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const { saveDraft, loadLatestDraft, saveState, draftState, canPersist, errorMessage } =
    useOeSnapshotPersistence(activeProfileId);
  const { assessmentYear, reliefAnswers, income, excludeSourceDocId } = session;

  const reliefsQuery = useQuery({
    queryKey: [
      "optimization-explainable-engine",
      "reliefs",
      assessmentYear,
      excludeSourceDocId,
    ],
    queryFn: () => getReliefs(assessmentYear, excludeSourceDocId),
    enabled: Boolean(assessmentYear),
    retry: false,
  });

  const entries = sortReliefs(
    (reliefsQuery.data?.entries ?? []).filter((entry) =>
      reliefListedForInterview(entry, assessmentYear),
    ),
  );
  const profileQuery = useQuery({
    queryKey: ["profile", activeProfileId],
    queryFn: () => getProfile(activeProfileId!),
    enabled: Boolean(activeProfileId),
    retry: false,
  });

  useEffect(() => {
    if (!activeProfileId || !profileQuery.data) return;
    const stored = profileQuery.data.tax_return_detail as
      | { section6?: { reliefEvidenceByYear?: Record<string, Record<string, { id: string }[]>> } }
      | undefined;
    const published = stored?.section6?.reliefEvidenceByYear;
    if (hasPublishedEvidenceSnapshot(published)) {
      importProfileEvidence(
        activeProfileId,
        published as Parameters<typeof importProfileEvidence>[1],
      );
    }
  }, [activeProfileId, profileQuery.data]);
  const [step, setStep] = useState(0);
  const flushCurrentRef = useRef<() => void>(() => {});

  useEffect(() => {
    if (entries.length === 0) return;
    if (step >= entries.length) setStep(entries.length - 1);
  }, [entries.length, step]);

  const current = entries[step] ?? null;

  if (reliefsQuery.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading RAG reliefs for YA {yaDisplay(assessmentYear)}…
      </p>
    );
  }

  if (reliefsQuery.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive" role="alert">
          Could not load reliefs for YA {yaDisplay(assessmentYear)}. Confirm the
          service on port 8009 is running.
        </p>
        <Button type="button" variant="outline" onClick={() => void navigate(-1)}>
          Back
        </Button>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Reliefs</h2>
        <p className="text-sm text-muted-foreground">
          No RAG relief rows for YA {yaDisplay(assessmentYear)} yet.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable-engine/income")}
        >
          Back
        </Button>
        <Button
          type="button"
          onClick={() => void navigate("/optimization-explainable-engine/result")}
        >
          Calculate
        </Button>
      </div>
    );
  }

  if (!current) return null;

  const existing = reliefAnswers.find((a) => a.entry_id === current.entry_id);
  const initial = draftsForEntry(current, existing, income);

  return (
    <div className="space-y-4">
      <ActiveProfileBanner moduleLabel="Optimization reliefs" />
      {canPersist ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-3">
          <p className="flex-1 text-sm text-muted-foreground">
            Save or reload the interview draft for this taxpayer profile.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={draftState === "loading"}
            onClick={() =>
              void loadLatestDraft(session.assessmentYear).then((loaded) => {
                if (loaded) replaceSession(loaded);
              })
            }
          >
            {draftState === "loading" ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Loading…
              </>
            ) : (
              "Load saved draft"
            )}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={saveState === "loading"}
            onClick={() => void saveDraft(session)}
          >
            {saveState === "loading" ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Saving…
              </>
            ) : saveState === "done" ? (
              "Draft saved"
            ) : (
              "Save draft"
            )}
          </Button>
        </div>
      ) : null}
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
      <div className="flex flex-col gap-4 md:flex-row md:items-start">
      <ReliefJumpNav
        assessmentYear={assessmentYear}
        entries={entries}
        step={step}
        profileId={activeProfileId}
        onSelect={(index) => {
          if (index === step) return;
          flushCurrentRef.current();
          setStep(index);
        }}
      />
      <div className="min-w-0 flex-1">
        <ReliefStepCard
          key={current.entry_id}
          entry={current}
          assessmentYear={assessmentYear}
          entryCount={entries.length}
          step={step}
          income={income}
          initialAmount={initial.amount}
          initialAffirmed={initial.affirmed}
          initialComponents={initial.components}
          evidenceChecks={session.evidenceChecks[current.entry_id] ?? {}}
          onEvidenceCheck={(item, checked) =>
            setEvidenceCheck(current.entry_id, item, checked)
          }
          taxpayerProfileId={activeProfileId}
          onRegisterFlush={(flush) => {
            flushCurrentRef.current = flush;
          }}
          onFlush={upsertReliefAnswer}
          onClear={clearReliefAnswer}
          onBack={() => {
            flushCurrentRef.current();
            if (step <= 0) {
              void navigate("/optimization-explainable-engine/income");
              return;
            }
            setStep((s) => s - 1);
          }}
          onSave={(answer, advanceToDone) => {
            if (answer.skipped || hasRealClaim(current, answer)) {
              upsertReliefAnswer(answer);
            } else {
              clearReliefAnswer(answer.entry_id);
            }
            if (advanceToDone) {
              void navigate("/optimization-explainable-engine/result");
              return;
            }
            setStep((s) => s + 1);
          }}
        />
      </div>
    </div>
    </div>
  );
}

function ReliefJumpNav({
  assessmentYear,
  entries,
  step,
  profileId,
  onSelect,
}: {
  assessmentYear: string;
  entries: ReliefEntry[];
  step: number;
  profileId: string | null;
  onSelect: (index: number) => void;
}) {
  const revision = useEvidenceRevision();
  return (
    <aside className="md:sticky md:top-3 md:w-60 md:shrink-0">
      <nav
        className="rounded-md border bg-background"
        aria-label={`Reliefs for YA ${yaDisplay(assessmentYear)}`}
      >
        <div className="border-b px-3 py-2">
          <p className="text-xs font-medium">
            {entries.length} reliefs · YA {yaDisplay(assessmentYear)}
          </p>
          <p className="text-[11px] text-muted-foreground">
            Jump to any relief. The list comes from this year’s RAG catalog,
            including newly activated Acts. Receipt badges show files this
            taxpayer uploaded for the year.
          </p>
        </div>
        <ol className="flex max-h-40 gap-1 overflow-x-auto p-2 md:max-h-[min(32rem,calc(100vh-12rem))] md:flex-col md:overflow-y-auto">
          {entries.map((entry, index) => {
            const current = index === step;
            const needsReceipt = reliefRequiresReceipt(entry);
            const loaded =
              needsReceipt &&
              countReliefEvidence(
                profileId,
                assessmentYear,
                entry.compare_group_id,
                entry.display_name,
              ) > 0;
            return (
              <li key={`${entry.entry_id}-${revision}`} className="shrink-0 md:shrink">
                <button
                  type="button"
                  aria-current={current ? "step" : undefined}
                  onClick={() => onSelect(index)}
                  className={cn(
                    "flex w-full min-w-[11rem] items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors md:min-w-0",
                    current
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 w-5 shrink-0 text-[10px] font-medium tabular-nums",
                      current ? "text-primary-foreground" : "text-muted-foreground",
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="line-clamp-2 min-w-0 flex-1 font-medium leading-snug">
                    {entry.display_name}
                  </span>
                  {needsReceipt ? (
                    <span
                      className={cn(
                        "mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                        loaded
                          ? current
                            ? "bg-primary-foreground/20 text-primary-foreground"
                            : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                          : current
                            ? "bg-primary-foreground/10 text-primary-foreground/80"
                            : "bg-muted text-muted-foreground",
                      )}
                    >
                      {loaded ? "Image" : "No img"}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
    </aside>
  );
}

/**
 * Whether a filer qualifies can turn on a term the Act defines pages away, so
 * the test is shown here in the Act's own words rather than paraphrased.
 */
function DefinitionsBlock({
  definitions,
  actName,
}: {
  definitions: ReliefDefinition[];
  actName: string;
}) {
  const section = definitions.find((d) => d.section_ref)?.section_ref ?? "";
  return (
    <div className="space-y-2 rounded-md border p-3 text-xs">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">What the Act means by this</p>
        <p className="text-muted-foreground">
          These terms decide whether this relief is yours to claim.
        </p>
      </div>
      {definitions.map((definition) => (
        <div key={definition.term} className="space-y-0.5">
          <p className="font-medium capitalize">{definition.term}</p>
          <p className="italic text-muted-foreground">“{definition.text}”</p>
        </div>
      ))}
      <p className="border-t pt-2 text-[11px] text-muted-foreground">
        {actName}
        {section ? ` · Section ${section} (interpretation)` : ""}
      </p>
    </div>
  );
}

/**
 * A relief that names only "items (i) and (v)" of another paragraph is unreadable
 * on its own, so the items it points at are spelled out from the compiled source
 * paragraph instead of leaving the filer to look them up.
 */
function CoveredItemsBlock({ covers }: { covers: ReliefCovers }) {
  return (
    <div className="space-y-2 rounded-md border p-3 text-xs">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">What this covers</p>
        <p className="text-muted-foreground">
          The Act limits this to the following items of paragraph{" "}
          {covers.paragraph_ref}:
        </p>
      </div>
      <ul className="space-y-1">
        {covers.items.map((item) => (
          <li key={item.component_id} className="flex gap-2" title={item.quote}>
            <span className="text-muted-foreground">({item.roman})</span>
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
      <p className="border-t pt-2 text-[11px] text-muted-foreground">
        From {covers.source_display_name} · {covers.source_act_name} ·{" "}
        {covers.source_section_ref}
      </p>
    </div>
  );
}

function fieldId(componentId: string): string {
  return `oe-sub-${componentId.replace(/[^\w-]/g, "-")}`;
}

/**
 * Reliefs the Act enumerates get one box per listed recipient inside the same
 * card, so a filer who gave to several of them keeps the split visible instead
 * of pre-adding the total themselves.
 */
function SubItemAmounts({
  entry,
  values,
  onChange,
  total,
  applied,
  cap,
}: {
  entry: ReliefEntry;
  values: Record<string, string>;
  onChange: (componentId: string, value: string) => void;
  total: number;
  applied: number;
  cap: number | null;
}) {
  return (
    <div className="space-y-3 rounded-md border border-dashed p-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">Amount by recipient (LKR)</p>
        <p className="text-xs text-muted-foreground">
          The Act lists these separately. Fill in only the ones you gave to — they
          are added together below.
        </p>
      </div>
      <ul className="space-y-2">
        {(entry.sub_items ?? []).map((item) => (
          <li
            key={item.component_id}
            className="grid gap-1 sm:grid-cols-[1fr_11rem] sm:items-center sm:gap-3"
          >
            <Label
              htmlFor={fieldId(item.component_id)}
              className="text-sm font-normal leading-snug"
              title={item.quote}
            >
              <span className="mr-1 text-muted-foreground">({item.roman})</span>
              {item.label}
            </Label>
            <Input
              id={fieldId(item.component_id)}
              inputMode="numeric"
              value={formatMoneyInput(values[item.component_id] ?? "")}
              onChange={(e) => onChange(item.component_id, formatMoneyInput(e.target.value))}
              placeholder="0"
            />
          </li>
        ))}
      </ul>
      <p className="border-t pt-2 text-sm">
        Combined claim:{" "}
        <span className="font-medium">{formatMoneyInput(String(total))} LKR</span>
        {cap != null && applied !== total ? (
          <span className="text-muted-foreground">
            {" "}
            · after cap {formatMoneyInput(String(applied))} LKR
          </span>
        ) : null}
      </p>
    </div>
  );
}

function ReliefStepCard({
  entry,
  assessmentYear,
  entryCount,
  step,
  income,
  initialAmount,
  initialAffirmed,
  initialComponents,
  evidenceChecks,
  onEvidenceCheck,
  taxpayerProfileId,
  onRegisterFlush,
  onFlush,
  onClear,
  onBack,
  onSave,
}: {
  entry: ReliefEntry;
  assessmentYear: string;
  entryCount: number;
  step: number;
  income: InterviewIncomeState;
  initialAmount: string;
  initialAffirmed: boolean;
  initialComponents: Record<string, string>;
  evidenceChecks: Record<string, boolean>;
  onEvidenceCheck: (item: string, checked: boolean) => void;
  taxpayerProfileId: string | null;
  onRegisterFlush: (flush: () => void) => void;
  onFlush: (answer: ReliefAnswer) => void;
  onClear: (entryId: string) => void;
  onBack: () => void;
  onSave: (answer: ReliefAnswer, advanceToDone: boolean) => void;
}) {
  const [amountDraft, setAmountDraft] = useState(initialAmount);
  const [affirmedDraft, setAffirmedDraft] = useState(initialAffirmed);
  const [componentsDraft, setComponentsDraft] = useState(initialComponents);
  const draftsRef = useRef({ amountDraft, affirmedDraft, componentsDraft });
  draftsRef.current = { amountDraft, affirmedDraft, componentsDraft };

  const split = hasSubItems(entry);
  const totalIncome = totalIncomeLkr(income);
  const claimLkr = split
    ? subItemTotalLkr(entry, componentsDraft)
    : parseLkr(amountDraft);
  const applied = previewAppliedLkr(entry, income, claimLkr, affirmedDraft);
  const incomeBase = incomeBaseLkr(entry, income);
  const kind = entry.input_kind;
  const needsYesNo = kind === "yes_no_amount" || kind === "boolean";
  const derivedAmount =
    kind === "notice" ||
    entry.engine_binding?.kind === "senior_citizen_interest_relief" ||
    entry.unit === "percent";
  const showAmount =
    !split &&
    (kind === "amount" || (kind === "yes_no_amount" && affirmedDraft && !derivedAmount));
  const showSubItems = split && (!needsYesNo || affirmedDraft);
  const cap = resolveReliefCapAmount(entry);
  const minQualifying = resolveMinQualifyingAmount(entry);
  const last = step + 1 >= entryCount;
  const belowMinimum =
    minQualifying != null && claimLkr > 0 && claimLkr < minQualifying;
  const capIncomeCopy =
    cap != null
      ? capAndIncomeCopy(cap, incomeBase || totalIncome, applied)
      : null;

  useEffect(() => {
    onRegisterFlush(() => {
      const drafts = draftsRef.current;
      const splitItems = hasSubItems(entry);
      const kindNow = entry.input_kind;
      const needsYesNoNow = kindNow === "yes_no_amount" || kindNow === "boolean";
      const claim = splitItems
        ? subItemTotalLkr(entry, drafts.componentsDraft)
        : parseLkr(drafts.amountDraft);
      const appliedNow = previewAppliedLkr(
        entry,
        income,
        claim,
        drafts.affirmedDraft,
      );
      const answer = {
        entry_id: entry.entry_id,
        compare_group_id: entry.compare_group_id,
        amount: String(appliedNow),
        affirmed: needsYesNoNow ? drafts.affirmedDraft : true,
        skipped: false,
        components: splitItems ? drafts.componentsDraft : undefined,
      };
      if (hasRealClaim(entry, answer)) {
        onFlush(answer);
      } else {
        onClear(entry.entry_id);
      }
    });
  }, [entry, income, onClear, onFlush, onRegisterFlush]);

  function save(skipped: boolean): void {
    if (skipped) {
      onSave(
        {
          entry_id: entry.entry_id,
          compare_group_id: entry.compare_group_id,
          amount: "0",
          affirmed: false,
          skipped: true,
        },
        last,
      );
      return;
    }
    onSave(
      {
        entry_id: entry.entry_id,
        compare_group_id: entry.compare_group_id,
        amount: String(applied),
        affirmed: needsYesNo ? affirmedDraft : true,
        skipped: false,
        components: split ? componentsDraft : undefined,
      },
      last,
    );
  }

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 -mx-1 rounded-md border bg-background/95 px-3 py-2 text-xs backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-medium">
              {entryCount} reliefs for YA {yaDisplay(assessmentYear)}
            </span>
            <span className="mx-1.5 text-muted-foreground">·</span>
            <span className="text-muted-foreground">
              Question {step + 1} of {entryCount}
            </span>
          </div>
          <span className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">
            From RAG index
          </span>
        </div>
      </div>

      <div className="space-y-4 rounded-md border p-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {entry.display_name}
          </p>
          <h2 className="text-lg font-semibold leading-snug">{entry.question_prompt}</h2>
          {entry.help ? (
            <p className="text-sm text-muted-foreground">{entry.help}</p>
          ) : null}
          {entry.auto_applied && kind === "notice" ? (
            <p className="text-xs text-muted-foreground">
              Auto-applied statutory relief — no claim amount required.
            </p>
          ) : null}
          {capLine(entry, assessmentYear) ? (
            <p className="text-xs text-muted-foreground">
              {capLine(entry, assessmentYear)}
            </p>
          ) : null}
          {minQualifyingLine(entry, assessmentYear) ? (
            <p className="text-xs text-muted-foreground">
              {minQualifyingLine(entry, assessmentYear)}
            </p>
          ) : null}
          {belowMinimum ? (
            <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
              Claimed {formatMoneyInput(String(claimLkr))} LKR is below the Act minimum of{" "}
              {formatMoneyInput(String(minQualifying))} LKR — no relief applies (0 LKR).
            </p>
          ) : null}
          {cap != null && entry.unit !== "percent" && entry.unit !== "text" && capIncomeCopy ? (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{capIncomeCopy.summary}</span>
            </p>
          ) : null}
          {entry.unit === "percent" && cap != null ? (
            <p className="text-xs text-muted-foreground">
              Calculated as {cap}% of{" "}
              <span className="font-medium text-foreground">
                {formatMoneyInput(String(incomeBase))} LKR
              </span>
              , which is{" "}
              <span className="font-medium text-foreground">
                {formatMoneyInput(String(applied))} LKR
              </span>
              .
            </p>
          ) : null}
        </div>

        {kind === "notice" ? (
          <div className="max-w-xs space-y-2">
            <Label htmlFor="oe-relief-applied">Relief that applies (LKR)</Label>
            <Input
              id="oe-relief-applied"
              inputMode="numeric"
              readOnly
              value={formatMoneyInput(String(applied))}
              className="bg-muted/40"
            />
            <p className="text-xs text-muted-foreground">
              {capIncomeCopy?.hint ??
                "Change income on the Income step to update this."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {needsYesNo ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={affirmedDraft ? "default" : "outline"}
                  onClick={() => setAffirmedDraft(true)}
                >
                  Yes
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={!affirmedDraft ? "default" : "outline"}
                  onClick={() => setAffirmedDraft(false)}
                >
                  No
                </Button>
              </div>
            ) : null}
            {derivedAmount && affirmedDraft && kind !== "notice" ? (
              <div className="max-w-xs space-y-2">
                <Label htmlFor="oe-relief-derived">Relief that applies (LKR)</Label>
                <Input
                  id="oe-relief-derived"
                  inputMode="numeric"
                  readOnly
                  value={formatMoneyInput(String(applied))}
                  className="bg-muted/40"
                />
              </div>
            ) : null}
            {showSubItems ? (
              <SubItemAmounts
                entry={entry}
                values={componentsDraft}
                onChange={(componentId, value) =>
                  setComponentsDraft((prev) => ({ ...prev, [componentId]: value }))
                }
                total={claimLkr}
                applied={applied}
                cap={cap}
              />
            ) : null}
            {showAmount ? (
              <div className="max-w-xs space-y-2">
                <Label htmlFor="oe-relief-amount">Amount (LKR)</Label>
                <Input
                  id="oe-relief-amount"
                  inputMode="numeric"
                  value={formatMoneyInput(amountDraft)}
                  onChange={(e) => setAmountDraft(formatMoneyInput(e.target.value))}
                  placeholder="0"
                />
                {cap != null && entry.unit !== "percent" ? (
                  <p className="text-xs text-muted-foreground">
                    After cap:{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(applied))} LKR
                    </span>
                  </p>
                ) : null}
                {belowMinimum ? (
                  <p className="text-xs text-muted-foreground">
                    Applied after minimum:{" "}
                    <span className="font-medium text-foreground">0 LKR</span>
                  </p>
                ) : minQualifying != null && !belowMinimum && claimLkr > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Qualifies (at/above minimum) — applied{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(applied))} LKR
                    </span>
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        )}

        {entry.definitions?.length ? (
          <DefinitionsBlock definitions={entry.definitions} actName={entry.act_name} />
        ) : null}

        {entry.covers ? <CoveredItemsBlock covers={entry.covers} /> : null}

        <div className="rounded-md border bg-muted/30 p-3 text-[11px] text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">Legal source (this YA)</p>
          <p>
            {entry.act_name} · {entry.section_ref} · {entry.source_doc_id}
          </p>
          {entry.quote ? <p className="italic">“{entry.quote}”</p> : null}
        </div>

        <HonestyBlock entry={entry} />
        <DocumentsChecklist
          items={entry.required_evidence ?? []}
          checks={evidenceChecks}
          onCheck={onEvidenceCheck}
        />
        <ReliefEvidenceFromEntry
          profileId={taxpayerProfileId}
          assessmentYear={assessmentYear}
          entry={entry}
          mode="auditor"
        />
        <GuideNotesBox
          compareGroupId={entry.compare_group_id}
          assessmentYear={assessmentYear}
          actCap={entry.unit === "percent" || entry.unit === "text" ? null : cap}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" variant="ghost" onClick={() => save(true)}>
          Skip
        </Button>
        <Button type="button" onClick={() => save(false)}>
          {last ? "Calculate" : "Next"}
        </Button>
      </div>
    </div>
  );
}

function HonestyBlock({ entry }: { entry: ReliefEntry }) {
  const raw = entry.eligibility_text?.trim() ?? "";
  const whoFor = raw ? friendlyEligibility(raw) : null;
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
      <p className="font-medium">Who this is for</p>
      <p className="mt-1 opacity-90">
        {whoFor ?? "Check that this relief fits your situation before you claim it."}
      </p>
      <p className="mt-1 text-[11px] opacity-80">
        The rupee amount above comes from the Act. This box does not change it. By
        continuing you are saying you think you qualify — this tool does not check
        that for you.
      </p>
    </div>
  );
}

function friendlyEligibility(raw: string): string {
  let text = raw.trim();
  text = text.replace(
    /^for each year of assessment commencing on or after /i,
    "This applies to tax years starting on or after ",
  );
  text = text.replace(
    /year of assessment commencing on or after /gi,
    "tax years starting on or after ",
  );
  text = text.replace(/commencing on or after /gi, "starting on or after ");
  text = text.replace(/year of assessment/gi, "tax year");
  if (!/[.!?]$/.test(text)) text += ".";
  return text;
}

function DocumentsChecklist({
  items,
  checks,
  onCheck,
}: {
  items: string[];
  checks: Record<string, boolean>;
  onCheck: (item: string, checked: boolean) => void;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-xs font-medium">Documents checklist</p>
      <p className="text-[11px] text-muted-foreground">
        Tick what you have. This does not change tax — it is a reminder only.
      </p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item}>
            <label className="flex items-start gap-2 text-sm">
              <Checkbox
                className="mt-0.5"
                checked={Boolean(checks[item])}
                onChange={(event) => onCheck(item, event.target.checked)}
              />
              <span>{item}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

function rupeeAmountsIn(text: string): number[] {
  const found: number[] = [];
  const pattern = /Rs\.?\s*([\d,]+)/gi;
  for (const match of text.matchAll(pattern)) {
    const n = Number((match[1] ?? "").replace(/,/g, ""));
    if (Number.isFinite(n) && n >= 1000) found.push(n);
  }
  return found;
}

function helpConflictsWithYearCap(help: string | undefined, actCap: number | null): boolean {
  if (actCap == null || !help) return false;
  return rupeeAmountsIn(help).some((amount) => amount !== actCap);
}

function GuideNotesBox({
  compareGroupId,
  assessmentYear,
  actCap,
}: {
  compareGroupId: string;
  assessmentYear: string;
  actCap: number | null;
}) {
  const notesQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "guide-notes", compareGroupId],
    queryFn: () => getGuideNotes(compareGroupId),
    retry: false,
  });
  const notes = notesQuery.data?.notes ?? [];
  if (notesQuery.isLoading) {
    return (
      <p className="text-[11px] text-muted-foreground">Loading Guide notes…</p>
    );
  }
  if (notes.length === 0) {
    return (
      <p className="text-[11px] text-muted-foreground">
        No Guide note for this relief. Load the Guide fixture on Load new act if you
        want help text here.
      </p>
    );
  }
  const yearCapLabel =
    actCap != null ? `${formatMoneyInput(String(actCap))} LKR` : null;
  return (
    <div className="space-y-2 rounded-md border border-sky-200 bg-sky-50 p-3 text-xs dark:border-sky-900 dark:bg-sky-950/40">
      <p className="font-medium text-sky-950 dark:text-sky-100">
        Guide <span className="font-normal opacity-80">(help only — not a cap)</span>
      </p>
      {yearCapLabel ? (
        <p>
          For YA {yaDisplay(assessmentYear)} the Act sets this relief at{" "}
          <span className="font-medium">{yearCapLabel}</span>. The Guide does not
          change that amount.
        </p>
      ) : null}
      {notes.map((note) => {
        const staleHelp = helpConflictsWithYearCap(note.help, actCap);
        return (
          <div key={`${note.source_doc_id}-${note.display_name}`} className="space-y-1">
            <p className="font-medium">{note.display_name}</p>
            {staleHelp ? (
              <p>
                The Guide explains who qualifies. Its rupee figure is from an earlier
                Fifth Schedule and is not the YA {yaDisplay(assessmentYear)} cap.
              </p>
            ) : note.help ? (
              <p>{note.help}</p>
            ) : null}
            {note.quote ? (
              <p className="italic opacity-80">
                {staleHelp ? (
                  <span className="not-italic font-medium opacity-100">
                    Guide PDF wording (older figure):{" "}
                  </span>
                ) : null}
                “{note.quote}”
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
