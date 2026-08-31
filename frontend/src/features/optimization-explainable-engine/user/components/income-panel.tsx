import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { formatLkr, parseLkr, yaDisplay } from "../../format-lkr";
import {
  businessIncomeLkr,
  employmentIncomeLkr,
  interestScheduleTotals,
  investmentIncomeLkr,
  otherIncomeLkr,
  totalIncomeLkr,
  apitAlreadyPaidLkr,
  whtAlreadyPaidLkr,
} from "../../income-aggregate";
import { incomeCatalogCard } from "../../income-catalog";
import type { InterviewIncomeState } from "../../types";
import { profileToInterviewIncome } from "@/lib/profile-bridge/tax-return-to-oe-income";
import { OeNavChips } from "./oe-nav-chips";
import { UvPanelShell, YaSelector } from "./uv-chrome";
import { useTaxpayerOe } from "../taxpayer-oe-context";
import { TAXWISE_OE_RELIEFS } from "../paths";

type BreakdownLine = { label: string; value: number; muted?: boolean };

function positiveLines(lines: BreakdownLine[]): BreakdownLine[] {
  return lines.filter((l) => l.value > 0);
}

function employmentBreakdown(income: InterviewIncomeState): BreakdownLine[] {
  if (income.employmentMode === "total") {
    const gross = parseLkr(income.form.employment_income);
    const fwh = parseLkr(income.form.employment_final_withholding);
    return positiveLines([
      { label: "Employment total", value: gross },
      { label: "Less: final WHT / exempt", value: fwh, muted: true },
    ]);
  }
  const card = incomeCatalogCard("employment");
  const lines: BreakdownLine[] = [];
  for (const field of card?.fields ?? []) {
    const value = parseLkr(income.employmentAmounts[field.component_id] ?? "0");
    if (value <= 0) continue;
    const muted = field.default_treatment !== "include";
    lines.push({
      label: muted ? `Less: ${field.display_name}` : field.display_name,
      value,
      muted,
    });
  }
  return lines;
}

function businessBreakdown(income: InterviewIncomeState): BreakdownLine[] {
  if (income.businessMode === "breakdown") {
    const gross = parseLkr(income.businessAmounts.biz_gross ?? income.form.business_gross);
    const deductions = parseLkr(
      income.businessAmounts.biz_deductions ?? income.form.business_deductions,
    );
    const ca = parseLkr(
      income.businessAmounts.biz_capital_allowances ?? income.form.capital_allowances,
    );
    return positiveLines([
      { label: "Gross business receipts", value: gross },
      { label: "Less: allowable expenses", value: deductions, muted: true },
      { label: "Less: capital allowances", value: ca, muted: true },
    ]);
  }
  const net =
    parseLkr(income.businessAmounts.biz_net_profits ?? "0") ||
    parseLkr(income.form.business_income);
  return positiveLines([{ label: "Net assessable business profits", value: net }]);
}

function investmentBreakdown(income: InterviewIncomeState): BreakdownLine[] {
  if (income.investmentMode === "total") {
    const gross = parseLkr(income.form.investment_income);
    const fwh = parseLkr(income.form.investment_final_withholding);
    return positiveLines([
      { label: "Investment total", value: gross },
      { label: "Less: final WHT / exempt", value: fwh, muted: true },
    ]);
  }

  const lines: BreakdownLine[] = [];
  const schedule = income.interestSchedule ?? [];
  if (schedule.length > 0) {
    for (const row of schedule) {
      const interest = parseLkr(row.interest);
      if (interest <= 0) continue;
      lines.push({
        label: row.label?.trim() ? `Interest — ${row.label}` : "Interest",
        value: interest,
      });
    }
  } else {
    const interest = parseLkr(income.investmentAmounts.inv_interest ?? "0");
    if (interest > 0) lines.push({ label: "Interest", value: interest });
  }

  const card = incomeCatalogCard("investment");
  for (const field of card?.fields ?? []) {
    if (field.component_id === "inv_interest") continue;
    const value = parseLkr(income.investmentAmounts[field.component_id] ?? "0");
    if (value <= 0) continue;
    const muted = field.default_treatment !== "include";
    lines.push({
      label: muted ? `Less: ${field.display_name}` : field.display_name,
      value,
      muted,
    });
  }
  return lines;
}

