import { ArrowDown, Equal, Minus, Plus } from "lucide-react";

import type { CalculateResponse } from "../../api";
import { formatLkr } from "../../format-lkr";
import { cn } from "@/lib/utils";
import { ordinaryTaxFromSlabs } from "../../tax-buildup";

function FlowRow({
  label,
  hint,
  value,
  tone = "default",
  operator,
}: {
  label: string;
  hint: string;
  value: string;
  tone?: "default" | "reduce" | "mid" | "hero" | "aside";
  operator?: "minus" | "equals" | "plus";
}) {
  return (
    <div className="flex gap-3">
      <div className="flex w-7 shrink-0 flex-col items-center pt-1">
        {operator === "minus" ? (
          <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[var(--uv-border)] bg-black/30 text-[var(--uv-text-muted)]">
            <Minus className="h-3.5 w-3.5" aria-hidden />
          </span>
        ) : null}
        {operator === "plus" ? (
          <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[var(--uv-border)] bg-black/30 text-[var(--uv-text-muted)]">
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </span>
        ) : null}
        {operator === "equals" ? (
          <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[var(--uv-accent)]/40 bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]">
            <Equal className="h-3.5 w-3.5" aria-hidden />
          </span>
        ) : null}
        {!operator ? (
          <span className="mt-1 h-2 w-2 rounded-full bg-[var(--uv-text-muted)]/50" />
        ) : null}
      </div>
      <div
        className={cn(
          "min-w-0 flex-1 rounded-xl border px-3 py-3",
          tone === "default" && "border-[var(--uv-border)] bg-black/10",
          tone === "reduce" && "border-[var(--uv-border)] bg-black/20",
          tone === "aside" && "border-amber-500/30 bg-amber-500/10",
          tone === "mid" && "border-[var(--uv-accent)]/30 bg-[var(--uv-accent)]/10",
          tone === "hero" &&
            "border-[var(--uv-accent)]/50 bg-[var(--uv-accent)]/15 ring-1 ring-[var(--uv-accent)]/30",
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--uv-text)]">{label}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--uv-text-muted)]">{hint}</p>
          </div>
          <p
            className={cn(
              "shrink-0 text-base font-semibold tabular-nums tracking-tight sm:text-lg",
              tone === "hero" || tone === "mid"
                ? "text-[var(--uv-accent)]"
                : tone === "aside"
                  ? "text-amber-200"
                  : "text-[var(--uv-text)]",
            )}
          >
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}

function StageTitle({ step, title, subtitle }: { step: number; title: string; subtitle: string }) {
  return (
    <div className="mb-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--uv-text-muted)]">
        Step {step}
      </p>
      <h3 className="text-sm font-semibold text-[var(--uv-text)]">{title}</h3>
      <p className="mt-0.5 text-xs text-[var(--uv-text-muted)]">{subtitle}</p>
    </div>
  );
}

/**
 * Vertical story matching the engine:
 * reliefs apply only to ordinary income; qualifying terminal benefits are taxed separately.
 */
