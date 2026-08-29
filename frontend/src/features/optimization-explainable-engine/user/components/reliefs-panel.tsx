import { Link } from "react-router-dom";
import { Check, Loader2 } from "lucide-react";

import { formatLkr, parseLkr, yaDisplay } from "../../format-lkr";
import { previewAppliedLkr, type ReliefAnswer, type ReliefEntry } from "../../types";
import { sortReliefsForInterview } from "../../sort-reliefs";
import { OeNavChips } from "./oe-nav-chips";
import { UvPanelShell, YaSelector } from "./uv-chrome";
import { useTaxpayerOe } from "../taxpayer-oe-context";
import { TAXWISE_OE_RESULT } from "../paths";

function answerFor(
  answers: ReliefAnswer[],
  entry: ReliefEntry,
): ReliefAnswer | undefined {
  return answers.find((a) => a.entry_id === entry.entry_id);
}

function ClaimToggle({
  active,
  incomplete,
  locked,
  onToggle,
}: {
  active: boolean;
  incomplete: boolean;
  locked: boolean;
  onToggle: () => void;
}) {
  const label = incomplete ? "Enter amount" : active ? "Claimed" : "Not claimed";
  return (
    <button
      type="button"
      disabled={locked}
      onClick={onToggle}
      aria-pressed={active || incomplete}
      className={[
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
        incomplete
          ? "border-amber-400/50 bg-amber-500/15 text-amber-300"
          : active
            ? "border-emerald-400/50 bg-emerald-500/20 text-emerald-300"
            : "border-[var(--uv-border)] bg-transparent text-[var(--uv-text-muted)] hover:border-[var(--uv-text-muted)] hover:text-[var(--uv-text)]",
        locked ? "cursor-not-allowed opacity-60" : "cursor-pointer",
      ].join(" ")}
    >
      <span
        className={[
          "flex h-4 w-4 items-center justify-center rounded-sm border",
          incomplete
            ? "border-amber-400 bg-amber-400 text-[var(--uv-bg)]"
            : active
              ? "border-emerald-400 bg-emerald-400 text-[var(--uv-bg)]"
              : "border-[var(--uv-text-muted)] bg-transparent",
        ].join(" ")}
        aria-hidden
      >
        {active || incomplete ? <Check className="h-3 w-3 stroke-[3]" /> : null}
      </span>
      {label}
    </button>
  );
}

function entryNeedsAmount(entry: ReliefEntry): boolean {
  if (entry.unit === "percent") return false;
  if (isAutomaticRelief(entry)) return false;
  return entry.input_kind === "amount" || entry.input_kind === "yes_no_amount";
}

/** Statutory notice / personal relief — engine applies without a taxpayer claim toggle. */
function isAutomaticRelief(entry: ReliefEntry): boolean {
  if (entry.auto_applied) return true;
  if (entry.input_kind === "notice") return true;
  const group = (entry.compare_group_id ?? "").toLowerCase();
  if (group === "personal_relief") return true;
  const prompt = `${entry.question_prompt ?? ""} ${entry.display_name ?? ""}`.toLowerCase();
  return prompt.includes("applies automatically");
}

function AutoAppliedBadge({ amountLabel }: { amountLabel: string }) {
  return (
    <div className="inline-flex shrink-0 flex-col items-end gap-1">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/45 bg-sky-500/15 px-3 py-1.5 text-xs font-semibold text-sky-300">
        <span
          className="flex h-4 w-4 items-center justify-center rounded-sm border border-sky-400 bg-sky-400 text-[var(--uv-bg)]"
          aria-hidden
        >
          <Check className="h-3 w-3 stroke-[3]" />
        </span>
        Applied automatically
      </span>
      <span className="text-[11px] text-[var(--uv-text-muted)]">{amountLabel}</span>
    </div>
  );
}

