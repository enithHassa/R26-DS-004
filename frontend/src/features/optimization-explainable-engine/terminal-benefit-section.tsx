import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { CatalogCardShell } from "./catalog-card-shell";
import { formatMoneyInput } from "./format-lkr";
import { useInterview } from "./session";
import {
  TERMINAL_BENEFIT_TYPE_OPTIONS,
  newTerminalBenefitRow,
  showsEmploymentPeriodQuestion,
  showsTerminalPeriod,
  unusedTerminalBenefitTypes,
} from "./terminal-benefits";
import type { TerminalBenefitRow, TerminalBenefitType } from "./types";

export function TerminalBenefitSection({
  open,
  onToggle,
  actVersionLabel,
  onExplain,
}: {
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplain: () => void;
}) {
  const { session, patchIncome } = useInterview();
  const { income, assessmentYear } = session;
  const rows = income.terminalBenefits ?? [];
  const has = Boolean(income.hasTerminalBenefits);
  const allTypesUsed = rows.length >= TERMINAL_BENEFIT_TYPE_OPTIONS.length;
  const fieldHint = has
    ? `${rows.length} benefit${rows.length === 1 ? "" : "s"}`
    : "optional";

  function setHasTerminalBenefits(next: boolean): void {
    if (next) {
      patchIncome({
        hasTerminalBenefits: true,
        terminalBenefits: rows.length > 0 ? rows : [newTerminalBenefitRow()],
      });
      return;
    }
    patchIncome({ hasTerminalBenefits: false, terminalBenefits: [] });
  }

  function patchRow(id: string, patch: Partial<TerminalBenefitRow>): void {
    patchIncome((prev) => ({
      terminalBenefits: (prev.terminalBenefits ?? []).map((row) =>
        row.id === id ? { ...row, ...patch } : row,
      ),
    }));
  }

  function addRow(): void {
    if (allTypesUsed) return;
    patchIncome((prev) => ({
      hasTerminalBenefits: true,
      terminalBenefits: [...(prev.terminalBenefits ?? []), newTerminalBenefitRow()],
    }));
  }

  function removeRow(id: string): void {
    patchIncome((prev) => {
      const next = (prev.terminalBenefits ?? []).filter((row) => row.id !== id);
      if (next.length === 0) {
        return { hasTerminalBenefits: false, terminalBenefits: [] };
      }
      return { terminalBenefits: next };
    });
  }

  return (
    <CatalogCardShell
      title="Retirement & terminal benefits"
      subtitle="Commuted pension, retiring gratuity, loss of office, or ETF at retirement — taxed on a special ladder, separate from ordinary income."
      actVersionLabel={actVersionLabel}
      fieldCount={has ? rows.length : undefined}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3 border-t border-border/60 pt-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Optional — most returns leave this as No.{" "}
            <span className="text-[10px] text-muted-foreground/80">({fieldHint})</span>
          </p>
          <button
            type="button"
            className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            onClick={onExplain}
            aria-label="Explain retirement and terminal benefits"
          >
            <Info className="h-3 w-3" aria-hidden />
            Explain
          </button>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Did you receive any of these benefits?</legend>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name="has-terminal-benefits"
                checked={!has}
                onChange={() => setHasTerminalBenefits(false)}
              />
              No
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name="has-terminal-benefits"
                checked={has}
                onChange={() => setHasTerminalBenefits(true)}
              />
              Yes
            </label>
          </div>
        </fieldset>

        {has
          ? rows.map((row, index) => (
              <TerminalBenefitRowCard
                key={row.id}
                row={row}
                index={index}
                assessmentYear={assessmentYear}
                availableTypes={unusedTerminalBenefitTypes(rows, row.id)}
                onPatch={(patch) => patchRow(row.id, patch)}
                onRemove={() => removeRow(row.id)}
              />
            ))
          : null}

        {has && !allTypesUsed ? (
          <Button type="button" size="sm" variant="outline" onClick={addRow}>
            + Add another terminal benefit
          </Button>
        ) : null}
      </div>
    </CatalogCardShell>
  );
}

