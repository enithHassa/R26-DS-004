import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { getReliefs } from "../api";
import { formatMoneyInput, parseLkr, yaDisplay } from "../format-lkr";
import { useInterview } from "../session";
import {
  incomeBaseLkr,
  parseCap,
  previewAppliedLkr,
  totalIncomeLkr,
  type InterviewIncomeState,
  type ReliefAnswer,
  type ReliefEntry,
} from "../types";

function sortReliefs(entries: ReliefEntry[]): ReliefEntry[] {
  return [...entries].sort(
    (a, b) => a.sort_order - b.sort_order || a.entry_id.localeCompare(b.entry_id),
  );
}

function capLine(entry: ReliefEntry, assessmentYear: string): string | null {
  const cap = parseCap(entry.cap_amount);
  if (cap == null) return null;
  if (entry.unit === "percent") {
    return `Rate for YA ${yaDisplay(assessmentYear)}: ${cap}%`;
  }
  if (entry.unit === "text") return null;
  return `Cap for YA ${yaDisplay(assessmentYear)}: ${formatMoneyInput(String(cap))} LKR`;
}

function draftsForEntry(
  entry: ReliefEntry,
  existing: ReliefAnswer | undefined,
  income: InterviewIncomeState,
): { amount: string; affirmed: boolean } {
  const needsYesNo =
    entry.input_kind === "yes_no_amount" || entry.input_kind === "boolean";
  const affirmed = existing?.affirmed ?? !needsYesNo;
  if (entry.input_kind === "notice") {
    return {
      amount: String(previewAppliedLkr(entry, income, 0, true)),
      affirmed: true,
    };
  }
  return { amount: existing?.amount ?? "0", affirmed };
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
  const { session, upsertReliefAnswer } = useInterview();
  const { assessmentYear, reliefAnswers, income, excludeSourceDocId } = session;

  const reliefsQuery = useQuery({
    queryKey: [
      "optimization-explainable",
      "reliefs",
      assessmentYear,
      excludeSourceDocId,
    ],
    queryFn: () => getReliefs(assessmentYear, excludeSourceDocId),
    enabled: Boolean(assessmentYear),
    retry: false,
  });

  const entries = sortReliefs(reliefsQuery.data?.entries ?? []);
  const [step, setStep] = useState(0);

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
          service on port 8008 is running.
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
          onClick={() => void navigate("/optimization-explainable/income")}
        >
          Back
        </Button>
        <Button
          type="button"
          onClick={() => void navigate("/optimization-explainable/result")}
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
    <ReliefStepCard
      key={current.entry_id}
      entry={current}
      assessmentYear={assessmentYear}
      entryCount={entries.length}
      step={step}
      income={income}
      initialAmount={initial.amount}
      initialAffirmed={initial.affirmed}
      onBack={() => {
        if (step <= 0) {
          void navigate("/optimization-explainable/income");
          return;
        }
        setStep((s) => s - 1);
      }}
      onSave={(answer, advanceToDone) => {
        upsertReliefAnswer(answer);
        if (advanceToDone) {
          void navigate("/optimization-explainable/result");
          return;
        }
        setStep((s) => s + 1);
      }}
    />
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
  onBack: () => void;
  onSave: (answer: ReliefAnswer, advanceToDone: boolean) => void;
}) {
  const [amountDraft, setAmountDraft] = useState(initialAmount);
  const [affirmedDraft, setAffirmedDraft] = useState(initialAffirmed);

  const totalIncome = totalIncomeLkr(income);
  const claimLkr = parseLkr(amountDraft);
  const applied = previewAppliedLkr(entry, income, claimLkr, affirmedDraft);
  const incomeBase = incomeBaseLkr(entry, income);
  const kind = entry.input_kind;
  const needsYesNo = kind === "yes_no_amount" || kind === "boolean";
  const derivedAmount =
    kind === "notice" ||
    entry.engine_binding?.kind === "senior_citizen_interest_relief" ||
    entry.unit === "percent";
  const showAmount =
    kind === "amount" || (kind === "yes_no_amount" && affirmedDraft && !derivedAmount);
  const cap = parseCap(entry.cap_amount);
  const last = step + 1 >= entryCount;

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
          {cap != null && entry.unit !== "percent" && entry.unit !== "text" ? (
            <p className="text-xs text-muted-foreground">
              Applies as{" "}
              <span className="font-medium text-foreground">
                min(cap {formatMoneyInput(String(cap))}, income{" "}
                {formatMoneyInput(String(incomeBase || totalIncome))})
              </span>
              {" → "}
              <span className="font-medium text-foreground">
                {formatMoneyInput(String(applied))} LKR
              </span>
            </p>
          ) : null}
          {entry.unit === "percent" && cap != null ? (
            <p className="text-xs text-muted-foreground">
              Applies as{" "}
              <span className="font-medium text-foreground">
                {cap}% of {formatMoneyInput(String(incomeBase))}
              </span>
              {" → "}
              <span className="font-medium text-foreground">
                {formatMoneyInput(String(applied))} LKR
              </span>
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
              Auto-filled as{" "}
              <span className="font-medium text-foreground">
                min(Rs {formatMoneyInput(String(cap ?? 0))}, income{" "}
                {formatMoneyInput(String(incomeBase))})
              </span>
              . Change income on the Income step to update this.
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
              </div>
            ) : null}
          </div>
        )}

        <div className="rounded-md border bg-muted/30 p-3 text-[11px] text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">Provenance (this YA)</p>
          <p>
            {entry.act_name} · {entry.section_ref} · {entry.source_doc_id}
          </p>
          {entry.quote ? <p className="italic">“{entry.quote}”</p> : null}
        </div>
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