export function ReliefsPanel() {
  const {
    scenario,
    isLoading,
    isError,
    selectYear,
    assessmentYear,
    patchClaims,
  } = useTaxpayerOe();

  if (isError) {
    return (
      <p className="text-sm text-red-400" role="alert">
        Could not load reliefs. Confirm Comp 3 (:8003) and OE Engine (:8009) are running, then
        refresh.
      </p>
    );
  }

  if (isLoading || !scenario) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading reliefs…
      </p>
    );
  }

  const ya = assessmentYear ?? scenario.assessmentYear;
  const answers = scenario.session.reliefAnswers;
  // Keep automatic (notice / personal) rows visible — they apply without a claim toggle.
  const entries = sortReliefsForInterview(scenario.reliefEntries);
  const locked = Boolean(scenario.finalized);

  function toggle(entry: ReliefEntry) {
    if (locked) return;
    const existing = answerFor(answers, entry);
    if (existing && !existing.skipped) {
      patchClaims(answers.filter((a) => a.entry_id !== entry.entry_id));
      return;
    }
    const priorAmt = parseLkr(existing?.amount ?? "0");
    const next: ReliefAnswer = {
      entry_id: entry.entry_id,
      compare_group_id: entry.compare_group_id,
      affirmed: true,
      // Don't seed amount-based claims with "0" — that looks "Claimed" but applies nothing.
      amount:
        priorAmt > 0
          ? String(priorAmt)
          : entryNeedsAmount(entry)
            ? ""
            : entry.cap_amount && entry.unit !== "percent"
              ? entry.cap_amount
              : "0",
      skipped: false,
    };
    patchClaims([...answers.filter((a) => a.entry_id !== entry.entry_id), next]);
  }

  function setAmount(entry: ReliefEntry, amount: string) {
    if (locked) return;
    const existing = answerFor(answers, entry);
    const next: ReliefAnswer = {
      entry_id: entry.entry_id,
      compare_group_id: entry.compare_group_id,
      affirmed: true,
      amount,
      skipped: false,
      components: existing?.components,
    };
    patchClaims([...answers.filter((a) => a.entry_id !== entry.entry_id), next]);
  }

  return (
    <UvPanelShell
      header={
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <OeNavChips />
            <h2 className="mt-3 text-lg font-semibold">My Reliefs</h2>
            <p className="text-sm text-[var(--uv-text-muted)]">
              YA {yaDisplay(ya)} catalog
              {locked
                ? " — showing auditor-approved claims (read-only)."
                : " — suggested from your profile; toggle or adjust amounts."}
            </p>
          </div>
          <YaSelector value={ya} years={scenario.availableYears} onChange={selectYear} />
        </div>
      }
    >
      {entries.length === 0 ? (
        <p className="text-sm text-[var(--uv-text-muted)]">
          No claimable relief rows for this year yet. Confirm OE Engine has a promoted year view.
        </p>
      ) : (
        <ul className="space-y-3">
          {entries.map((entry) => {
            const automatic = isAutomaticRelief(entry);
            const ans = answerFor(answers, entry);
            const selected = Boolean(ans && !ans.skipped);
            const claimAmt = parseLkr(ans?.amount ?? "0");
            const incomplete =
              !automatic && selected && entryNeedsAmount(entry) && claimAmt <= 0;
            const active = !automatic && selected && !incomplete;
            const preview = previewAppliedLkr(
              entry,
              scenario.session.income,
              automatic ? 0 : claimAmt,
              automatic ? true : (ans?.affirmed ?? selected),
            );
            const capLabel =
              entry.unit === "percent" && entry.cap_amount
                ? `Rate ${entry.cap_amount}%`
                : entry.cap_amount
                  ? `Cap ${formatLkr(entry.cap_amount)}`
                  : "";
            return (
              <li
                key={entry.entry_id}
                className={[
                  "rounded-xl border p-4 transition-colors",
                  automatic
                    ? "border-sky-500/35 bg-sky-500/5"
                    : incomplete
                      ? "border-amber-500/35 bg-amber-500/5"
                      : active
                        ? "border-emerald-500/35 bg-emerald-500/5"
                        : "border-[var(--uv-border)] bg-[var(--uv-bg-card)]",
                ].join(" ")}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      {entry.question_prompt || entry.display_name}
                    </p>
                    <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
                      {entry.display_name}
                      {capLabel ? ` · ${capLabel}` : ""}
                    </p>
                    {automatic ? (
                      <p className="mt-1 text-xs text-sky-300/90">
                        Statutory relief — included in your tax calculation with no claim needed.
                      </p>
                    ) : null}
                  </div>
                  {automatic ? (
                    <AutoAppliedBadge amountLabel={`Est. applied: ${formatLkr(preview)}`} />
                  ) : (
                    <ClaimToggle
                      active={active}
                      incomplete={incomplete}
                      locked={locked}
                      onToggle={() => toggle(entry)}
                    />
                  )}
                </div>
                {!automatic && selected ? (
                  <div className="mt-3 flex flex-wrap items-end gap-3">
                    <label className="text-xs text-[var(--uv-text-muted)]">
                      Amount (LKR)
                      <input
                        type="text"
                        disabled={locked}
                        value={ans?.amount ?? ""}
                        onChange={(e) => setAmount(entry, e.target.value)}
                        placeholder="Enter amount"
                        className="mt-1 block w-40 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)] px-3 py-1.5 text-sm text-[var(--uv-text)]"
                      />
                    </label>
                    <p className="text-xs text-[var(--uv-text-muted)]">
                      Est. applied:{" "}
                      <span className="text-[var(--uv-accent)]">{formatLkr(preview)}</span>
                    </p>
                    {incomplete ? (
                      <p className="basis-full text-xs text-amber-300">
                        Marked for claim, but amount is 0 — enter an amount or turn claim off.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <Link
        to={TAXWISE_OE_RESULT}
        className="inline-flex w-fit rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)]"
      >
        Continue to result
      </Link>
    </UvPanelShell>
  );
}
