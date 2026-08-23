import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  getReliefInterviewApproved,
  type ReliefInterviewApprovedYear,
} from "../../api";
import { formatMoneyInput } from "../../format-lkr";
import {
  sortEntries,
  isUnconfirmedTransitionalCarry,
  type ApprovedEntry,
  type ReliefAnswer,
} from "./catalog-types";
import { parseLkr } from "./income-cards";
import {
  isListedPublicDoneeGroup,
  listedDoneeMeta,
  LISTED_DONEES_BLOCK_PROMPT,
  LISTED_DONEES_HELP,
  sortListedDoneeEntries,
} from "./listed-donees";
import {
  IRD_APPROVED_CHARITY_LIST_URL,
  isApprovedCharityDonationGroup,
} from "./approved-charity-donation";
import { isBankMergerQpGroup } from "./bank-merger-qp";
import { isEntityCharityDonationGroup } from "./entity-charity-donation";
import { isResidentReliefsDeductionGroup } from "./resident-reliefs-notice";
import { isQualifyingPaymentsDeductionGroup } from "./qualifying-payments-notice";
import { isNonResidentCitizenReliefGroup } from "./non-resident-citizen-notice";
import {
  emptyExpenditureBreakdown,
  EXPENDITURE_RELIEF_HEADLINE,
  EXPENDITURE_RELIEF_INTRO,
  EXPENDITURE_SUBCATEGORIES,
  isExpenditureReliefAvailableForYa,
  isExpenditureReliefGroup,
  sumExpenditureBreakdown,
  type ExpenditureSubcategoryId,
} from "./expenditure-relief";
import { isEmploymentIncomeReliefAvailableForYa, isEmploymentIncomeReliefGroup } from "./employment-relief";
import {
  INV_RENTS_COMPONENT_ID,
  isRentalIncomeReliefGroup,
  rentalIncomeReliefAmount,
} from "./rental-income-relief";
import { isSamurdhiShopQpGroup } from "./samurdhi-shop-qp";
import { isSolarPanelReliefGroup } from "./solar-panel-relief";
import {
  isCinemaConstructionQpGroup,
  isCinemaUpgradingQpGroup,
  isFilmProductionQpGroup,
} from "./film-cinema-qp";
import {
  estimateGrossIncomeLkr,
  isPersonalReliefGroup,
  personalReliefAppliedLkr,
} from "./personal-relief";
import { useReliefInterview } from "./session";
import { yaDisplay } from "./types";
import type { ReliefInterviewIncomeState } from "./types";

/** Fifth Sch 2(d) base is Sec 7 interest include — inv_interest when components mode. */
function interestIncomeLkr(income: ReliefInterviewIncomeState): number {
  if (income.investmentMode === "components") {
    return parseLkr(income.investmentAmounts.inv_interest ?? "0");
  }
  return 0;
}

function seniorCitizenReliefAmount(
  income: ReliefInterviewIncomeState,
  statutoryCap: string | null | undefined,
): number {
  const interest = interestIncomeLkr(income);
  const cap = parseLkr(String(statutoryCap ?? "0"));
  if (interest <= 0 || cap <= 0) return 0;
  return Math.min(interest, cap);
}

/** Fifth Sch 2(c) base is Sec 7 rents include — inv_rents when components mode. */
function rentIncomeLkr(income: ReliefInterviewIncomeState): number {
  if (income.investmentMode === "components") {
    return parseLkr(income.investmentAmounts[INV_RENTS_COMPONENT_ID] ?? "0");
  }
  return 0;
}

function asApprovedEntries(raw: ReliefInterviewApprovedYear): ApprovedEntry[] {
  const entries = Array.isArray(raw.entries) ? raw.entries : [];
  return sortEntries(
    entries.filter((e): e is ApprovedEntry => {
      const row = e as Partial<ApprovedEntry>;
      return Boolean(row.entry_id && row.compare_group_id && row.question_prompt);
    }) as ApprovedEntry[],
  );
}

type ReliefStep =
  | { kind: "single"; entry: ApprovedEntry }
  | { kind: "donee_block"; entries: ApprovedEntry[] };

function buildReliefSteps(
  entries: ApprovedEntry[],
  assessmentYear: string,
): ReliefStep[] {
  const visible = entries.filter((e) => {
    if (isBankMergerQpGroup(e.compare_group_id)) return false;
    if (isEntityCharityDonationGroup(e.compare_group_id)) return false;
    if (isResidentReliefsDeductionGroup(e.compare_group_id)) return false;
    if (isQualifyingPaymentsDeductionGroup(e.compare_group_id)) return false;
    if (isNonResidentCitizenReliefGroup(e.compare_group_id)) return false;
    if (
      isExpenditureReliefGroup(e.compare_group_id) &&
      !isExpenditureReliefAvailableForYa(assessmentYear)
    ) {
      return false;
    }
    if (
      isEmploymentIncomeReliefGroup(e.compare_group_id) &&
      !isEmploymentIncomeReliefAvailableForYa(assessmentYear)
    ) {
      return false;
    }
    return true;
  });
  const donees = sortListedDoneeEntries(
    visible.filter((e) => isListedPublicDoneeGroup(e.compare_group_id)),
  );
  const doneeIds = new Set(donees.map((e) => e.entry_id));
  const steps: ReliefStep[] = [];
  let inserted = false;
  for (const e of visible) {
    if (doneeIds.has(e.entry_id)) {
      if (!inserted && donees.length > 0) {
        steps.push({ kind: "donee_block", entries: donees });
        inserted = true;
      }
      continue;
    }
    steps.push({ kind: "single", entry: e });
  }
  return steps;
}