function otherBreakdown(income: InterviewIncomeState): BreakdownLine[] {
  if (income.otherMode === "total") {
    const gross = parseLkr(income.form.other_income);
    const fwh = parseLkr(income.form.other_final_withholding);
    return positiveLines([
      { label: "Other income total", value: gross },
      { label: "Less: final WHT / exempt", value: fwh, muted: true },
    ]);
  }
  const lines: BreakdownLine[] = [];
  const residual = parseLkr(income.otherAmounts.oth_residual ?? "0");
  if (residual > 0) lines.push({ label: "Other residual income", value: residual });
  for (const row of income.otherCustomRows ?? []) {
    const value = parseLkr(row.amount);
    if (value <= 0) continue;
    lines.push({ label: row.label?.trim() || "Other", value });
  }
  const fwh = parseLkr(income.otherAmounts.oth_final_withholding ?? "0");
  if (fwh > 0) lines.push({ label: "Less: final WHT / exempt", value: fwh, muted: true });
  return lines;
}

function LineRow({ label, value, muted }: BreakdownLine) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className={muted ? "text-[var(--uv-text-muted)]" : "text-[var(--uv-text)]"}>
        {label}
      </span>
      <span
        className={`shrink-0 tabular-nums font-medium ${
          muted ? "text-[var(--uv-text-muted)]" : "text-[var(--uv-text)]"
        }`}
      >
        {muted ? `− ${formatLkr(value)}` : formatLkr(value)}
      </span>
    </div>
  );
}

