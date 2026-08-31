import { useMemo, type ReactNode } from "react";
import { Info, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { CatalogCardShell } from "./catalog-card-shell";
import { CatalogFieldRow } from "./field-explain";
import { formatLkr, formatMoneyInput, parseLkr } from "./format-lkr";
import type { IncomeCatalogCard, IncomeCatalogField } from "./income-catalog";
import type {
  BusinessInputMode,
  EmploymentInputMode,
  IncomeFormSlice,
  InvestmentInputMode,
  OtherCustomRow,
  OtherInputMode,
} from "./types";

export type { OtherCustomRow };

export function EmploymentIncomeSection({
  card,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  form,
  onPatch,
  apitAlreadyPaid,
  onApitChange,
  open,
  onToggle,
  actVersionLabel,
  onExplainField,
}: {
  card?: IncomeCatalogCard | null;
  mode: EmploymentInputMode;
  onModeChange: (mode: EmploymentInputMode) => void;
  fields: IncomeCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  apitAlreadyPaid: string;
  onApitChange: (value: string) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: IncomeCatalogField) => void;
}) {
  const componentSubtotal = useMemo(() => {
    return fields.reduce((sum, field) => {
      const amount = parseLkr(amounts[field.component_id] ?? "0");
      if (field.default_treatment === "include") return sum + amount;
      return sum;
    }, 0);
  }, [fields, amounts]);

  const exclusionTotal = useMemo(() => {
    return fields.reduce((sum, field) => {
      if (field.default_treatment !== "final_withholding") return sum;
      return sum + parseLkr(amounts[field.component_id] ?? "0");
    }, 0);
  }, [fields, amounts]);

  function switchMode(next: EmploymentInputMode): void {
    if (next === mode) return;
    if (next === "total") {
      onPatch("employment_income", String(Math.max(0, componentSubtotal)));
      onPatch("employment_final_withholding", String(exclusionTotal));
    } else {
      onPatch("employment_income", "0");
      onPatch("employment_final_withholding", "0");
    }
    onModeChange(next);
  }

  return (
    <CatalogCardShell
      card={card}
      title="Employment Income"
      subtitle="Sec 5 components or a single annual total."
      actVersionLabel={actVersionLabel}
      fieldCount={fields.length}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "components" ? "default" : "outline"}
            onClick={() => switchMode("components")}
          >
            Components
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "total" ? "default" : "outline"}
            onClick={() => switchMode("total")}
          >
            Single total
          </Button>
        </div>

        {mode === "total" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <MoneyField
              id="employment_income"
              label="Employment income"
              value={form.employment_income}
              onChange={(v) => onPatch("employment_income", v)}
            />
            <MoneyField
              id="employment_final_withholding"
              label="Final WHT / exempt amounts (Sec 5(3)(a))"
              hint="Optional — amounts excluded from assessable employment income."
              value={form.employment_final_withholding}
              onChange={(v) => onPatch("employment_final_withholding", v)}
            />
          </div>
        ) : fields.length === 0 ? (
          <p className="text-xs text-muted-foreground">No employment fields loaded.</p>
        ) : (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              {fields.map((field) => (
                <CatalogFieldRow
                  key={field.component_id}
                  field={field}
                  amount={amounts[field.component_id] ?? "0"}
                  onAmountChange={(v) => onAmountChange(field.component_id, v)}
                  onExplain={() => onExplainField(field)}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Included subtotal:{" "}
              <span className="font-medium text-foreground">
                {formatLkr(String(componentSubtotal))}
              </span>
              {exclusionTotal > 0 ? (
                <>
                  {" "}
                  − exclusions {formatLkr(String(exclusionTotal))} → net{" "}
                  <span className="font-medium text-foreground">
                    {formatLkr(String(Math.max(0, componentSubtotal - exclusionTotal)))}
                  </span>
                </>
              ) : null}
            </p>
          </div>
        )}

        <div className="rounded-md border border-dashed bg-muted/20 p-3">
          <MoneyField
            id="apit_already_paid"
            label="APIT deducted at source (tax credit)"
            hint="From APIT Certificate / Form 16 — credited against tax payable, not subtracted from employment income."
            value={apitAlreadyPaid}
            onChange={onApitChange}
          />
        </div>
      </div>
    </CatalogCardShell>
  );
}