export function ResultFlowBoard({ result }: { result: CalculateResponse }) {
  const wht = result.wht_credit ?? 0;
  const apit = result.apit_credit ?? 0;
  const credits = wht + apit;
  const refund = result.tax_refund ?? 0;
  const balance = result.balance_payable ?? result.tax_payable;
  const hasCredits = credits > 0;
  const terminalAmount = result.terminal_benefit_amount ?? 0;
  const terminalTax = result.terminal_benefit_tax ?? 0;
  const hasTerminal = terminalAmount > 0;
  // Engine: total_reliefs = ordinary_gross − taxable; gross = ordinary + terminal.
  const ordinaryIncome = Math.max(0, result.gross_income - terminalAmount);
  const ordinaryTax = ordinaryTaxFromSlabs(result.slab_lines);

  return (
    <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4 sm:p-5">
      <div className="mb-4 border-b border-[var(--uv-border)] pb-3">
        <h3 className="text-sm font-semibold text-[var(--uv-text)]">How your tax is figured</h3>
        <p className="mt-1 text-xs leading-relaxed text-[var(--uv-text-muted)]">
          Read top to bottom. Reliefs only reduce ordinary income — not terminal benefits — so a
          pocket calculator of “gross − reliefs” will not match taxable income when terminal
          benefits are included.
        </p>
      </div>

      <div className="space-y-5">
        <div>
          <StageTitle
            step={1}
            title="From earnings to taxable income"
            subtitle={
              hasTerminal
                ? "Set terminal benefits aside first; then apply reliefs to the rest."
                : "Start with ordinary earnings, then take off allowed reliefs."
            }
          />
          <div className="space-y-2">
            <FlowRow
              label="Total income reported"
              hint="Ordinary earnings plus any qualifying terminal benefits in this scenario."
              value={formatLkr(result.gross_income)}
            />
            {hasTerminal ? (
              <>
                <FlowRow
                  operator="minus"
                  label="Terminal benefits (set aside)"
                  hint="Taxed on a separate ladder later — reliefs do not reduce this amount."
                  value={formatLkr(terminalAmount)}
                  tone="aside"
                />
                <FlowRow
                  operator="equals"
                  label="Ordinary income"
                  hint="Employment, business, investment, and other income that reliefs can reduce."
                  value={formatLkr(ordinaryIncome)}
                />
                <FlowRow
                  operator="minus"
                  label="Reliefs"
                  hint="Approved reductions (personal relief, solar, donations, and so on)."
                  value={formatLkr(result.total_reliefs)}
                  tone="reduce"
                />
                <FlowRow
                  operator="equals"
                  label="Taxable income"
                  hint={`${formatLkr(ordinaryIncome)} − ${formatLkr(result.total_reliefs)} = ${formatLkr(result.taxable_income)}. This is what ordinary rate bands use.`}
                  value={formatLkr(result.taxable_income)}
                  tone="mid"
                />
              </>
            ) : (
              <>
                <FlowRow
                  operator="minus"
                  label="Reliefs"
                  hint="Approved reductions (personal relief, solar, donations, and so on)."
                  value={formatLkr(result.total_reliefs)}
                  tone="reduce"
                />
                <FlowRow
                  operator="equals"
                  label="Taxable income"
                  hint={`${formatLkr(result.gross_income)} − ${formatLkr(result.total_reliefs)} = ${formatLkr(result.taxable_income)}. This is what the rate bands use.`}
                  value={formatLkr(result.taxable_income)}
                  tone="mid"
                />
              </>
            )}
          </div>
        </div>

        <div className="flex justify-center text-[var(--uv-text-muted)]" aria-hidden>
          <ArrowDown className="h-4 w-4" />
        </div>

        <div>
          <StageTitle
            step={2}
            title="Tax on that amount"
            subtitle={
              hasTerminal
                ? "Ordinary bands on taxable income, plus separate tax on terminal benefits."
                : "Progressive rate bands turn taxable income into tax payable."
            }
          />
          <div className="space-y-2">
            {hasTerminal && terminalTax > 0 ? (
              <>
                <FlowRow
                  label="Ordinary income tax"
                  hint="Tax from the First Schedule bands on taxable income."
                  value={formatLkr(ordinaryTax)}
                />
                <FlowRow
                  operator="plus"
                  label="Terminal-benefit tax"
                  hint="Separate tax ladder on the terminal benefits set aside above."
                  value={formatLkr(terminalTax)}
                  tone="aside"
                />
                <FlowRow
                  operator="equals"
                  label="Tax payable"
                  hint="Ordinary tax + terminal-benefit tax, before credits."
                  value={formatLkr(result.tax_payable)}
                  tone="mid"
                />
              </>
            ) : (
              <FlowRow
                label="Tax payable"
                hint="Total tax before counting money already paid at source."
                value={formatLkr(result.tax_payable)}
                tone="mid"
              />
            )}
            {hasCredits ? (
              <>
                {apit > 0 ? (
                  <FlowRow
                    operator="minus"
                    label="APIT credit"
                    hint="Pay-as-you-earn tax already taken from salary."
                    value={formatLkr(apit)}
                    tone="reduce"
                  />
                ) : null}
                {wht > 0 ? (
                  <FlowRow
                    operator="minus"
                    label="WHT credit"
                    hint="Withholding tax already paid on some income."
                    value={formatLkr(wht)}
                    tone="reduce"
                  />
                ) : null}
              </>
            ) : null}
            <FlowRow
              operator="equals"
              label={refund > 0 ? "Refund due" : "Balance payable"}
              hint={
                refund > 0
                  ? "Credits were higher than tax — this is what comes back."
                  : hasCredits
                    ? "What remains after subtracting tax already paid."
                    : "What you still need to pay for this year."
              }
              value={formatLkr(refund > 0 ? refund : balance)}
              tone="hero"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