function HeadSection({
  title,
  total,
  lines,
  footnote,
}: {
  title: string;
  total: number;
  lines: BreakdownLine[];
  footnote?: string;
}) {
  if (total <= 0 && lines.length === 0) return null;

  return (
    <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
      <div className="flex items-baseline justify-between gap-3 border-b border-[var(--uv-border)] pb-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-sm font-semibold tabular-nums text-[var(--uv-accent)]">
          {formatLkr(total)}
        </p>
      </div>
      {lines.length > 0 ? (
        <div className="mt-1 divide-y divide-[var(--uv-border)]/60">
          {lines.map((line) => (
            <LineRow key={`${line.label}-${line.value}`} {...line} />
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-[var(--uv-text-muted)]">No component detail available.</p>
      )}
      {footnote ? (
        <p className="mt-2 text-[11px] leading-relaxed text-[var(--uv-text-muted)]">{footnote}</p>
      ) : null}
    </section>
  );
}

export function IncomePanel() {
  const {
    scenario,
    isLoading,
    isError,
    selectYear,
    assessmentYear,
    patchIncomeSession,
    reload,
  } = useTaxpayerOe();

  if (isError) {
    return (
      <p className="text-sm text-red-400" role="alert">
        Could not load income. Confirm Comp 3 (:8003) and OE Engine (:8009) are running, then
        refresh.
      </p>
    );
  }

  if (isLoading || !scenario) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading income…
      </p>
    );
  }

  const ya = assessmentYear ?? scenario.assessmentYear;
  const income = scenario.session.income;
  const employment = employmentIncomeLkr(income);
  const business = businessIncomeLkr(income);
  const investment = investmentIncomeLkr(income);
  const other = otherIncomeLkr(income);
  const total = totalIncomeLkr(income);
  const apit = apitAlreadyPaidLkr(income);
  const wht = whtAlreadyPaidLkr(income);
  const schedule = interestScheduleTotals(income);

  const empLines = employmentBreakdown(income);
  const bizLines = businessBreakdown(income);
  const invLines = investmentBreakdown(income);
  const othLines = otherBreakdown(income);

  function reloadFromProfile() {
    const mapped = profileToInterviewIncome(scenario.profile);
    patchIncomeSession({
      ...scenario.session,
      assessmentYear: ya,
      income: {
        ...mapped.income,
        taxpayerName: mapped.income.taxpayerName || scenario.fullName,
        tin: mapped.income.tin || scenario.tin,
      },
    });
  }

  const buildParts = [
    employment > 0 ? `Employment ${formatLkr(employment)}` : null,
    business > 0 ? `Business ${formatLkr(business)}` : null,
    investment > 0 ? `Investment ${formatLkr(investment)}` : null,
    other > 0 ? `Other ${formatLkr(other)}` : null,
  ].filter(Boolean);

  return (
    <UvPanelShell
      header={
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <OeNavChips />
            <h2 className="mt-3 text-lg font-semibold">My Income</h2>
            <p className="text-sm text-[var(--uv-text-muted)]">
              Loaded from your Tax Return Profile for YA {yaDisplay(ya)}.
              {scenario.finalized ? " Seeded from auditor-approved snapshot." : ""}
            </p>
          </div>
          <YaSelector value={ya} years={scenario.availableYears} onChange={selectYear} />
        </div>
      }
    >
      <div className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
        <p className="text-xs text-[var(--uv-text-muted)]">Name · TIN</p>
        <p className="mt-1 text-sm font-medium">
          {income.taxpayerName || scenario.fullName || "—"} ·{" "}
          {income.tin || scenario.tin || "—"}
        </p>
      </div>

      <div className="space-y-3">
        <HeadSection
          title="Employment income"
          total={employment}
          lines={empLines}
          footnote={
            apit > 0
              ? `APIT prepaid credit ${formatLkr(apit)} — credited against tax payable, not subtracted from employment income.`
              : undefined
          }
        />
        <HeadSection title="Business income" total={business} lines={bizLines} />
        <HeadSection
          title="Investment income"
          total={investment}
          lines={invLines}
          footnote={
            wht > 0 || schedule.wht > 0
              ? `WHT already paid on interest ${formatLkr(wht || schedule.wht)} — tax credit on Result, not a cut from assessable income.`
              : undefined
          }
        />
        <HeadSection title="Other income" total={other} lines={othLines} />
      </div>

      <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4">
        <h3 className="text-sm font-semibold">How total assessable is built</h3>
        <p className="mt-1 text-xs text-[var(--uv-text-muted)]">
          Assessable income = employment + business + investment + other (only heads with
          amounts). APIT and interest WHT are credits later — they do not reduce this total.
        </p>
        <div className="mt-3 space-y-1.5">
          {employment > 0 ? (
            <LineRow label="Employment" value={employment} />
          ) : null}
          {business > 0 ? <LineRow label="Business" value={business} /> : null}
          {investment > 0 ? <LineRow label="Investment" value={investment} /> : null}
          {other > 0 ? <LineRow label="Other" value={other} /> : null}
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[var(--uv-border)] pt-3">
          <span className="text-sm font-semibold">Total assessable</span>
          <span className="text-base font-semibold tabular-nums text-[var(--uv-accent)]">
            {formatLkr(total)}
          </span>
        </div>
        {buildParts.length > 0 ? (
          <p className="mt-2 text-[11px] leading-relaxed text-[var(--uv-text-muted)]">
            {buildParts.join(" + ")} = {formatLkr(total)}
          </p>
        ) : null}
      </section>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={reloadFromProfile}
          className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium hover:bg-white/5"
        >
          Reload from Tax Return Profile
        </button>
        <button
          type="button"
          onClick={() => void reload()}
          className="rounded-lg border border-[var(--uv-border)] px-4 py-2 text-sm font-medium hover:bg-white/5"
        >
          Reset scenario
        </button>
        <Link
          to={TAXWISE_OE_RELIEFS}
          className="rounded-lg bg-[var(--uv-accent)] px-4 py-2 text-sm font-medium text-[var(--uv-accent-foreground)]"
        >
          Continue to reliefs
        </Link>
      </div>
    </UvPanelShell>
  );
}