function MoneyField({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        inputMode="numeric"
        value={formatMoneyInput(value)}
        onChange={(event) => onChange(formatMoneyInput(event.target.value))}
        placeholder="0"
      />
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function BusinessIncomeSection({
  card,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  form,
  onPatch,
  open,
  onToggle,
  actVersionLabel,
  onExplainField,
}: {
  card?: IncomeCatalogCard | null;
  mode: BusinessInputMode;
  onModeChange: (mode: BusinessInputMode) => void;
  fields: IncomeCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: IncomeCatalogField) => void;
}) {
  const useCatalog = fields.length > 0;
  const netFields = fields
    .filter((f) => f.ui_group === "net")
    .sort((a, b) => a.sort_order - b.sort_order);
  const breakdownFields = fields
    .filter((f) => f.ui_group === "breakdown")
    .sort((a, b) => a.sort_order - b.sort_order);

  const estimatedNet = useMemo(() => {
    if (mode === "net") {
      if (useCatalog) return parseLkr(amounts.biz_net_profits ?? "0");
      return parseLkr(form.business_income);
    }
    const gross = useCatalog
      ? parseLkr(amounts.biz_gross ?? "0")
      : parseLkr(form.business_gross);
    const deductions = Math.min(
      useCatalog
        ? parseLkr(amounts.biz_deductions ?? "0")
        : parseLkr(form.business_deductions),
      gross,
    );
    const remaining = gross - deductions;
    const ca = Math.min(
      useCatalog
        ? parseLkr(amounts.biz_capital_allowances ?? "0")
        : parseLkr(form.capital_allowances),
      remaining,
    );
    return Math.max(0, gross - deductions - ca);
  }, [
    mode,
    useCatalog,
    amounts,
    form.business_income,
    form.business_gross,
    form.business_deductions,
    form.capital_allowances,
  ]);

  function clearCatalogGroup(group: "net" | "breakdown"): void {
    for (const field of fields) {
      if (field.ui_group === group) {
        onAmountChange(field.component_id, "0");
      }
    }
  }

  function switchMode(next: BusinessInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "net") {
      clearCatalogGroup("breakdown");
      onPatch("business_gross", "0");
      onPatch("business_deductions", "0");
      onPatch("capital_allowances", "0");
    } else {
      clearCatalogGroup("net");
      onPatch("business_income", "0");
    }
  }

  function fieldHint(field: IncomeCatalogField): string {
    const sec = field.paragraph
      ? `Sec ${field.section}(${field.paragraph})`
      : `Sec ${field.section}`;
    return field.reason_short ? `${sec} — ${field.reason_short}` : sec;
  }

  function renderCatalogField(field: IncomeCatalogField) {
    return (
      <CatalogFieldRow
        key={field.component_id}
        field={field}
        amount={amounts[field.component_id] ?? "0"}
        onAmountChange={(v) => onAmountChange(field.component_id, v)}
        onExplain={() => onExplainField(field)}
        hint={fieldHint(field)}
      />
    );
  }

  return (
    <CatalogCardShell
      card={card}
      title="Business Income"
      subtitle="Net profits or gross minus Sec 11 expenses and Sec 16 capital allowances."
      actVersionLabel={actVersionLabel}
      fieldCount={fields.length}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "net" ? "default" : "outline"}
            onClick={() => switchMode("net")}
          >
            Net profits
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "breakdown" ? "default" : "outline"}
            onClick={() => switchMode("breakdown")}
          >
            Gross minus deductions
          </Button>
        </div>

        {mode === "net" ? (
          useCatalog && netFields.length > 0 ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">{netFields.map(renderCatalogField)}</div>
              <p className="text-xs text-muted-foreground">
                Amount included in assessable income:{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(estimatedNet))}
                </span>
              </p>
            </div>
          ) : (
            <MoneyField
              id="business_income"
              label="Net assessable profits (annual LKR)"
              hint="Profits after allowable expenses — the amount that goes into assessable income."
              value={form.business_income}
              onChange={(v) => onPatch("business_income", v)}
            />
          )
        ) : useCatalog && breakdownFields.length > 0 ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              {breakdownFields.map(renderCatalogField)}
            </div>
            <p className="text-xs text-muted-foreground">
              Estimated net for assessable income:{" "}
              <span className="font-medium text-foreground">
                {formatLkr(String(estimatedNet))}
              </span>{" "}
              (gross − Sec 11 expenses − Sec 16 capital allowances)
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid gap-4 sm:grid-cols-3">
              <MoneyField
                id="business_gross"
                label="Gross receipts"
                hint="Total business income before deductions."
                value={form.business_gross}
                onChange={(v) => onPatch("business_gross", v)}
              />
              <MoneyField
                id="business_deductions"
                label="Allowable expenses"
                hint="Sec 11 — operating expenses incurred in producing income."
                value={form.business_deductions}
                onChange={(v) => onPatch("business_deductions", v)}
              />
              <MoneyField
                id="capital_allowances"
                label="Capital allowances"
                hint="Sec 16 — depreciation / CA claimed for the year."
                value={form.capital_allowances}
                onChange={(v) => onPatch("capital_allowances", v)}
              />
            </div>
            {parseLkr(form.business_gross) > 0 ? (
              <p className="text-xs text-muted-foreground">
                Estimated net for assessable income:{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(estimatedNet))}
                </span>
              </p>
            ) : null}
          </div>
        )}
      </div>
    </CatalogCardShell>
  );
}