export function ReliefInterviewReliefsPage() {
  const navigate = useNavigate();
  const {
    session,
    upsertReliefAnswer,
    setSelectedCompareGroupId,
    patchIncome,
  } = useReliefInterview();
  const { assessmentYear, reliefAnswers, income } = session;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [asOfEntries, setAsOfEntries] = useState<ApprovedEntry[]>([]);
  const [step, setStep] = useState(0);
  const [amountDraft, setAmountDraft] = useState("0");
  const [affirmedDraft, setAffirmedDraft] = useState(true);
  const [rentIncomeDraft, setRentIncomeDraft] = useState("0");
  const [doneeAffirmed, setDoneeAffirmed] = useState(false);
  const [doneeAmounts, setDoneeAmounts] = useState<Record<string, string>>({});
  const [expenditureAmounts, setExpenditureAmounts] = useState(
    emptyExpenditureBreakdown,
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getReliefInterviewApproved(assessmentYear)
      .then((asOf) => {
        if (cancelled) return;
        setAsOfEntries(asApprovedEntries(asOf));
        setStep(0);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load approved catalogs.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assessmentYear]);

  const steps = useMemo(
    () => buildReliefSteps(asOfEntries, assessmentYear),
    [asOfEntries, assessmentYear],
  );
  const current = steps[step] ?? null;

  const seniorInterestLkr = interestIncomeLkr(income);
  const seniorDerivedRelief =
    current?.kind === "single" &&
    current.entry.compare_group_id === "senior_citizen_interest_relief"
      ? seniorCitizenReliefAmount(income, current.entry.cap_amount)
      : 0;

  const rentDerivedRelief = rentalIncomeReliefAmount(parseLkr(rentIncomeDraft));

  const personalGrossLkr = estimateGrossIncomeLkr(income);
  const personalCapLkr =
    current?.kind === "single" &&
    isPersonalReliefGroup(current.entry.compare_group_id)
      ? parseLkr(String(current.entry.cap_amount ?? "0"))
      : 0;
  const personalAppliedLkr =
    current?.kind === "single" &&
    isPersonalReliefGroup(current.entry.compare_group_id)
      ? personalReliefAppliedLkr(income, current.entry.cap_amount)
      : 0;

  useEffect(() => {
    if (!current || current.kind !== "single") return;
    if (!isPersonalReliefGroup(current.entry.compare_group_id)) return;
    setAmountDraft(String(personalAppliedLkr));
    setAffirmedDraft(true);
  }, [
    current?.kind === "single" ? current.entry.entry_id : null,
    personalAppliedLkr,
  ]);

  useEffect(() => {
    if (!current || current.kind !== "single") return;
    if (current.entry.compare_group_id !== "senior_citizen_interest_relief") return;
    if (!affirmedDraft) {
      setAmountDraft("0");
      return;
    }
    setAmountDraft(String(seniorDerivedRelief));
  }, [
    current?.kind === "single" ? current.entry.entry_id : null,
    affirmedDraft,
    seniorDerivedRelief,
  ]);

  useEffect(() => {
    if (!current || current.kind !== "single") return;
    if (!isRentalIncomeReliefGroup(current.entry.compare_group_id)) return;
    if (!affirmedDraft) {
      setAmountDraft("0");
      return;
    }
    setAmountDraft(String(rentDerivedRelief));
  }, [
    current?.kind === "single" ? current.entry.entry_id : null,
    affirmedDraft,
    rentDerivedRelief,
  ]);

  useEffect(() => {
    if (!current) return;
    if (current.kind === "single") {
      const existing = reliefAnswers.find((a) => a.entry_id === current.entry.entry_id);
      const isSenior =
        current.entry.compare_group_id === "senior_citizen_interest_relief";
      const isRent = isRentalIncomeReliefGroup(current.entry.compare_group_id);
      const isPersonal = isPersonalReliefGroup(current.entry.compare_group_id);
      const isExpenditure = isExpenditureReliefGroup(current.entry.compare_group_id);
      const rentsOnIncome = rentIncomeLkr(income);
      setAffirmedDraft(
        existing?.affirmed ??
          (isSenior ? false : isRent ? rentsOnIncome > 0 : true),
      );
      if (isRent) {
        setRentIncomeDraft(
          formatMoneyInput(String(income.investmentAmounts[INV_RENTS_COMPONENT_ID] ?? "0")),
        );
      }
      if (isExpenditure) {
        const base = emptyExpenditureBreakdown();
        const saved = existing?.amount_breakdown ?? {};
        for (const row of EXPENDITURE_SUBCATEGORIES) {
          base[row.id] = saved[row.id] ?? "0";
        }
        setExpenditureAmounts(base);
        setAmountDraft(String(sumExpenditureBreakdown(base)));
      } else if (!isSenior && !isRent && !isPersonal) {
        setAmountDraft(existing?.amount ?? "0");
      }
      return;
    }
    const amounts: Record<string, string> = {};
    let any = false;
    for (const e of current.entries) {
      const existing = reliefAnswers.find((a) => a.entry_id === e.entry_id);
      amounts[e.entry_id] = existing?.amount ?? "0";
      if (existing && existing.skipped !== true && existing.affirmed !== false) {
        const n = Number(String(existing.amount ?? "0").replace(/,/g, ""));
        if (Number.isFinite(n) && n > 0) any = true;
      }
    }
    setDoneeAmounts(amounts);
    setDoneeAffirmed(any);
  }, [current?.kind === "single" ? current.entry.entry_id : `block-${step}`]); // eslint-disable-line react-hooks/exhaustive-deps -- reset draft per step

  const expenditureTotal = sumExpenditureBreakdown(expenditureAmounts);
  const expenditureCap =
    current?.kind === "single" &&
    isExpenditureReliefGroup(current.entry.compare_group_id)
      ? parseLkr(String(current.entry.cap_amount ?? "0"))
      : 0;
  const expenditureAllowed =
    expenditureCap > 0
      ? Math.min(expenditureTotal, expenditureCap)
      : expenditureTotal;

  function syncRentIncomeToSession(raw: string): void {
    const formatted = formatMoneyInput(raw);
    setRentIncomeDraft(formatted);
    patchIncome((prev) => ({
      investmentMode: "components",
      investmentAmounts: {
        ...prev.investmentAmounts,
        [INV_RENTS_COMPONENT_ID]: formatted || "0",
      },
    }));
  }

  function patchExpenditure(
    id: ExpenditureSubcategoryId,
    value: string,
  ): void {
    setExpenditureAmounts((prev) => {
      const next = { ...prev, [id]: formatMoneyInput(value) };
      setAmountDraft(String(sumExpenditureBreakdown(next)));
      return next;
    });
  }

  function saveSingle(partial: Partial<ReliefAnswer>): void {
    if (!current || current.kind !== "single") return;
    const entry = current.entry;
    const isExpenditure = isExpenditureReliefGroup(entry.compare_group_id);
    const isRent = isRentalIncomeReliefGroup(entry.compare_group_id);
    const isPersonal = isPersonalReliefGroup(entry.compare_group_id);
    const isSenior = entry.compare_group_id === "senior_citizen_interest_relief";
    if (partial.skipped) {
      upsertReliefAnswer({
        entry_id: entry.entry_id,
        compare_group_id: entry.compare_group_id,
        amount: "0",
        affirmed: false,
        amount_breakdown: isExpenditure
          ? emptyExpenditureBreakdown()
          : undefined,
        skipped: true,
      });
      return;
    }
    if (isRent) {
      syncRentIncomeToSession(rentIncomeDraft);
    }
    const total = isExpenditure
      ? sumExpenditureBreakdown(expenditureAmounts)
      : isRent
        ? affirmedDraft
          ? rentalIncomeReliefAmount(parseLkr(rentIncomeDraft))
          : 0
        : isPersonal
          ? personalReliefAppliedLkr(income, entry.cap_amount)
          : isSenior
            ? affirmedDraft
              ? seniorCitizenReliefAmount(income, entry.cap_amount)
              : 0
            : parseLkr(amountDraft);
    upsertReliefAnswer({
      entry_id: entry.entry_id,
      compare_group_id: entry.compare_group_id,
      amount: String(total),
      affirmed: isExpenditure
        ? total > 0
        : isPersonal
          ? true
          : affirmedDraft,
      amount_breakdown: isExpenditure
        ? { ...expenditureAmounts }
        : undefined,
      ...partial,
    });
  }

  function saveDoneeBlock(opts: { skipped: boolean }): void {
    if (!current || current.kind !== "donee_block") return;
    for (const e of current.entries) {
      const amt = doneeAmounts[e.entry_id] ?? "0";
      const n = Number(String(amt).replace(/,/g, ""));
      const hasAmount = Number.isFinite(n) && n > 0;
      if (opts.skipped || !doneeAffirmed) {
        upsertReliefAnswer({
          entry_id: e.entry_id,
          compare_group_id: e.compare_group_id,
          amount: "0",
          affirmed: false,
          skipped: opts.skipped,
        });
      } else {
        upsertReliefAnswer({
          entry_id: e.entry_id,
          compare_group_id: e.compare_group_id,
          amount: hasAmount ? amt : "0",
          affirmed: hasAmount,
          skipped: false,
        });
      }
    }
  }

  function advanceAfterSave(): void {
    if (step + 1 >= steps.length) {
      void navigate("/adaptive-tax/relief-interview/result");
      return;
    }
    setStep((s) => s + 1);
  }

  function goNext(): void {
    if (current?.kind === "single") {
      saveSingle({ skipped: false });
      setSelectedCompareGroupId(current.entry.compare_group_id);
    } else if (current?.kind === "donee_block") {
      saveDoneeBlock({ skipped: false });
      setSelectedCompareGroupId(current.entries[0]?.compare_group_id ?? null);
    }
    advanceAfterSave();
  }

  function goBack(): void {
    if (step <= 0) {
      void navigate("/adaptive-tax/relief-interview/income");
      return;
    }
    setStep((s) => s - 1);
  }

  function skipQuestion(): void {
    if (current?.kind === "single") {
      saveSingle({ skipped: true });
      setSelectedCompareGroupId(current.entry.compare_group_id);
    } else if (current?.kind === "donee_block") {
      saveDoneeBlock({ skipped: true });
      setSelectedCompareGroupId(current.entries[0]?.compare_group_id ?? null);
    }
    advanceAfterSave();
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading approved relief catalog for YA {yaDisplay(assessmentYear)}…
      </p>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
        <Button type="button" variant="outline" onClick={() => void navigate(-1)}>
          Back
        </Button>
      </div>
    );
  }

  if (asOfEntries.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Reliefs</h2>
        <div className="sticky top-0 z-10 -mx-1 mb-1 rounded-md border bg-background/95 px-3 py-2 text-xs backdrop-blur">
          <span className="font-medium">YA {yaDisplay(assessmentYear)} only</span>
        </div>
        <p className="text-sm text-muted-foreground">
          No approved relief rows for YA {yaDisplay(assessmentYear)} yet (
          <code className="text-xs">approved/{assessmentYear}.json</code>). Year-to-year
          catalog compare is a separate Adaptive Tax page.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={goBack}>
            Back
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void navigate("/adaptive-tax/compare")}
          >
            Open compare
          </Button>
          <Button
            type="button"
            onClick={() => void navigate("/adaptive-tax/relief-interview/result")}
          >
            Continue to result
          </Button>
        </div>
      </div>
    );
  }

  const showCfHint = assessmentYear === "2025_26";
  const single = current?.kind === "single" ? current.entry : null;
  const isExpenditureStep =
    single != null && isExpenditureReliefGroup(single.compare_group_id);
  const isRentStep =
    single != null && isRentalIncomeReliefGroup(single.compare_group_id);
  const isPersonalStep =
    single != null && isPersonalReliefGroup(single.compare_group_id);
  const isSeniorStep =
    single != null &&
    single.compare_group_id === "senior_citizen_interest_relief";

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 -mx-1 rounded-md border bg-background/95 px-3 py-2 text-xs backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-medium">
              {asOfEntries.length} reliefs for YA {yaDisplay(assessmentYear)}
            </span>
            <span className="mx-1.5 text-muted-foreground">·</span>
            <span className="text-muted-foreground">
              Question {step + 1} of {steps.length}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">
              Filed year only
            </span>
            {single && isUnconfirmedTransitionalCarry(single, assessmentYear) ? (
              <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                Last known figure — not confirmed for this year
              </span>
            ) : null}
            {single?.needs_manual_verification ? (
              <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                Needs manual verification
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {single ? (
        <div className="space-y-4 rounded-md border p-4">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {single.display_name}
            </p>
            <h2 className="text-lg font-semibold leading-snug">
              {isExpenditureStep
                ? EXPENDITURE_RELIEF_HEADLINE
                : single.question_prompt}
            </h2>
            {isExpenditureStep ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>{EXPENDITURE_RELIEF_INTRO}</p>
                <p>
                  Combined cap for YA {yaDisplay(assessmentYear)}:{" "}
                  <span className="font-medium text-foreground">
                    {formatMoneyInput(String(single.cap_amount ?? "0"))} LKR
                  </span>{" "}
                  for all five types together (not per row).
                </p>
              </div>
            ) : null}
            {single.auto_applied && single.input_kind === "notice" && !isPersonalStep ? (
              <p className="text-xs text-muted-foreground">
                Auto-applied statutory relief — no claim amount required.
              </p>
            ) : null}
            {isPersonalStep ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">2(a)</span>{" "}
                  personal relief for a{" "}
                  <span className="font-medium text-foreground">
                    resident individual
                  </span>
                  . This interview assumes you are resident, so the calculator
                  applies it automatically — you do not enter a separate claim.
                </p>
                <p className="font-medium text-foreground">Statutory amount</p>
                <p>
                  For YA {yaDisplay(assessmentYear)} the Act allows up to{" "}
                  <span className="font-medium text-foreground">
                    Rs {formatMoneyInput(String(single.cap_amount ?? "0"))}
                  </span>{" "}
                  (Act No. 2 of 2025 item (v) from 1 April 2025).
                </p>
                <p className="font-medium text-foreground">
                  How much applies to you
                </p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    If your income is{" "}
                    <span className="font-medium text-foreground">
                      greater than or equal to
                    </span>{" "}
                    the statutory amount, the full{" "}
                    <span className="font-medium text-foreground">
                      Rs {formatMoneyInput(String(single.cap_amount ?? "0"))}
                    </span>{" "}
                    is applied.
                  </li>
                  <li>
                    If your income is{" "}
                    <span className="font-medium text-foreground">lower</span>,
                    only up to that income is used (you cannot get more relief
                    than income).
                  </li>
                </ul>
                {personalGrossLkr <= 0 ? (
                  <p className="text-amber-800 dark:text-amber-200">
                    No income on the Income step yet — go back and enter income,
                    or personal relief stays at 0 until there is income to set
                    against.
                  </p>
                ) : (
                  <p>
                    Income from Income step (estimate):{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(personalGrossLkr))} LKR
                    </span>
                    {" → "}
                    relief that applies:{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(personalAppliedLkr))} LKR
                    </span>
                    {personalGrossLkr >= personalCapLkr
                      ? " (full statutory amount)."
                      : " (limited to your income)."}
                  </p>
                )}
                <p>
                  Trustees, receivers, executors, or liquidators cannot take this
                  personal relief in that capacity, and it is not deducted against
                  gains from realisation of investment assets.
                </p>
              </div>
            ) : null}
            {single.auto_applied &&
            (single.input_kind === "yes_no_amount" ||
              single.input_kind === "boolean") &&
            !isRentStep &&
            !isSeniorStep ? (
              <p className="text-xs text-muted-foreground">
                If you qualify, the statutory cap applies automatically — no
                claim amount to enter.
              </p>
            ) : null}
            {isRentStep ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">2(c)</span> gives a
                  statutory relief of{" "}
                  <span className="font-medium text-foreground">
                    25% of your rental income
                  </span>{" "}
                  from an investment asset. It stands in for repair, maintenance,
                  and depreciation on that asset.
                </p>
                <p className="font-medium text-foreground">Who can claim</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    An individual with{" "}
                    <span className="font-medium text-foreground">
                      rental income from an investment asset
                    </span>{" "}
                    for the year.
                  </li>
                  <li>
                    You must{" "}
                    <span className="font-medium text-foreground">not</span> also
                    claim actual repair, maintenance, or depreciation costs on the
                    same asset — choose either this 25% relief or actual costs, not
                    both.
                  </li>
                </ul>
                <p className="font-medium text-foreground">How the amount works</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Enter (or sync) your Sec 7{" "}
                    <span className="font-medium text-foreground">Rents</span>{" "}
                    include amount — the same field as Investment on the Income
                    step.
                  </li>
                  <li>
                    Relief that applies is{" "}
                    <span className="font-medium text-foreground">
                      25% of that rental income
                    </span>{" "}
                    (rounded down to whole rupees), shown automatically when you
                    choose Yes.
                  </li>
                  <li>
                    Put final-withholding rents on the investment final-withholding
                    line on Income — do not also put them here.
                  </li>
                </ul>
                {income.investmentMode !== "components" ? (
                  <p className="text-amber-800 dark:text-amber-200">
                    Entering rent here switches Investment to Components so the
                    calculator can use the Sec 7 Rents line.
                  </p>
                ) : null}
              </div>
            ) : null}
            {single && isSolarPanelReliefGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">2(g)</span> relief
                  for a{" "}
                  <span className="font-medium text-foreground">
                    resident individual
                  </span>{" "}
                  who acquires solar panels for their premises and connects them to
                  the{" "}
                  <span className="font-medium text-foreground">national grid</span>
                  .
                </p>
                <p className="font-medium text-foreground">Who can claim</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    You must be a resident individual for the year (this interview
                    assumes residence).
                  </li>
                  <li>
                    Panels must be fixed on{" "}
                    <span className="font-medium text-foreground">your premises</span>{" "}
                    and connected to the national grid — not a commercial plant that
                    fails those conditions.
                  </li>
                </ul>
                <p className="font-medium text-foreground">What amount to enter</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Enter what you spent on the panels,{" "}
                    <span className="font-medium text-foreground">or</span> amounts
                    paid to a bank on a loan taken to buy them (whichever you are
                    claiming for the year).
                  </li>
                  <li>
                    Relief for the year is{" "}
                    <span className="font-medium text-foreground">
                      the lower of that amount and Rs{" "}
                      {formatMoneyInput(String(single.cap_amount ?? "600000"))}
                    </span>
                    .
                  </li>
                </ul>
                <p>
                  Choose Yes only if you meet the conditions above, then enter the
                  claim amount. Choose No if you did not acquire qualifying panels
                  this year.
                </p>
              </div>
            ) : null}
            {single && isSamurdhiShopQpGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  This is a qualifying payment under Fifth Schedule 1(d) (from{" "}
                  <span className="font-medium text-foreground">1 April 2021</span>
                  ). Enter only what you actually contributed to{" "}
                  <span className="font-medium text-foreground">
                    set up a shop
                  </span>{" "}
                  that meets all of the conditions below.
                </p>
                <p className="font-medium text-foreground">Who can claim</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    You must be a{" "}
                    <span className="font-medium text-foreground">
                      resident individual
                    </span>{" "}
                    for the year (not a company or other entity under this item).
                  </li>
                </ul>
                <p className="font-medium text-foreground">
                  What the contribution must be for
                </p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Establishing a{" "}
                    <span className="font-medium text-foreground">shop</span>{" "}
                    (contribution may be in{" "}
                    <span className="font-medium text-foreground">
                      money or otherwise
                    </span>
                    — e.g. goods or other support used to set up the shop).
                  </li>
                  <li>
                    The shop must be for a{" "}
                    <span className="font-medium text-foreground">
                      female individual
                    </span>{" "}
                    from a{" "}
                    <span className="font-medium text-foreground">
                      Samurdhi beneficiary family
                    </span>
                    .
                  </li>
                  <li>
                    The arrangement must be{" "}
                    <span className="font-medium text-foreground">
                      recommended and confirmed
                    </span>{" "}
                    by the{" "}
                    <span className="font-medium text-foreground">
                      Department of Samurdhi Development
                    </span>
                    . Keep that confirmation with your records.
                  </li>
                </ul>
                <p className="font-medium text-foreground">Limits</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    The Act does{" "}
                    <span className="font-medium text-foreground">
                      not set a fixed rupee or percentage cap
                    </span>{" "}
                    for this item (unlike approved charity’s Rs 75,000 rule).
                  </li>
                  <li>
                    You still cannot deduct more than your remaining taxable
                    income for the year once qualifying payments are applied.
                  </li>
                  <li>
                    Ordinary donations, temple gifts, or general Samurdhi
                    donations that are{" "}
                    <span className="font-medium text-foreground">
                      not
                    </span>{" "}
                    for establishing such a shop (with Department confirmation)
                    do not qualify here.
                  </li>
                </ul>
              </div>
            ) : null}
            {single && isFilmProductionQpGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">1(f)(i)</span>{" "}
                  (from{" "}
                  <span className="font-medium text-foreground">1 April 2021</span>
                  ): expenditure on producing a film, including promotional spend.
                </p>
                <p className="font-medium text-foreground">What counts as a film</p>
                <p>
                  An audio-visual moving-image presentation, in any form or format,
                  intended primarily to be shown by projection on a screen in a{" "}
                  <span className="font-medium text-foreground">cinema</span>.
                </p>
                <p className="font-medium text-foreground">Who can claim</p>
                <p>
                  <span className="font-medium text-foreground">Any person</span>{" "}
                  (individual or entity) who incurred the qualifying film-production
                  expenditure on or after 1 April 2021.
                </p>
                <p className="font-medium text-foreground">
                  Project-cost gate (not a maximum claim)
                </p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Total production cost (including promotion) must be{" "}
                    <span className="font-medium text-foreground">
                      at least Rs{" "}
                      {formatMoneyInput(String(single.cap_amount ?? "5000000"))}
                    </span>
                    . Below that, this qualifying payment does not apply.
                  </li>
                  <li>
                    Enter the expenditure you are claiming for the year — Rs{" "}
                    {formatMoneyInput(String(single.cap_amount ?? "5000000"))} is{" "}
                    <span className="font-medium text-foreground">
                      not
                    </span>{" "}
                    a ceiling on how much you may claim.
                  </li>
                </ul>
                <p className="font-medium text-foreground">How much can be deducted</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Deduction for film/cinema items under 1(f) is limited to{" "}
                    <span className="font-medium text-foreground">
                      one-third of taxable income
                    </span>{" "}
                    for the year (shared pool with other 1(f) cinema claims).
                  </li>
                  <li>
                    Any amount not deducted this year may be{" "}
                    <span className="font-medium text-foreground">
                      carried forward
                    </span>{" "}
                    to later years, still subject to the same one-third limit each
                    year.
                  </li>
                </ul>
              </div>
            ) : null}
            {single && isCinemaConstructionQpGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">1(f)(ii)</span>{" "}
                  (from{" "}
                  <span className="font-medium text-foreground">1 April 2021</span>
                  ): expenditure on{" "}
                  <span className="font-medium text-foreground">
                    constructing and equipping a new cinema
                  </span>
                  .
                </p>
                <p className="font-medium text-foreground">Cost ceiling</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Project cost must{" "}
                    <span className="font-medium text-foreground">
                      not exceed Rs{" "}
                      {formatMoneyInput(String(single.cap_amount ?? "25000000"))}
                    </span>
                    . Enter the amount you are claiming (up to that ceiling).
                  </li>
                </ul>
                <p className="font-medium text-foreground">Certification</p>
                <p>
                  The National Film Corporation must certify the cinema as equipped
                  with digital technology, Digital Theatre Systems, and Dolby Sound
                  Systems.
                </p>
                <p className="font-medium text-foreground">How much can be deducted</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Deduction for all 1(f) film/cinema items is limited to{" "}
                    <span className="font-medium text-foreground">
                      one-third of taxable income
                    </span>{" "}
                    (shared pool with film production and cinema upgrading).
                  </li>
                  <li>
                    Unused amounts may be{" "}
                    <span className="font-medium text-foreground">
                      carried forward
                    </span>
                    , still subject to the same one-third limit each year.
                  </li>
                </ul>
              </div>
            ) : null}
            {single && isCinemaUpgradingQpGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  Fifth Schedule{" "}
                  <span className="font-medium text-foreground">1(f)(iii)</span>{" "}
                  (from{" "}
                  <span className="font-medium text-foreground">1 April 2021</span>
                  ): expenditure on{" "}
                  <span className="font-medium text-foreground">
                    upgrading a cinema
                  </span>
                  .
                </p>
                <p className="font-medium text-foreground">Cost ceiling</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Project cost must{" "}
                    <span className="font-medium text-foreground">
                      not exceed Rs{" "}
                      {formatMoneyInput(String(single.cap_amount ?? "10000000"))}
                    </span>
                    . Enter the amount you are claiming (up to that ceiling).
                  </li>
                </ul>
                <p className="font-medium text-foreground">Certification</p>
                <p>
                  The National Film Corporation must certify the cinema as equipped
                  with digital technology, Digital Theatre Systems, and Dolby Sound
                  Systems.
                </p>
                <p className="font-medium text-foreground">How much can be deducted</p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    Deduction for all 1(f) film/cinema items is limited to{" "}
                    <span className="font-medium text-foreground">
                      one-third of taxable income
                    </span>{" "}
                    (shared pool with film production and new cinema construction).
                  </li>
                  <li>
                    Unused amounts may be{" "}
                    <span className="font-medium text-foreground">
                      carried forward
                    </span>
                    , still subject to the same one-third limit each year.
                  </li>
                </ul>
              </div>
            ) : null}
            {single.compare_group_id === "foreign_currency_income_relief" ? (
              <p className="text-xs text-muted-foreground">
                Enter the qualifying foreign-currency service income for this year.
                Relief under Fifth Schedule 2(e) is{" "}
                <span className="font-medium text-foreground">
                  min(Rs {formatMoneyInput(String(single.cap_amount ?? "0"))}, that
                  income)
                </span>
                — not the full cap unless you earned that much.
              </p>
            ) : null}
            {isApprovedCharityDonationGroup(single.compare_group_id) ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>
                  This is only for{" "}
                  <span className="font-medium text-foreground">
                    donations in money
                  </span>{" "}
                  (not goods or free services) to a charity that:
                </p>
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    provides{" "}
                    <span className="font-medium text-foreground">
                      institutionalized care for the sick or the needy
                    </span>{" "}
                    (for example an elders’ home, children’s home, or similar care
                    institution); and
                  </li>
                  <li>
                    the{" "}
                    <span className="font-medium text-foreground">
                      Minister has declared
                    </span>{" "}
                    as an “approved charitable institution” for Fifth Schedule
                    1(a) (published in the Gazette).
                  </li>
                </ul>
                <p>
                  Ordinary temples, schools, or NGOs do{" "}
                  <span className="font-medium text-foreground">not</span> count
                  unless they appear on that approved list. Donations to the
                  Government, local authorities, universities, or named public
                  funds are different — those appear as separate questions later.
                </p>
                <p>
                  Your claim for an individual is limited to{" "}
                  <span className="font-medium text-foreground">
                    the lower of Rs{" "}
                    {formatMoneyInput(String(single.cap_amount ?? "0"))} or
                    one-third of your taxable income
                  </span>{" "}
                  for the year.
                </p>
                <p>
                  Check the current official list on the Inland Revenue website:{" "}
                  <a
                    href={IRD_APPROVED_CHARITY_LIST_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-foreground underline underline-offset-2"
                  >
                    IRD — Approved Charity
                  </a>
                  .
                </p>
              </div>
            ) : null}
            {single.compare_group_id === "senior_citizen_interest_relief" ? (
              <div className="space-y-1 text-xs text-muted-foreground">
                <p>
                  Under the Inland Revenue Act, No. 24 of 2017 (Interpretation), a{" "}
                  <span className="font-medium text-foreground">senior citizen</span>{" "}
                  for a year of assessment is an individual who is (a) a citizen of
                  Sri Lanka during that year, (b) resident in Sri Lanka for that
                  year, and (c) sixty years old or above at any time during that
                  year.
                </p>
                <p>
                  Fifth Schedule paragraph 2(d) limit:{" "}
                  <span className="font-medium text-foreground">
                    min(Rs {formatMoneyInput(String(single.cap_amount ?? "0"))}, your
                    interest income for the year)
                  </span>
                  .
                </p>
                {income.investmentMode !== "components" ? (
                  <p className="text-amber-800 dark:text-amber-200">
                    Enter Interest under Investment → Components (not a single
                    total) so this relief can read Sec 7 interest.
                  </p>
                ) : seniorInterestLkr <= 0 ? (
                  <p className="text-amber-800 dark:text-amber-200">
                    No Interest amount on the Income step yet — go back and enter
                    Interest, or this relief stays at 0.
                  </p>
                ) : (
                  <p>
                    Interest on Income step:{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(seniorInterestLkr))} LKR
                    </span>
                    {affirmedDraft ? (
                      <>
                        {" "}
                        → relief that applies:{" "}
                        <span className="font-medium text-foreground">
                          {formatMoneyInput(String(seniorDerivedRelief))} LKR
                        </span>
                      </>
                    ) : null}
                  </p>
                )}
                <p className="text-muted-foreground">
                  Affirm Yes only if you meet the senior-citizen definition above.
                  The calculator deducts{" "}
                  <span className="font-medium text-foreground">
                    min(Rs {formatMoneyInput(String(single.cap_amount ?? "0"))},
                    Interest)
                  </span>{" "}
                  under Fifth Schedule 2(d).
                </p>
              </div>
            ) : null}
            {single.cap_amount &&
            single.compare_group_id !== "senior_citizen_interest_relief" &&
            !isExpenditureStep &&
            !isRentStep &&
            !isFilmProductionQpGroup(single.compare_group_id) &&
            !isCinemaConstructionQpGroup(single.compare_group_id) &&
            !isCinemaUpgradingQpGroup(single.compare_group_id) &&
            !isPersonalStep &&
            single.unit !== "percent" ? (
              <p className="text-xs text-muted-foreground">
                Cap for YA {yaDisplay(assessmentYear)}:{" "}
                {formatMoneyInput(String(single.cap_amount))} LKR
              </p>
            ) : null}
            {single && isFilmProductionQpGroup(single.compare_group_id) ? (
              <p className="text-xs text-muted-foreground">
                Minimum film cost (including promotion) for YA{" "}
                {yaDisplay(assessmentYear)}:{" "}
                <span className="font-medium text-foreground">
                  Rs {formatMoneyInput(String(single.cap_amount ?? "5000000"))}
                </span>{" "}
                — not a maximum claim.
              </p>
            ) : null}
            {single && isCinemaConstructionQpGroup(single.compare_group_id) ? (
              <p className="text-xs text-muted-foreground">
                Maximum new-cinema cost for YA {yaDisplay(assessmentYear)}:{" "}
                <span className="font-medium text-foreground">
                  Rs {formatMoneyInput(String(single.cap_amount ?? "25000000"))}
                </span>
                .
              </p>
            ) : null}
            {single && isCinemaUpgradingQpGroup(single.compare_group_id) ? (
              <p className="text-xs text-muted-foreground">
                Maximum cinema-upgrading cost for YA {yaDisplay(assessmentYear)}:{" "}
                <span className="font-medium text-foreground">
                  Rs {formatMoneyInput(String(single.cap_amount ?? "10000000"))}
                </span>
                .
              </p>
            ) : null}
            {isPersonalStep ? (
              <p className="text-xs text-muted-foreground">
                Statutory personal relief for YA {yaDisplay(assessmentYear)}:{" "}
                <span className="font-medium text-foreground">
                  Rs {formatMoneyInput(String(single.cap_amount ?? "0"))}
                </span>
                . Applied in calculate for residents as{" "}
                <span className="font-medium text-foreground">
                  Rs {formatMoneyInput(String(personalAppliedLkr))}
                </span>
                .
              </p>
            ) : null}
          </div>

          {single.input_kind === "notice" ? (
            isPersonalStep ? (
              <div className="max-w-xs space-y-2">
                <Label htmlFor="ri-personal-relief-amount">
                  Relief that applies (LKR)
                </Label>
                <Input
                  id="ri-personal-relief-amount"
                  inputMode="numeric"
                  readOnly
                  value={formatMoneyInput(String(personalAppliedLkr))}
                  className="bg-muted/40"
                />
                <p className="text-xs text-muted-foreground">
                  Auto-filled as{" "}
                  <span className="font-medium text-foreground">
                    min(Rs {formatMoneyInput(String(single.cap_amount ?? "0"))},
                    income {formatMoneyInput(String(personalGrossLkr))})
                  </span>
                  . Change income on the Income step to update this.
                </p>
              </div>
            ) : null
          ) : isExpenditureStep ? (
            <div className="space-y-3">
              {EXPENDITURE_SUBCATEGORIES.map((row) => (
                <div
                  key={row.id}
                  className="space-y-2 rounded-md border border-dashed p-3"
                >
                  <Label htmlFor={`ri-exp-${row.id}`}>
                    <span className="font-medium text-foreground">
                      {row.roman} {row.short_label}
                    </span>
                  </Label>
                  <p className="text-[11px] text-muted-foreground">{row.help}</p>
                  <Input
                    id={`ri-exp-${row.id}`}
                    inputMode="numeric"
                    value={formatMoneyInput(expenditureAmounts[row.id])}
                    onChange={(e) => patchExpenditure(row.id, e.target.value)}
                    placeholder="0"
                  />
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Subtotal:{" "}
                <span className="font-medium text-foreground">
                  {formatMoneyInput(String(expenditureTotal))} LKR
                </span>
                {expenditureCap > 0 ? (
                  <>
                    {" "}
                    → after cap:{" "}
                    <span className="font-medium text-foreground">
                      {formatMoneyInput(String(expenditureAllowed))} LKR
                    </span>
                  </>
                ) : null}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {(single.input_kind === "yes_no_amount" ||
                single.input_kind === "boolean") && (
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
              )}
              {isRentStep ? (
                <div className="max-w-xs space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="ri-rent-income">
                      Rental income — Sec 7 Rents (LKR)
                    </Label>
                    <Input
                      id="ri-rent-income"
                      inputMode="numeric"
                      value={formatMoneyInput(rentIncomeDraft)}
                      onChange={(e) => syncRentIncomeToSession(e.target.value)}
                      placeholder="0"
                    />
                  </div>
                  {affirmedDraft ? (
                    <div className="space-y-2">
                      <Label htmlFor="ri-rent-relief-amount">
                        Relief that applies (LKR)
                      </Label>
                      <Input
                        id="ri-rent-relief-amount"
                        inputMode="numeric"
                        readOnly
                        value={formatMoneyInput(String(rentDerivedRelief))}
                        className="bg-muted/40"
                      />
                      <p className="text-xs text-muted-foreground">
                        Auto-filled as{" "}
                        <span className="font-medium text-foreground">
                          25% of rental income (
                          {formatMoneyInput(rentIncomeDraft || "0")})
                        </span>
                        . Synced with Income → Investment → Rents.
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Choose Yes to claim the 25% statutory relief (rental income
                      itself still stays on the Income step).
                    </p>
                  )}
                </div>
              ) : null}
              {isSeniorStep && affirmedDraft ? (
                <div className="max-w-xs space-y-2">
                  <Label htmlFor="ri-senior-relief-amount">
                    Relief that applies (LKR)
                  </Label>
                  <Input
                    id="ri-senior-relief-amount"
                    inputMode="numeric"
                    readOnly
                    value={formatMoneyInput(String(seniorDerivedRelief))}
                    className="bg-muted/40"
                  />
                  <p className="text-xs text-muted-foreground">
                    Auto-filled as{" "}
                    <span className="font-medium text-foreground">
                      min(Rs {formatMoneyInput(String(single.cap_amount ?? "0"))},
                      Interest {formatMoneyInput(String(seniorInterestLkr))})
                    </span>
                    . Change Interest on the Income step to update this.
                  </p>
                </div>
              ) : null}
              {(single.input_kind === "yes_no_amount" ||
                single.input_kind === "amount") &&
              affirmedDraft &&
              !single.auto_applied &&
              !isRentStep &&
              !isSeniorStep ? (
                <div className="max-w-xs space-y-2">
                  <Label htmlFor="ri-relief-amount">
                    {isApprovedCharityDonationGroup(single.compare_group_id)
                      ? "Total money donated to approved charities (LKR)"
                      : "Amount (LKR)"}
                  </Label>
                  <Input
                    id="ri-relief-amount"
                    inputMode="numeric"
                    value={formatMoneyInput(amountDraft)}
                    onChange={(e) => setAmountDraft(formatMoneyInput(e.target.value))}
                    placeholder="0"
                  />
                </div>
              ) : null}
            </div>
          )}

          <div className="rounded-md border bg-muted/30 p-3 text-[11px] text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">Provenance (this YA)</p>
            <p>
              {single.act_name} · {single.section_ref} · {single.source_doc_id}
            </p>
            {single.quote ? <p className="italic">“{single.quote}”</p> : null}
          </div>
        </div>
      ) : null}

      {current?.kind === "donee_block" ? (
        <div className="space-y-4 rounded-md border p-4">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              ¶1(b) listed public donees
            </p>
            <h2 className="text-lg font-semibold leading-snug">
              {LISTED_DONEES_BLOCK_PROMPT}
            </h2>
            <div className="space-y-2 text-xs text-muted-foreground">
              <p>{LISTED_DONEES_HELP.intro}</p>
              <p>{LISTED_DONEES_HELP.who}</p>
              <p>{LISTED_DONEES_HELP.form}</p>
              <p className="font-medium text-foreground">
                {LISTED_DONEES_HELP.limitsTitle}
              </p>
              <ul className="list-disc space-y-1 pl-4">
                {LISTED_DONEES_HELP.limits.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {showCfHint ? (
                <>
                  <p className="font-medium text-foreground">
                    {LISTED_DONEES_HELP.cfTitle}
                  </p>
                  <p>{LISTED_DONEES_HELP.cfBody}</p>
                </>
              ) : null}
              <p>{LISTED_DONEES_HELP.engineNote}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={doneeAffirmed ? "default" : "outline"}
              onClick={() => setDoneeAffirmed(true)}
            >
              Yes
            </Button>
            <Button
              type="button"
              size="sm"
              variant={!doneeAffirmed ? "default" : "outline"}
              onClick={() => setDoneeAffirmed(false)}
            >
              No
            </Button>
          </div>

          {doneeAffirmed ? (
            <ul className="space-y-3">
              {current.entries.map((e) => {
                const meta = listedDoneeMeta(e.compare_group_id);
                const cf =
                  showCfHint && meta?.sec52_4_eligible
                    ? "If unused this year, Sec 52(4) may allow carry-forward for this donee from YA 2025/26."
                    : null;
                return (
                  <li
                    key={e.entry_id}
                    className="space-y-2 rounded-md border border-dashed p-3"
                  >
                    <div className="space-y-0.5">
                      <p className="text-sm font-medium">
                        {meta ? (
                          <>
                            <span className="text-muted-foreground">{meta.roman}</span>{" "}
                            {meta.short_label}
                          </>
                        ) : (
                          e.display_name
                        )}
                      </p>
                      {cf ? (
                        <p className="text-[11px] text-amber-800 dark:text-amber-200">
                          {cf}
                        </p>
                      ) : null}
                      {e.quote ? (
                        <p className="text-[11px] italic text-muted-foreground">
                          “{e.quote}”
                        </p>
                      ) : null}
                    </div>
                    <div className="max-w-xs space-y-1">
                      <Label htmlFor={`ri-donee-${e.entry_id}`}>Amount (LKR)</Label>
                      <Input
                        id={`ri-donee-${e.entry_id}`}
                        inputMode="numeric"
                        value={formatMoneyInput(doneeAmounts[e.entry_id] ?? "0")}
                        onChange={(ev) =>
                          setDoneeAmounts((prev) => ({
                            ...prev,
                            [e.entry_id]: formatMoneyInput(ev.target.value),
                          }))
                        }
                        placeholder="0"
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={goBack}>
          Back
        </Button>
        <Button type="button" variant="ghost" onClick={skipQuestion}>
          Skip
        </Button>
        <Button type="button" onClick={goNext}>
          {step + 1 >= steps.length ? "Continue to result" : "Next"}
        </Button>
      </div>
    </div>
  );
}
