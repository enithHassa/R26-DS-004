/**
 * Duplicated income-card sections from calculator.tsx (Phase 2).
 * Do not import from calculator.tsx — that file must stay untouched.
 */
import { useMemo } from "react";
import { Info, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { FilingCatalogCard, FilingCatalogField } from "../../api";
import { formatLkr, formatMoneyInput } from "../../format-lkr";
import { CatalogCardShell } from "../../components/catalog-card-shell";
import { CatalogFieldRow } from "../../components/field-explain";

/** Subset of calculator FormState used by the four income cards. */
export type IncomeFormSlice = {
  employment_income: string;
  employment_final_withholding: string;
  business_income: string;
  business_gross: string;
  business_deductions: string;
  capital_allowances: string;
  investment_income: string;
  investment_final_withholding: string;
  other_income: string;
  other_final_withholding: string;
};

export function parseLkr(value: string): number {
  const cleaned = value.replace(/,/g, "").trim();
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

export type EmploymentInputMode = "components" | "total";
export type InvestmentInputMode = "components" | "total";
export type OtherInputMode = "components" | "total";
/** Mutually exclusive business entry paths (catalog-driven when available). */
export type BusinessInputMode = "net" | "breakdown";

export type OtherCustomRow = {
  key: string;
  label: string;
  amount: string;
};

export function EmploymentIncomeSection({
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
  card?: FilingCatalogCard | null;
  mode: EmploymentInputMode;
  onModeChange: (mode: EmploymentInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
}) {
  const componentSubtotal = useMemo(() => {
    return fields.reduce((sum, field) => {
      const amount = parseLkr(amounts[field.component_id] ?? "0");
      if (field.default_treatment === "include") return sum + amount;
      return sum;
    }, 0);
  }, [fields, amounts]);

  function switchMode(next: EmploymentInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "total") {
      // Keep classic total demo path.
    } else {
      onPatch("employment_income", "0");
      onPatch("employment_final_withholding", "0");
    }
  }

  return (
    <CatalogCardShell
      card={card}
      title="Employment Income"
      subtitle="Catalog-driven Sec 5 components or a single annual total."
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
          ) : (
            <div className="space-y-3">
              {fields.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Loading employment catalog fields…
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {fields.map((field) => (
                    <CatalogFieldRow
                      key={field.component_id}
                      field={field}
                      amount={amounts[field.component_id] ?? "0"}
                      onAmountChange={(v) => onAmountChange(field.component_id, v)}
                      actVersionLabel={actVersionLabel}
                      onExplain={() => onExplainField(field)}
                    />
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Included subtotal (client preview):{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(componentSubtotal))}
                </span>
                {" "}— Rule Engine aggregates with Act provenance.
              </p>
            </div>
          )}
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
  card?: FilingCatalogCard | null;
  mode: BusinessInputMode;
  onModeChange: (mode: BusinessInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
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

  function fieldHint(field: FilingCatalogField): string {
    const sec = field.paragraph
      ? `Sec ${field.section}(${field.paragraph})`
      : `Sec ${field.section}`;
    return field.reason_short ? `${sec} — ${field.reason_short}` : sec;
  }

  function renderCatalogField(field: FilingCatalogField) {
    return (
      <CatalogFieldRow
        key={field.component_id}
        field={field}
        amount={amounts[field.component_id] ?? "0"}
        onAmountChange={(v) => onAmountChange(field.component_id, v)}
        actVersionLabel={actVersionLabel}
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
                <div className="grid gap-3 sm:grid-cols-2">
                  {netFields.map(renderCatalogField)}
                </div>
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
                </span>
                {" "}
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
  actVersionLabel,
  onExplainField,
}: {
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  treatmentLabel?: (field: FilingCatalogField) => string;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {fields.map((field) => (
        <CatalogFieldRow
          key={field.component_id}
          field={field}
          amount={amounts[field.component_id] ?? "0"}
          onAmountChange={(v) => onAmountChange(field.component_id, v)}
          actVersionLabel={actVersionLabel}
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
}: {
  card?: FilingCatalogCard | null;
  mode: InvestmentInputMode;
  onModeChange: (mode: InvestmentInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
}) {
  const includeFields = useMemo(
    () => fields.filter((f) => f.default_treatment === "include"),
    [fields],
  );
  const exclusionFields = useMemo(
    () =>
      fields.filter(
        (f) =>
          f.default_treatment === "final_withholding" ||
          f.default_treatment === "exempt",
      ),
    [fields],
  );

  const includeSubtotal = useMemo(() => {
    return includeFields.reduce((sum, field) => {
      return sum + parseLkr(amounts[field.component_id] ?? "0");
    }, 0);
  }, [includeFields, amounts]);

  const exclusionSubtotal = useMemo(() => {
    return exclusionFields.reduce((sum, field) => {
      return sum + parseLkr(amounts[field.component_id] ?? "0");
    }, 0);
  }, [exclusionFields, amounts]);

  const netPreview = Math.max(0, includeSubtotal - exclusionSubtotal);

  const estimatedNet = useMemo(() => {
    const gross = parseLkr(form.investment_income);
    const excluded = Math.min(parseLkr(form.investment_final_withholding), gross);
    return Math.max(0, gross - excluded);
  }, [form.investment_income, form.investment_final_withholding]);

  function switchMode(next: InvestmentInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "components") {
      onPatch("investment_income", "0");
      onPatch("investment_final_withholding", "0");
    }
  }

  return (
    <CatalogCardShell
      card={card}
      title="Investment Income"
      subtitle="Sec 7 includes and final withholding exclusions — components or single total."
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
            <div className="space-y-3">
              <div className="grid gap-4 sm:grid-cols-2">
                <MoneyField
                  id="investment_income"
                  label="Gross investment income (annual LKR)"
                  hint="Dividends, interest, rent, royalties, etc. before exclusions."
                  value={form.investment_income}
                  onChange={(v) => onPatch("investment_income", v)}
                />
                <MoneyField
                  id="investment_final_withholding"
                  label="Less: Exempt / Final Withholding (Sec 7(3)(a))"
                  hint="Excluded from investment income — not an income include."
                  value={form.investment_final_withholding}
                  onChange={(v) => onPatch("investment_final_withholding", v)}
                />
              </div>
              {parseLkr(form.investment_income) > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Estimated net going to assessable income:{" "}
                  <span className="font-medium text-foreground">
                    {formatLkr(String(estimatedNet))}
                  </span>
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-4">
              {fields.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Loading investment catalog fields…
                </p>
              ) : (
                <>
                  <div className="space-y-2">
                    <div className="border-b border-border pb-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
                        Income components
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        Sec 7(2) amounts included in gains and profits from an investment.
                      </p>
                    </div>
                    <CatalogMoneyFields
                      fields={includeFields}
                      amounts={amounts}
                      onAmountChange={onAmountChange}
                      treatmentLabel={() => "include"}
                      actVersionLabel={actVersionLabel}
                      onExplainField={onExplainField}
                    />
                  </div>

                  {exclusionFields.length > 0 ? (
                    <div className="space-y-2 rounded-md border border-dashed border-border bg-background/60 p-3">
                      <div className="border-b border-border pb-1">
                        <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
                          Exclusions
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          Sec 7(3) — subtracted from investment income; not added as income.
                        </p>
                      </div>
                      <CatalogMoneyFields
                        fields={exclusionFields}
                        amounts={amounts}
                        onAmountChange={onAmountChange}
                        treatmentLabel={() => "less / exclude"}
                        actVersionLabel={actVersionLabel}
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
                          </span>
                          {" "}
                          → net preview{" "}
                          <span className="font-medium text-foreground">
                            {formatLkr(String(netPreview))}
                          </span>
                        </>
                      ) : null}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Rule Engine aggregates Sec 7(2) includes, then applies Sec 7(3)(a)
                      exclusions when Act provenance resolves.
                    </p>
                  </div>

                  <div className="rounded-md border bg-muted/40 p-3 text-[11px] text-muted-foreground space-y-1">
                    <p className="font-medium text-foreground">Source provenance</p>
                    <p>
                      Inland Revenue Act No. 24 of 2017 · Section 7(2)(a)–(f) includes ·
                      Section 7(3)(a) exclusions
                    </p>
                    <p>
                      Amendments checked: 2021, 2022, 2023, 2025, 2026 · Status: ✓ No
                      identified amendment to the Section 7 component list
                    </p>
                  </div>
                </>
              )}
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
  card?: FilingCatalogCard | null;
  mode: OtherInputMode;
  onModeChange: (mode: OtherInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  customRows: OtherCustomRow[];
  onCustomRowsChange: (rows: OtherCustomRow[]) => void;
  form: IncomeFormSlice;
  onPatch: <K extends keyof IncomeFormSlice>(key: K, value: IncomeFormSlice[K]) => void;
  open: boolean;
  onToggle: () => void;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
}) {
  const residualField = fields.find((f) => f.component_id === "oth_residual");
  const customField = fields.find((f) => f.component_id === "oth_custom");
  const exclusionFields = fields.filter(
    (f) =>
      f.default_treatment === "final_withholding" ||
      f.default_treatment === "exempt",
  );

  const includeSubtotal = useMemo(() => {
    const residual = parseLkr(amounts.oth_residual ?? "0");
    const custom = customRows.reduce((sum, row) => sum + parseLkr(row.amount), 0);
    return residual + custom;
  }, [amounts.oth_residual, customRows]);

  const exclusionSubtotal = useMemo(() => {
    return exclusionFields.reduce((sum, field) => {
      return sum + parseLkr(amounts[field.component_id] ?? "0");
    }, 0);
  }, [exclusionFields, amounts]);

  const netPreview = Math.max(0, includeSubtotal - exclusionSubtotal);

  const estimatedNet = useMemo(() => {
    const gross = parseLkr(form.other_income);
    const excluded = Math.min(parseLkr(form.other_final_withholding), gross);
    return Math.max(0, gross - excluded);
  }, [form.other_income, form.other_final_withholding]);

  function switchMode(next: OtherInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "components") {
      onPatch("other_income", "0");
      onPatch("other_final_withholding", "0");
    }
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
      subtitle="Sec 8 residual sources — Medium confidence unless a direct Sec 8 paragraph applies."
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
          ) : fields.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Loading other-income catalog fields…
            </p>
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
                    actVersionLabel={actVersionLabel}
                    onExplainField={onExplainField}
                  />
                  {residualField.confidence_reason ? (
                    <p className="text-[11px] text-muted-foreground">
                      {residualField.confidence_reason}
                    </p>
                  ) : null}
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
                {customField?.confidence_reason ? (
                  <p className="text-[11px] text-muted-foreground">
                    {customField.confidence_reason}
                  </p>
                ) : null}
                {customRows.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground">
                    Optional labeled sources under Sec 8. Confirm each is not already
                    under Sec 5, 6, or 7.
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
                              patchCustomRow(row.key, {
                                label: event.target.value,
                              })
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
                    actVersionLabel={actVersionLabel}
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
                      </span>
                      {" "}
                      → net preview{" "}
                      <span className="font-medium text-foreground">
                        {formatLkr(String(netPreview))}
                      </span>
                    </>
                  ) : null}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Casual and non-recurring profits are outside Sec 8. Do not re-enter
                  amounts already under employment, business, or investment.
                </p>
              </div>

              <div className="rounded-md border bg-muted/40 p-3 text-[11px] text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">Source provenance</p>
                <p>
                  Inland Revenue Act No. 24 of 2017 · Section 8(1) residual head ·
                  Section 8(2)(a)–(b) exclusions
                </p>
                <p>
                  Custom / residual classification defaults to Medium confidence
                  (interpretive) — not Guide-backed High confidence.
                </p>
              </div>
            </>
          )}
        </div>
    </CatalogCardShell>
  );
}