function CatalogMoneyFields({
  fields,
  amounts,
  onAmountChange,
  treatmentLabel,
  onExplainField,
}: {
  fields: IncomeCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  treatmentLabel?: (field: IncomeCatalogField) => string;
  onExplainField: (field: IncomeCatalogField) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {fields.map((field) => (
        <CatalogFieldRow
          key={field.component_id}
          field={field}
          amount={amounts[field.component_id] ?? "0"}
          onAmountChange={(v) => onAmountChange(field.component_id, v)}
          onExplain={() => onExplainField(field)}
          treatmentLabel={treatmentLabel}
        />
      ))}
    </div>
  );
}

export function InvestmentIncomeSection({
  card,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  form,
  onPatch,
  open,
  onToggle,
  actVersionLabel,
  onExplainField,
  scheduleInterestLkr,
  interestSchedule,
}: {
  card?: IncomeCatalogCard | null;
  mode: InvestmentInputMode;
  onModeChange: (mode: InvestmentInputMode) => void;
  fields: IncomeCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: IncomeCatalogField) => void;
  scheduleInterestLkr: number;
  interestSchedule?: ReactNode;
}) {
  const includeFields = useMemo(
    () =>
      fields.filter(
        (f) => f.default_treatment === "include" && f.component_id !== "inv_interest",
      ),
    [fields],
  );
  const exclusionFields = useMemo(
    () =>
      fields.filter(
        (f) =>
          f.default_treatment === "final_withholding" || f.default_treatment === "exempt",
      ),
    [fields],
  );

  const includeSubtotal = useMemo(() => {
    const other = includeFields.reduce(
      (sum, field) => sum + parseLkr(amounts[field.component_id] ?? "0"),
      0,
    );
    return other + scheduleInterestLkr;
  }, [includeFields, amounts, scheduleInterestLkr]);

  const exclusionSubtotal = useMemo(() => {
    return exclusionFields.reduce(
      (sum, field) => sum + parseLkr(amounts[field.component_id] ?? "0"),
      0,
    );
  }, [exclusionFields, amounts]);

  const netPreview = Math.max(0, includeSubtotal - exclusionSubtotal);

  const estimatedNet = useMemo(() => {
    const gross = parseLkr(form.investment_income);
    const excluded = Math.min(parseLkr(form.investment_final_withholding), gross);
    return Math.max(0, gross - excluded);
  }, [form.investment_income, form.investment_final_withholding]);

  function switchMode(next: InvestmentInputMode): void {
    if (next === mode) return;
    if (next === "total") {
      onPatch("investment_income", String(netPreview));
    } else {
      onPatch("investment_income", "0");
      onPatch("investment_final_withholding", "0");
    }
    onModeChange(next);
  }

  return (
    <CatalogCardShell
      card={card}
      title="Investment Income"
      subtitle="Enter interest on the WHT schedule. Other Sec 7 components below."
      actVersionLabel={actVersionLabel}
      fieldCount={fields.filter((f) => f.component_id !== "inv_interest").length}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "components" ? "default" : "outline"}
            onClick={() => switchMode("components")}
          >
            Components
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "total" ? "default" : "outline"}
            onClick={() => switchMode("total")}
          >
            Single total
          </Button>
        </div>

        {mode === "total" ? (
          <div className="space-y-3">
            <div className="grid gap-4 sm:grid-cols-2">
              <MoneyField
                id="investment_income"
                label="Gross investment income (annual LKR)"
                hint="Includes interest from the WHT schedule when you switch from Components."
                value={form.investment_income}
                onChange={(v) => onPatch("investment_income", v)}
              />
              <MoneyField
                id="investment_final_withholding"
                label="Final WHT / exempt amounts (Sec 7(3)(a))"
                hint="Optional — amounts excluded from assessable investment income."
                value={form.investment_final_withholding}
                onChange={(v) => onPatch("investment_final_withholding", v)}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Estimated net going to assessable income:{" "}
              <span className="font-medium text-foreground">
                {formatLkr(String(estimatedNet))}
              </span>
              . WHT schedule below is the interest relief base and tax credit only — not
              added again on top of this total.
            </p>
            {interestSchedule}
          </div>
        ) : (
          <div className="space-y-3">
            {interestSchedule}
            {includeFields.length === 0 && exclusionFields.length === 0 ? (
              <p className="text-xs text-muted-foreground">No investment fields loaded.</p>
            ) : (
              <CatalogMoneyFields
                fields={[...includeFields, ...exclusionFields]}
                amounts={amounts}
                onAmountChange={onAmountChange}
                onExplainField={onExplainField}
              />
            )}
            <p className="text-xs text-muted-foreground">
              Included subtotal:{" "}
              <span className="font-medium text-foreground">
                {formatLkr(String(includeSubtotal))}
              </span>
              {exclusionSubtotal > 0 ? (
                <>
                  {" "}
                  − exclusions {formatLkr(String(exclusionSubtotal))} → net{" "}
                  <span className="font-medium text-foreground">
                    {formatLkr(String(netPreview))}
                  </span>
                </>
              ) : null}
            </p>
          </div>
        )}
      </div>
    </CatalogCardShell>
  );
}