function TerminalBenefitRowCard({
  row,
  index,
  assessmentYear,
  availableTypes,
  onPatch,
  onRemove,
}: {
  row: TerminalBenefitRow;
  index: number;
  assessmentYear: string;
  availableTypes: Exclude<TerminalBenefitType, "">[];
  onPatch: (patch: Partial<TerminalBenefitRow>) => void;
  onRemove: () => void;
}) {
  const typeOptions = TERMINAL_BENEFIT_TYPE_OPTIONS.filter(
    (option) => availableTypes.includes(option.value) || option.value === row.type,
  );
  const showPeriod = showsTerminalPeriod(assessmentYear);
  const showYears = showsEmploymentPeriodQuestion(assessmentYear, row.terminalBenefitPeriod);
  const showScheme = row.type === "loss_of_office_compensation";
  const typeLabel =
    TERMINAL_BENEFIT_TYPE_OPTIONS.find((option) => option.value === row.type)?.label ??
    `benefit ${index + 1}`;

  return (
    <div className="space-y-3 rounded-md border border-border/80 bg-background/40 p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor={`terminal-type-${row.id}`}>Type</Label>
          <select
            id={`terminal-type-${row.id}`}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            value={row.type}
            onChange={(event) =>
              onPatch({
                type: event.target.value as TerminalBenefitType,
                lossOfOfficeSchemeApproved:
                  event.target.value === "loss_of_office_compensation"
                    ? row.lossOfOfficeSchemeApproved
                    : false,
              })
            }
          >
            <option value="">Select a benefit type</option>
            {typeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor={`terminal-amount-${row.id}`}>Amount (LKR)</Label>
          <Input
            id={`terminal-amount-${row.id}`}
            inputMode="decimal"
            value={formatMoneyInput(row.amount ?? "0")}
            onChange={(event) => onPatch({ amount: formatMoneyInput(event.target.value) })}
          />
        </div>
      </div>
      {showPeriod ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">When was this paid in 2019/20?</legend>
          <p className="text-[11px] text-muted-foreground">
            2019/20 is not one blended rate — choose the period this payment belongs to.
          </p>
          <div className="flex flex-col gap-2 text-sm">
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name={`terminal-period-${row.id}`}
                checked={row.terminalBenefitPeriod === "pre_2020"}
                onChange={() => onPatch({ terminalBenefitPeriod: "pre_2020" })}
              />
              1 April 2019 – 31 December 2019
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name={`terminal-period-${row.id}`}
                checked={row.terminalBenefitPeriod === "from_2020_01_01"}
                onChange={() =>
                  onPatch({
                    terminalBenefitPeriod: "from_2020_01_01",
                    employmentPeriodOver20Years: false,
                  })
                }
              />
              1 January 2020 – 31 March 2020
            </label>
          </div>
        </fieldset>
      ) : null}
      {showYears ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Employment or contribution period</legend>
          <div className="flex flex-col gap-2 text-sm">
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name={`terminal-years-${row.id}`}
                checked={!row.employmentPeriodOver20Years}
                onChange={() => onPatch({ employmentPeriodOver20Years: false })}
              />
              20 years or less
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name={`terminal-years-${row.id}`}
                checked={row.employmentPeriodOver20Years}
                onChange={() => onPatch({ employmentPeriodOver20Years: true })}
              />
              More than 20 years
            </label>
          </div>
        </fieldset>
      ) : null}
      {showScheme ? (
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={row.lossOfOfficeSchemeApproved}
            onChange={(event) => onPatch({ lossOfOfficeSchemeApproved: event.target.checked })}
          />
          Paid under a scheme uniformly applicable to all employees (Commissioner-General)
        </label>
      ) : null}
      <Button type="button" size="sm" variant="ghost" onClick={onRemove}>
        Remove {typeLabel}
      </Button>
    </div>
  );
}
