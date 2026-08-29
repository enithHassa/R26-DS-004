import { cn } from "@/lib/utils";

import type { CalculateResponse } from "./api";
import { formatLkr } from "./format-lkr";

function Cell({
  label,
  value,
  tone = "default",
  className,
}: {
  label: string;
  value: number;
  tone?: "default" | "accent" | "credit" | "hero";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border px-2.5 py-2",
        tone === "accent" && "border-primary/30 bg-primary/5",
        tone === "credit" && "border-emerald-500/30 bg-emerald-500/5",
        tone === "hero" && "border-primary/35 bg-primary/8",
        tone === "default" && "border-border/80 bg-background",
        className,
      )}
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 tabular-nums tracking-tight",
          tone === "hero" ? "text-lg font-semibold sm:text-xl" : "text-sm font-semibold",
          tone === "accent" && "text-primary",
          tone === "credit" && "text-emerald-800 dark:text-emerald-200",
        )}
      >
        {formatLkr(value)}
      </p>
    </div>
  );
}

/** Compact result totals — one board, no tall vertical stack. */
export function ResultSummaryBoard({ result }: { result: CalculateResponse }) {
  const terminalTax = result.terminal_benefit_tax ?? 0;
  const ordinaryTax = Math.max(0, result.tax_payable - terminalTax);
  const wht = result.wht_credit ?? 0;
  const apit = result.apit_credit ?? 0;
  const refund = result.tax_refund ?? 0;
  const balance = result.balance_payable ?? result.tax_payable;

  return (
    <div className="rounded-xl border border-border/80 bg-card/40 p-3 shadow-sm">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">Result totals</p>
        <p className="text-[11px] text-muted-foreground">
          Income → reliefs → tax → credits
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Cell label="Assessable (gross)" value={result.gross_income} />
        <Cell label="Reliefs applied" value={result.total_reliefs} />
        <Cell label="Taxable income" value={result.taxable_income} tone="accent" />
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <Cell label="Tax payable" value={result.tax_payable} />
        <Cell label="APIT credit" value={apit} tone="credit" />
        <Cell label="WHT credit" value={wht} tone="credit" />
      </div>

      {terminalTax > 0 ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <Cell label="Ordinary income tax" value={ordinaryTax} />
          <Cell label="Terminal-benefit tax" value={terminalTax} />
        </div>
      ) : null}

      <Cell
        className="mt-2"
        label={refund > 0 ? "Refund due" : "Balance payable"}
        value={refund > 0 ? refund : balance}
        tone="hero"
      />
    </div>
  );
}