export function OtherIncomeSection({
  card,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  customRows,
  onCustomRowsChange,
  form,
  onPatch,
  open,
  onToggle,
  actVersionLabel,
  onExplainField,
}: {
  card?: IncomeCatalogCard | null;
  mode: OtherInputMode;
  onModeChange: (mode: OtherInputMode) => void;
  fields: IncomeCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  customRows: OtherCustomRow[];
  onCustomRowsChange: (rows: OtherCustomRow[]) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: IncomeCatalogField) => void;
}) {
  const residualField = fields.find((f) => f.component_id === "oth_residual");
  const customField = fields.find((f) => f.component_id === "oth_custom");
  const exclusionFields = fields.filter(
    (f) =>
      f.default_treatment === "final_withholding" || f.default_treatment === "exempt",
  );

  const includeSubtotal = useMemo(() => {
    const residual = parseLkr(amounts.oth_residual ?? "0");
    const custom = customRows.reduce((sum, row) => sum + parseLkr(row.amount), 0);
    return residual + custom;
  }, [amounts.oth_residual, customRows]);

  const exclusionSubtotal = useMemo(() => {
    return exclusionFields.reduce(
      (sum, field) => sum + parseLkr(amounts[field.component_id] ?? "0"),
      0,
    );
  }, [exclusionFields, amounts]);

  const netPreview = Math.max(0, includeSubtotal - exclusionSubtotal);

  const estimatedNet = useMemo(() => {
    const gross = parseLkr(form.other_income);
    const excluded = Math.min(parseLkr(form.other_final_withholding), gross);
    return Math.max(0, gross - excluded);
  }, [form.other_income, form.other_final_withholding]);

  function switchMode(next: OtherInputMode): void {
    if (next === mode) return;
    if (next === "total") {
      onPatch("other_income", String(netPreview));
    } else {
      onPatch("other_income", "0");
      onPatch("other_final_withholding", "0");
    }
    onModeChange(next);
  }

  function addCustomRow(): void {
    onCustomRowsChange([
      ...customRows,
      {
        key: `custom-${Date.now()}-${customRows.length}`,
        label: "",
        amount: "0",
      },
    ]);
  }

  function patchCustomRow(
    key: string,
    patch: Partial<Pick<OtherCustomRow, "label" | "amount">>,
  ): void {
    onCustomRowsChange(
      customRows.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  }

  function removeCustomRow(key: string): void {
    onCustomRowsChange(customRows.filter((row) => row.key !== key));
  }

  return (
    <CatalogCardShell
      card={card}
      title="Other Income"
      subtitle="Sec 8 residual sources — medium confidence unless a direct Sec 8 paragraph applies."
      actVersionLabel={actVersionLabel}
      fieldCount={fields.length}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "components" ? "default" : "outline"}
            onClick={() => switchMode("components")}
          >
            Residual / custom
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "total" ? "default" : "outline"}
            onClick={() => switchMode("total")}
          >
            Single total
          </Button>
        </div>

        {mode === "total" ? (
          <div className="space-y-3">
            <div className="grid gap-4 sm:grid-cols-2">
              <MoneyField
                id="other_income"
                label="Other income (annual LKR)"
                hint="Sec 8 residual gains/profits — not employment, business, or investment."
                value={form.other_income}
                onChange={(v) => onPatch("other_income", v)}
              />
              <MoneyField
                id="other_final_withholding"
                label="Less: Exempt / Final Withholding (Sec 8(2)(a))"
                hint="Excluded from other income — not an income include."
                value={form.other_final_withholding}
                onChange={(v) => onPatch("other_final_withholding", v)}
              />
            </div>
            {parseLkr(form.other_income) > 0 ? (
              <p className="text-xs text-muted-foreground">
                Estimated net for assessable income:{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(estimatedNet))}
                </span>
              </p>
            ) : null}
          </div>
        ) : (
          <>
            {residualField ? (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">
                  Residual head (Sec 8(1))
                </p>
                <CatalogMoneyFields
                  fields={[residualField]}
                  amounts={amounts}
                  onAmountChange={onAmountChange}
                  treatmentLabel={() => "include (residual)"}
                  onExplainField={onExplainField}
                />
              </div>
            ) : null}

            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    Custom residual sources
                  </p>
                  {customField ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                      onClick={() => onExplainField(customField)}
                    >
                      <Info className="h-3 w-3" aria-hidden />
                      Explain
                    </button>
                  ) : null}
                </div>
                <Button type="button" size="sm" variant="outline" onClick={addCustomRow}>
                  <Plus className="h-3.5 w-3.5" />
                  Add source
                </Button>
              </div>
              {customRows.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">
                  Optional labeled sources under Sec 8. Confirm each is not already under
                  Sec 5, 6, or 7.
                </p>
              ) : (
                <div className="space-y-3">
                  {customRows.map((row) => (
                    <div
                      key={row.key}
                      className="grid gap-2 sm:grid-cols-[1fr_minmax(0,10rem)_auto]"
                    >
                      <div className="space-y-1">
                        <Label htmlFor={`${row.key}-label`}>Source label</Label>
                        <Input
                          id={`${row.key}-label`}
                          value={row.label}
                          onChange={(event) =>
                            patchCustomRow(row.key, { label: event.target.value })
                          }
                          placeholder="e.g. Freelance residual receipts"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`${row.key}-amount`}>Amount (LKR)</Label>
                        <Input
                          id={`${row.key}-amount`}
                          inputMode="numeric"
                          value={formatMoneyInput(row.amount)}
                          onChange={(event) =>
                            patchCustomRow(row.key, {
                              amount: formatMoneyInput(event.target.value),
                            })
                          }
                          placeholder="0"
                        />
                      </div>
                      <div className="flex items-end">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => removeCustomRow(row.key)}
                          aria-label="Remove custom source"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {exclusionFields.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">
                  Sec 8(2)(a) — subtracted from other income; not added as income.
                </p>
                <CatalogMoneyFields
                  fields={exclusionFields}
                  amounts={amounts}
                  onAmountChange={onAmountChange}
                  treatmentLabel={() => "less / exclude"}
                  onExplainField={onExplainField}
                />
              </div>
            ) : null}

            <div className="space-y-1 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">
                Included subtotal:{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(includeSubtotal))}
                </span>
                {exclusionSubtotal > 0 ? (
                  <>
                    {" "}
                    − exclusions{" "}
                    <span className="font-medium text-foreground">
                      {formatLkr(String(exclusionSubtotal))}
                    </span>{" "}
                    → net preview{" "}
                    <span className="font-medium text-foreground">
                      {formatLkr(String(netPreview))}
                    </span>
                  </>
                ) : null}
              </p>
            </div>
          </>
        )}
      </div>
    </CatalogCardShell>
  );
}
