import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Calculator,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  calculateTax,
  getFilingCatalog,
  getFilingCatalogExplain,
  type CalculateTaxRequest,
  type CalculateTaxResponse,
  type FilingCatalogCard,
  type FilingCatalogExplain,
  type FilingCatalogField,
  type FilingLine,
  type KnowledgeVersions,
  type QualifyingPaymentCategoryResult,
  type QualifyingPaymentSummary,
} from "../api";
import { formatLkr, formatMoneyInput, toMoneyWire } from "../format-lkr";
import { CalculatedUsingStrip } from "../components/calculated-using-strip";
import { UnresolvedClaimsBanner } from "../components/unresolved-claims-banner";
import {
  CalculatorGroupHead,
  CatalogCardShell,
} from "../components/catalog-card-shell";
import {
  CatalogFieldRow,
  FieldExplainDrawer,
} from "../components/field-explain";
import { TaxpayerResultSummary } from "../components/taxpayer-result-summary";
import {
  buildClearTestDataPatch,
  buildFillTestDataPatch,
  type CalculatorTestDataContext,
} from "../calculator-test-data";

type FormState = {
  assessment_year: "2024_25" | "2025_26";
  resident_status: "resident" | "non_resident";
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
  qualifying_payments: string;
  apit_already_paid: string;
};

function sec52CapLabel(year: FormState["assessment_year"]): "1.2M" | "1.8M" {
  return year === "2025_26" ? "1.8M" : "1.2M";
}

const INITIAL: FormState = {
  assessment_year: "2024_25",
  resident_status: "resident",
  employment_income: "0",
  employment_final_withholding: "0",
  business_income: "0",
  business_gross: "0",
  business_deductions: "0",
  capital_allowances: "0",
  investment_income: "0",
  investment_final_withholding: "0",
  other_income: "0",
  other_final_withholding: "0",
  qualifying_payments: "0",
  apit_already_paid: "0",
};

function Chip({ children }: { children: string }) {
  return (
    <span className="inline-flex max-w-full truncate rounded-md border bg-muted/60 px-1.5 py-0.5 text-[11px] text-foreground">
      {children}
    </span>
  );
}

type EmploymentInputMode = "components" | "total";
type InvestmentInputMode = "components" | "total";
type OtherInputMode = "components" | "total";
type DeductionInputMode = "components" | "total";
/** Mutually exclusive business entry paths (catalog-driven when available). */
type BusinessInputMode = "net" | "breakdown";

type OtherCustomRow = {
  key: string;
  label: string;
  amount: string;
};

function EmploymentIncomeSection({
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
  form: FormState;
  onPatch: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
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

function parseLkr(value: string): number {
  const cleaned = value.replace(/,/g, "").trim();
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

function BusinessIncomeSection({
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
  form: FormState;
  onPatch: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
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

function InvestmentIncomeSection({
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
  form: FormState;
  onPatch: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
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

function OtherIncomeSection({
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
  form: FormState;
  onPatch: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
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

function yaLabel(year: "2024_25" | "2025_26"): string {
  return year === "2025_26" ? "YA 2025/26" : "YA 2024/25";
}

type CarryForwardTone = "eligible" | "not_available" | "na" | "schedule";

type QpFieldLegalStatus = {
  /** Compact chip for legal reference (no duplicated "Fifth Schedule"). */
  legalChip: string;
  /** Current-year deduction decision. */
  currentYearLabel: string;
  currentYearOk: boolean;
  currentYearNote: string;
  /** Always "Carry-forward" for consistent hierarchy. */
  carryForwardHeading: string;
  /** Carry-forward decision (separate from current-year). */
  carryForwardLabel: string;
  carryForwardTone: CarryForwardTone;
  /** Short taxpayer-facing note; empty when the label is enough. */
  carryForwardNote: string;
  /** Detailed explanation for View legal basis. */
  whyAvailable: string;
  legalBasisCarryForwardDetail: string;
};

function qpLegalChip(field: FilingCatalogField): string {
  const para = (field.paragraph || "").trim();
  if (!para) return `Section ${field.section ?? "52"}`;
  if (/^fifth\s+sch/i.test(para) || /^section\b/i.test(para)) return para;
  return `Fifth Schedule ${para}`;
}

function qpFieldLegalStatus(
  field: FilingCatalogField,
  assessmentYear: "2024_25" | "2025_26",
): QpFieldLegalStatus {
  const legalChip = qpLegalChip(field);
  const ya = yaLabel(assessmentYear);
  const filmIds = new Set([
    "qp_film_production",
    "qp_cinema_construction",
    "qp_cinema_upgrading",
  ]);
  const isReview = field.component_id === "qp_unclassified_review";
  const isBroughtForward = field.component_id === "qp_brought_forward";

  if (isReview) {
    return {
      legalChip,
      currentYearLabel: "Current-year qualifying payment — needs classification",
      currentYearOk: false,
      currentYearNote:
        "This amount is not auto-deducted until it is matched to an applicable Fifth Schedule provision.",
      carryForwardHeading: "Carry-forward",
      carryForwardLabel: "— Not available",
      carryForwardTone: "not_available",
      carryForwardNote: "",
      whyAvailable:
        "This review field exists so unclassified amounts are captured without inventing a legal category.",
      legalBasisCarryForwardDetail:
        "Carry-forward is unavailable until the payment is classified under an applicable Fifth Schedule provision.",
    };
  }

  if (isBroughtForward) {
    return {
      legalChip,
      currentYearLabel: "Prior-year amount (input)",
      currentYearOk: true,
      currentYearNote:
        "Enter undeducted amounts previously carried under Sec 52(4) (1(b)(i) and 1(b)(v) only).",
      carryForwardHeading: "Carry-forward",
      carryForwardLabel: "Prior-year Sec 52(4) input",
      carryForwardTone: "eligible",
      carryForwardNote: "",
      whyAvailable:
        "Sec 52(4) lets certain undeducted qualifying payments from a prior year be brought forward into YA 2025/26.",
      legalBasisCarryForwardDetail:
        "This field records amounts previously carried under Sec 52(4) for use in the current year of assessment.",
    };
  }

  if (filmIds.has(field.component_id)) {
    return {
      legalChip,
      currentYearLabel: "Current-year qualifying payment",
      currentYearOk: true,
      currentYearNote:
        "May qualify as a qualifying payment this year under Fifth Schedule 1(f), subject to the applicable limits.",
      carryForwardHeading: "Carry-forward",
      carryForwardLabel: "Schedule 1(f) treatment",
      carryForwardTone: "schedule",
      carryForwardNote:
        "Film/cinema payments are subject to the special Schedule 1(f) treatment rather than the Sec 52(4) carry-forward.",
      whyAvailable: `This payment is listed under ${legalChip}.`,
      legalBasisCarryForwardDetail:
        "Film/cinema payments follow Fifth Schedule 1(f). Unused amounts under that schedule are not carried forward under Sec 52(4).",
    };
  }

  const currentYearNote =
    "May qualify as a qualifying payment this year, subject to the applicable Sec 52 / Fifth Schedule limits.";

  if (assessmentYear !== "2025_26") {
    return {
      legalChip,
      currentYearLabel: "Current-year qualifying payment",
      currentYearOk: true,
      currentYearNote,
      carryForwardHeading: "Carry-forward",
      carryForwardLabel: `— Not applicable for ${ya}`,
      carryForwardTone: "na",
      carryForwardNote: "",
      whyAvailable: `This payment is listed under ${legalChip}.`,
      legalBasisCarryForwardDetail:
        "Sec 52(4) carry-forward applies only for years of assessment commencing on or after 1 April 2025 (YA 2025/26). For this assessment year the payment may still qualify as a current-year deduction, subject to limits.",
    };
  }

  if (field.sec52_4_carry_forward) {
    return {
      legalChip,
      currentYearLabel: "Current-year qualifying payment",
      currentYearOk: true,
      currentYearNote,
      carryForwardHeading: "Carry-forward",
      carryForwardLabel: "✓ Eligible under Sec 52(4)",
      carryForwardTone: "eligible",
      carryForwardNote: "",
      whyAvailable: `This payment is listed under ${legalChip}.`,
      legalBasisCarryForwardDetail:
        "Unused eligible amounts may be carried forward under Sec 52(4), subject to the Act.",
    };
  }

  return {
    legalChip,
    currentYearLabel: "Current-year qualifying payment",
    currentYearOk: true,
    currentYearNote,
    carryForwardHeading: "Carry-forward",
    carryForwardLabel: "— Not available",
    carryForwardTone: "not_available",
    carryForwardNote: "",
    whyAvailable: `This payment is listed under ${legalChip}.`,
    legalBasisCarryForwardDetail:
      "This payment may qualify for deduction in the current year, subject to the applicable limits. Unused amounts cannot be carried forward under Sec 52(4).",
  };
}

/** Status color only: green = positive; amber = attention; neutral otherwise. */
function statusPositiveClass(): string {
  return "font-medium text-emerald-800 dark:text-emerald-300";
}

function statusAttentionClass(): string {
  return "font-medium text-amber-800 dark:text-amber-300";
}

function statusNeutralClass(): string {
  return "font-medium text-foreground";
}

function carryForwardValueClass(tone: CarryForwardTone): string {
  switch (tone) {
    case "eligible":
      return statusPositiveClass();
    case "not_available":
    case "na":
    case "schedule":
      return statusNeutralClass();
  }
}

function QpWhyPanel({
  field,
  assessmentYear,
  status,
}: {
  field: FilingCatalogField;
  assessmentYear: "2024_25" | "2025_26";
  status: QpFieldLegalStatus;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<FilingCatalogExplain | null>(null);
  const fetchGen = useRef(0);

  async function toggle(): Promise<void> {
    const next = !open;
    setOpen(next);
    if (!next || payload) return;
    const gen = ++fetchGen.current;
    setLoading(true);
    setError(null);
    try {
      const data = await getFilingCatalogExplain(field.component_id, assessmentYear);
      if (gen !== fetchGen.current) return;
      setPayload(data);
    } catch (err: unknown) {
      if (gen !== fetchGen.current) return;
      setError(err instanceof Error ? err.message : "Failed to load legal basis.");
    } finally {
      if (gen === fetchGen.current) setLoading(false);
    }
  }

  return (
    <div className="space-y-1">
      <button
        type="button"
        className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        onClick={() => void toggle()}
      >
        <Info className="h-3 w-3" aria-hidden />
        {open ? "Hide legal basis" : "View legal basis"}
      </button>
      {open ? (
        <div className="rounded border border-border bg-background/90 px-2.5 py-2 text-[11px] text-muted-foreground space-y-1.5">
          {loading ? <p>Loading Act evidence…</p> : null}
          {error ? <p className="text-destructive">{error}</p> : null}
          {payload ? (
            <>
              <p>
                <span className="font-medium text-foreground/80">
                  Why this field is available
                </span>
                <br />
                <span className="text-foreground">{status.whyAvailable}</span>
              </p>
              <p>
                <span className="font-medium text-foreground/80">Legal basis</span>
                <br />
                <span className="text-foreground">
                  {payload.paragraph
                    ? /^fifth\s+sch/i.test(payload.paragraph.trim())
                      ? payload.paragraph
                      : `Fifth Schedule ${payload.paragraph}`
                    : `Section ${payload.section ?? "52"}`}
                </span>
              </p>
              {payload.statutory_scope ? (
                <p>
                  <span className="font-medium text-foreground/80">Statutory scope</span>
                  <br />
                  <span className="text-foreground">{payload.statutory_scope}</span>
                </p>
              ) : null}
              <p>
                <span className="font-medium text-foreground/80">
                  Current-year treatment
                </span>
                <br />
                <span className="text-foreground">{status.currentYearNote}</span>
              </p>
              <p>
                <span className="font-medium text-foreground/80">
                  Carry-forward treatment
                </span>
                <br />
                <span className="text-foreground">
                  {status.carryForwardLabel.replace(/^✓\s*/, "").replace(/^—\s*/, "")}
                </span>
                <br />
                <span className="text-foreground">
                  {status.legalBasisCarryForwardDetail}
                </span>
                {payload.sec52_4_status ? (
                  <>
                    <br />
                    <span className="text-muted-foreground">
                      Sec 52(4) basis: {payload.sec52_4_status}
                    </span>
                  </>
                ) : null}
              </p>
              <p>
                <span className="font-medium text-foreground/80">Assessment year</span>
                <br />
                <span className="text-foreground">
                  {yaLabel(payload.assessment_year ?? assessmentYear)}
                </span>
              </p>
              <p>
                <span className="font-medium text-foreground/80">Source</span>
                <br />
                <span className="text-foreground">
                  {payload.source_label ?? payload.source_doc_id ?? "—"}
                </span>
              </p>
              {payload.source_quote ? (
                <p>
                  <span className="font-medium text-foreground/80">Evidence</span>
                  <br />
                  <span className="text-foreground italic">
                    &ldquo;{payload.source_quote}&rdquo;
                  </span>
                </p>
              ) : null}
              <p>
                <span className="font-medium text-foreground/80">Confidence</span>
                <br />
                <span className="text-foreground">
                  {payload.legal_confidence}
                  {payload.confidence_reason
                    ? ` — ${payload.confidence_reason}`
                    : ""}
                </span>
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function QualifyingPaymentsSection({
  card,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  totalValue,
  onTotalChange,
  open,
  onToggle,
  summary,
  categoryResults,
  assessmentYear,
  actVersionLabel,
}: {
  card?: FilingCatalogCard | null;
  mode: DeductionInputMode;
  onModeChange: (mode: DeductionInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  totalValue: string;
  onTotalChange: (value: string) => void;
  open: boolean;
  onToggle: () => void;
  summary?: QualifyingPaymentSummary | null;
  categoryResults?: QualifyingPaymentCategoryResult[];
  assessmentYear: "2024_25" | "2025_26";
  actVersionLabel?: string | null;
}) {
  const [filmOpen, setFilmOpen] = useState(true);
  const resultsById = useMemo(() => {
    const map = new Map<string, QualifyingPaymentCategoryResult>();
    for (const row of categoryResults ?? []) {
      map.set(row.component_id, row);
    }
    return map;
  }, [categoryResults]);

  const groups = useMemo(() => {
    const order = ["donations", "special", "film_cinema", "carry_forward", "review"];
    const labels: Record<string, string> = {
      donations: "Donations",
      special: "Special qualifying payments",
      film_cinema: "Film production / cinema-related",
      carry_forward: "Brought forward",
      review: "Requires review",
    };
    const bucket = new Map<string, FilingCatalogField[]>();
    for (const field of fields) {
      if (field.status === "pending_unsupported" || field.engine_support === "unsupported") {
        continue;
      }
      const key = field.ui_group || "other";
      const list = bucket.get(key) ?? [];
      list.push(field);
      bucket.set(key, list);
    }
    return order
      .filter((key) => (bucket.get(key)?.length ?? 0) > 0)
      .map((key) => ({
        key,
        label: labels[key] ?? key,
        fields: (bucket.get(key) ?? []).sort((a, b) => a.sort_order - b.sort_order),
      }));
  }, [fields]);

  const claimedPreview = useMemo(() => {
    return fields.reduce((sum, field) => {
      if (field.component_id === "qp_unclassified_review") return sum;
      if (field.default_treatment === "deduct") {
        return sum + parseLkr(amounts[field.component_id] ?? "0");
      }
      return sum;
    }, 0);
  }, [fields, amounts]);

  function switchMode(next: DeductionInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "components") onTotalChange("0");
  }

  function renderField(field: FilingCatalogField) {
    const result = resultsById.get(field.component_id);
    const isReview = field.component_id === "qp_unclassified_review";
    const status = qpFieldLegalStatus(field, assessmentYear);
    return (
      <div key={field.component_id} className="space-y-2 border-b border-border/60 pb-3 last:border-0">
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor={field.component_id} className="text-sm font-medium">
            {field.display_name}
          </Label>
          {isReview ? (
            <span className="text-[10px] text-amber-800 dark:text-amber-300">
              Needs legal classification
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center rounded border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {status.legalChip}
          </span>
          <span className="inline-flex items-center rounded border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {yaLabel(assessmentYear)}
          </span>
        </div>
        <div className="space-y-1 text-[11px]">
          <div className="space-y-0.5">
            <p className="text-muted-foreground">Current-year qualifying payment</p>
            <p
              className={
                status.currentYearOk ? statusPositiveClass() : statusAttentionClass()
              }
            >
              {status.currentYearOk
                ? field.component_id === "qp_brought_forward"
                  ? "✓ Prior-year amount (input)"
                  : "✓ Yes"
                : isReview
                  ? "— Needs classification before deduction"
                  : `— ${status.currentYearLabel}`}
            </p>
          </div>
          <div className="space-y-0.5">
            <p className="text-muted-foreground">{status.carryForwardHeading}</p>
            <p className={carryForwardValueClass(status.carryForwardTone)}>
              {status.carryForwardLabel}
            </p>
            {status.carryForwardNote ? (
              <p className="text-muted-foreground leading-snug">
                {status.carryForwardNote}
              </p>
            ) : null}
          </div>
        </div>
        <Input
          id={field.component_id}
          inputMode="numeric"
          value={formatMoneyInput(amounts[field.component_id] ?? "0")}
          onChange={(event) =>
            onAmountChange(field.component_id, formatMoneyInput(event.target.value))
          }
          placeholder="0"
        />
        <QpWhyPanel
          key={`${field.component_id}:${assessmentYear}`}
          field={field}
          assessmentYear={assessmentYear}
          status={status}
        />
        {isReview ? (
          <p className="text-[11px] text-muted-foreground leading-snug">
            This amount is held for review and is not auto-deducted until it is matched
            to an applicable Fifth Schedule provision.
          </p>
        ) : null}
        {result && parseLkr(result.claimed) > 0 ? (
          <div className="rounded border border-border bg-muted/30 px-2 py-1.5 text-[11px] text-muted-foreground space-y-0.5">
            <p>
              Claimed:{" "}
              <span className="text-foreground">
                {formatLkr(result.claimed_amount ?? result.claimed)}
              </span>
            </p>
            <p>
              Allowable:{" "}
              <span className="text-foreground">
                {formatLkr(result.allowable_amount ?? result.allowable)}
              </span>
            </p>
            <p>
              Deducted this year:{" "}
              <span className="text-foreground">
                {formatLkr(result.deducted_this_year ?? "0")}
              </span>
            </p>
            <p>
              Undeducted:{" "}
              <span className="text-foreground">
                {formatLkr(result.undeducted_amount ?? "0")}
              </span>
            </p>
            <p>
              Carry-forward:{" "}
              <span className="text-foreground">
                {result.carry_forward_basis === "fifth_sch_1f"
                  ? "Schedule 1(f) treatment"
                  : result.sec52_4_eligible
                    ? "Eligible under Sec 52(4)"
                    : "Not available"}
              </span>
            </p>
            <p>
              Carry-forward amount:{" "}
              <span className="text-foreground">
                {formatLkr(result.carry_forward_amount ?? "0")}
              </span>
            </p>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <CatalogCardShell
      card={card}
      title="Qualifying Payments"
      subtitle="Sec 52 / Fifth Schedule — per-category validation then aggregate limitation."
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
              Single total (legacy)
            </Button>
          </div>

          {mode === "total" ? (
            <div className="space-y-2">
              <MoneyField
                id="qp-legacy-total"
                label="Simplified / legacy aggregate (no Fifth Schedule category)"
                value={totalValue}
                onChange={onTotalChange}
              />
              <p className="text-[11px] text-amber-800 dark:text-amber-300">
                Entering a single total does not identify the underlying Fifth Schedule
                category. For full legal validation and explainability, use Components.
              </p>
            </div>
          ) : fields.length === 0 ? (
            <p className="text-xs text-muted-foreground">Loading catalog fields…</p>
          ) : (
            <div className="space-y-4">
              {groups.map((group) => {
                if (group.key === "film_cinema") {
                  return (
                    <div key={group.key} className="space-y-2">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"
                        onClick={() => setFilmOpen((v) => !v)}
                      >
                        <span>{group.label}</span>
                        {filmOpen ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </button>
                      {filmOpen ? (
                        <div className="space-y-3">{group.fields.map(renderField)}</div>
                      ) : null}
                    </div>
                  );
                }
                return (
                  <div key={group.key} className="space-y-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {group.label}
                    </p>
                    {group.fields.map(renderField)}
                  </div>
                );
              })}

              <div className="rounded border bg-background/70 px-3 py-2 text-xs text-muted-foreground">
                <p>
                  Claimed preview (typed lines):{" "}
                  <span className="font-medium text-foreground">
                    {formatLkr(String(claimedPreview))}
                  </span>
                </p>
                <div className="mt-2 space-y-1 border-t border-border/50 pt-2">
                  <p>
                    Carry-forward under Sec 52(4):{" "}
                    <span className="font-medium text-foreground">
                      {assessmentYear !== "2025_26"
                        ? "Not applicable for this assessment year"
                        : summary?.carry_forward_out
                          ? formatLkr(summary.carry_forward_out)
                          : summary
                            ? formatLkr("0")
                            : "Calculate to see eligible amount"}
                    </span>
                  </p>
                  {summary ? (
                    <>
                      <p>
                        Total claimed:{" "}
                        <span className="text-foreground">
                          {formatLkr(summary.total_claimed)}
                        </span>
                      </p>
                      <p>
                        Allowable before Sec 52 limit:{" "}
                        <span className="text-foreground">
                          {formatLkr(summary.total_allowable_before_sec52)}
                        </span>
                      </p>
                      <p>
                        Section 52 limitation:{" "}
                        <span className="text-foreground">
                          {summary.section_52_cap
                            ? formatLkr(summary.section_52_cap)
                            : "—"}
                        </span>
                      </p>
                      <p>
                        Final qualifying-payment deduction:{" "}
                        <span className="font-medium text-foreground">
                          {formatLkr(summary.final_allowable_deduction)}
                        </span>
                      </p>
                      {summary.unused_after_sec52 ? (
                        <p>
                          Unused absolute-cap room (informational, not CF):{" "}
                          <span className="text-foreground">
                            {formatLkr(summary.unused_after_sec52)}
                          </span>
                        </p>
                      ) : null}
                      {assessmentYear === "2025_26" &&
                      summary.carry_forward_not_eligible &&
                      parseLkr(summary.carry_forward_not_eligible) > 0 ? (
                        <p>
                          Carry-forward not eligible (other categories):{" "}
                          <span className="text-foreground">
                            {formatLkr(summary.carry_forward_not_eligible)}
                          </span>
                        </p>
                      ) : null}
                      {summary.total_needs_review &&
                      parseLkr(summary.total_needs_review) > 0 ? (
                        <p>
                          Needs review (not deducted):{" "}
                          <span className="text-foreground">
                            {formatLkr(summary.total_needs_review)}
                          </span>
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <p className="mt-1">
                      Calculate to see category-level allowable amounts and the Sec 52
                      aggregate limitation.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
    </CatalogCardShell>
  );
}

function DeductionCardSection({
  card,
  title,
  subtitle,
  mode,
  onModeChange,
  fields,
  amounts,
  onAmountChange,
  totalLabel,
  totalValue,
  onTotalChange,
  open,
  onToggle,
  provenanceNote,
  actVersionLabel,
  onExplainField,
  componentsOnly = false,
}: {
  card?: FilingCatalogCard | null;
  title: string;
  subtitle: string;
  mode: DeductionInputMode;
  onModeChange: (mode: DeductionInputMode) => void;
  fields: FilingCatalogField[];
  amounts: Record<string, string>;
  onAmountChange: (componentId: string, value: string) => void;
  totalLabel: string;
  totalValue: string;
  onTotalChange: (value: string) => void;
  open: boolean;
  onToggle: () => void;
  provenanceNote?: string;
  actVersionLabel?: string | null;
  onExplainField: (field: FilingCatalogField) => void;
  componentsOnly?: boolean;
}) {
  const claimed = useMemo(() => {
    return fields.reduce((sum, field) => {
      if (field.default_treatment === "deduct" || field.default_treatment === "credit") {
        return sum + parseLkr(amounts[field.component_id] ?? "0");
      }
      return sum;
    }, 0);
  }, [fields, amounts]);

  function switchMode(next: DeductionInputMode): void {
    if (next === mode) return;
    onModeChange(next);
    if (next === "components") onTotalChange("0");
  }

  return (
    <CatalogCardShell
      card={card}
      title={title}
      subtitle={subtitle}
      actVersionLabel={actVersionLabel}
      fieldCount={fields.length}
      open={open}
      onToggle={onToggle}
    >
      <div className="space-y-3">
          {componentsOnly ? null : (
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
          )}

          {!componentsOnly && mode === "total" ? (
            <MoneyField
              id={`${title}-total`}
              label={totalLabel}
              value={totalValue}
              onChange={onTotalChange}
            />
          ) : fields.length === 0 ? (
            <p className="text-xs text-muted-foreground">Loading catalog fields…</p>
          ) : (
            <div className="space-y-3">
              <CatalogMoneyFields
                fields={fields}
                amounts={amounts}
                onAmountChange={onAmountChange}
                treatmentLabel={(field) =>
                  field.default_treatment === "credit" ? "credit" : "deduct"
                }
                actVersionLabel={actVersionLabel}
                onExplainField={onExplainField}
              />
              <p className="text-xs text-muted-foreground">
                Claimed subtotal (client preview):{" "}
                <span className="font-medium text-foreground">
                  {formatLkr(String(claimed))}
                </span>
                {" "}— Rule Engine applies Fifth Schedule / Sec 52 caps with Act provenance.
              </p>
              {provenanceNote ? (
                <p className="text-[11px] text-muted-foreground">{provenanceNote}</p>
              ) : null}
            </div>
          )}
        </div>
    </CatalogCardShell>
  );
}

export function AdaptiveTaxCalculatorPage() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [businessInputMode, setBusinessInputMode] =
    useState<BusinessInputMode>("net");
  const [businessOpen, setBusinessOpen] = useState(true);
  const [businessCard, setBusinessCard] = useState<FilingCatalogCard | null>(null);
  const [businessAmounts, setBusinessAmounts] = useState<Record<string, string>>({});
  const [employmentMode, setEmploymentMode] =
    useState<EmploymentInputMode>("components");
  const [employmentOpen, setEmploymentOpen] = useState(true);
  const [employmentCard, setEmploymentCard] = useState<FilingCatalogCard | null>(null);
  const [employmentAmounts, setEmploymentAmounts] = useState<Record<string, string>>({});
  const [investmentMode, setInvestmentMode] =
    useState<InvestmentInputMode>("components");
  const [investmentOpen, setInvestmentOpen] = useState(false);
  const [investmentCard, setInvestmentCard] = useState<FilingCatalogCard | null>(null);
  const [investmentAmounts, setInvestmentAmounts] = useState<Record<string, string>>({});
  const [otherMode, setOtherMode] = useState<OtherInputMode>("components");
  const [otherOpen, setOtherOpen] = useState(false);
  const [otherCard, setOtherCard] = useState<FilingCatalogCard | null>(null);
  const [otherAmounts, setOtherAmounts] = useState<Record<string, string>>({});
  const [otherCustomRows, setOtherCustomRows] = useState<OtherCustomRow[]>([]);
  const [qpMode, setQpMode] = useState<DeductionInputMode>("components");
  const [qpOpen, setQpOpen] = useState(false);
  const [qpCard, setQpCard] = useState<FilingCatalogCard | null>(null);
  const [qpAmounts, setQpAmounts] = useState<Record<string, string>>({});
  const [statutoryOpen, setStatutoryOpen] = useState(false);
  const [statutoryCard, setStatutoryCard] = useState<FilingCatalogCard | null>(null);
  const [statutoryAmounts, setStatutoryAmounts] = useState<Record<string, string>>({});
  const [creditMode, setCreditMode] = useState<DeductionInputMode>("components");
  const [creditOpen, setCreditOpen] = useState(false);
  const [creditCard, setCreditCard] = useState<FilingCatalogCard | null>(null);
  const [creditAmounts, setCreditAmounts] = useState<Record<string, string>>({});
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogPreviewVersions, setCatalogPreviewVersions] =
    useState<KnowledgeVersions | null>(null);
  const [actVersionLabel, setActVersionLabel] = useState<string | null>(null);
  const [explainField, setExplainField] = useState<FilingCatalogField | null>(null);
  const [result, setResult] = useState<CalculateTaxResponse | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getFilingCatalog(form.assessment_year)
      .then((catalog) => {
        if (cancelled) return;
        setCatalogError(null);
        setCatalogPreviewVersions({
          act_version: catalog.act_version ?? undefined,
          act_version_label: catalog.act_version_label ?? undefined,
          catalog_version: catalog.catalog_version,
          rule_pack_version: `${catalog.assessment_year}.current`,
          knowledge_graph_version: catalog.knowledge_graph_version ?? undefined,
          extraction_version: catalog.extraction_version ?? undefined,
        });
        setActVersionLabel(catalog.act_version_label ?? null);
        const empCard = catalog.cards.find((c) => c.card_id === "employment") ?? null;
        const bizCard = catalog.cards.find((c) => c.card_id === "business") ?? null;
        const invCard = catalog.cards.find((c) => c.card_id === "investment") ?? null;
        const otherCat = catalog.cards.find((c) => c.card_id === "other_income") ?? null;
        const qpCat = catalog.cards.find((c) => c.card_id === "qualifying_payments") ?? null;
        const statutoryCat = catalog.cards.find((c) => c.card_id === "statutory_reliefs") ?? null;
        const credCat = catalog.cards.find((c) => c.card_id === "tax_credits") ?? null;
        setEmploymentCard(empCard);
        setBusinessCard(bizCard);
        setInvestmentCard(invCard);
        setOtherCard(otherCat);
        setQpCard(qpCat);
        setStatutoryCard(statutoryCat);
        setCreditCard(credCat);
        setEmploymentAmounts((prev) => {
          const next: Record<string, string> = {};
          for (const field of empCard?.fields ?? []) {
            next[field.component_id] = prev[field.component_id] ?? "0";
          }
          // Sensible demo defaults matching ex18 when first load.
          if (
            Object.values(next).every((v) => parseLkr(v) === 0) &&
            next.emp_salary !== undefined
          ) {
            next.emp_salary = "1600000";
            if (next.emp_bonus !== undefined) next.emp_bonus = "200000";
          }
          return next;
        });
        const seedAmounts = (
          card: FilingCatalogCard | null,
          prev: Record<string, string>,
        ) => {
          const next: Record<string, string> = {};
          for (const field of card?.fields ?? []) {
            next[field.component_id] = prev[field.component_id] ?? "0";
          }
          return next;
        };
        setInvestmentAmounts((prev) => seedAmounts(invCard, prev));
        setOtherAmounts((prev) => seedAmounts(otherCat, prev));
        setBusinessAmounts((prev) => seedAmounts(bizCard, prev));
        setQpAmounts((prev) => seedAmounts(qpCat, prev));
        setStatutoryAmounts((prev) => seedAmounts(statutoryCat, prev));
        setCreditAmounts((prev) => seedAmounts(credCat, prev));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setCatalogError(
          err instanceof Error ? err.message : "Failed to load filing catalog.",
        );
        setEmploymentMode("total");
        setInvestmentMode("total");
        setOtherMode("total");
        setQpMode("total");
        setCreditMode("total");
      });
    return () => {
      cancelled = true;
    };
  }, [form.assessment_year]);

  function patch<K extends keyof FormState>(key: K, value: FormState[K]): void {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function openFieldExplain(field: FilingCatalogField): void {
    setExplainField(field);
  }

  function patchEmploymentAmount(componentId: string, value: string): void {
    setEmploymentAmounts((prev) => ({ ...prev, [componentId]: value }));
  }

  function patchInvestmentAmount(componentId: string, value: string): void {
    setInvestmentAmounts((prev) => ({ ...prev, [componentId]: value }));
  }

  function linesFromAmounts(
    mode: DeductionInputMode | InvestmentInputMode | EmploymentInputMode,
    amounts: Record<string, string>,
  ): FilingLine[] {
    if (mode !== "components") return [];
    return Object.entries(amounts)
      .filter(([, amount]) => parseLkr(amount) > 0)
      .map(([component_id, amount]) => ({
        component_id,
        amount: toMoneyWire(amount),
      }));
  }

  function businessFilingLines(): FilingLine[] {
    if (!businessCard?.fields.length) return [];
    const allowed =
      businessInputMode === "net"
        ? new Set(
            businessCard.fields
              .filter((f) => f.ui_group === "net")
              .map((f) => f.component_id),
          )
        : new Set(
            businessCard.fields
              .filter((f) => f.ui_group === "breakdown")
              .map((f) => f.component_id),
          );
    return Object.entries(businessAmounts)
      .filter(([id, amount]) => allowed.has(id) && parseLkr(amount) > 0)
      .map(([component_id, amount]) => ({
        component_id,
        amount: toMoneyWire(amount),
      }));
  }

  function otherFilingLines(): FilingLine[] {
    if (otherMode !== "components") return [];
    const lines: FilingLine[] = [];
    const residual = parseLkr(otherAmounts.oth_residual ?? "0");
    if (residual > 0) {
      lines.push({
        component_id: "oth_residual",
        amount: toMoneyWire(otherAmounts.oth_residual ?? "0"),
      });
    }
    for (const row of otherCustomRows) {
      if (parseLkr(row.amount) <= 0) continue;
      lines.push({
        component_id: "oth_custom",
        amount: toMoneyWire(row.amount),
        label_override: row.label.trim() || undefined,
      });
    }
    const fwh = parseLkr(otherAmounts.oth_final_withholding ?? "0");
    if (fwh > 0) {
      lines.push({
        component_id: "oth_final_withholding",
        amount: toMoneyWire(otherAmounts.oth_final_withholding ?? "0"),
      });
    }
    return lines;
  }

  function buildTestDataContext(): CalculatorTestDataContext {
    return {
      resident_status: form.resident_status,
      employmentFieldIds: employmentCard?.fields.map((f) => f.component_id) ?? [],
      businessFieldIds: businessCard?.fields.map((f) => f.component_id) ?? [],
      investmentFieldIds: investmentCard?.fields.map((f) => f.component_id) ?? [],
      otherFieldIds: otherCard?.fields.map((f) => f.component_id) ?? [],
      qpFieldIds: qpCard?.fields.map((f) => f.component_id) ?? [],
      statutoryFieldIds: statutoryCard?.fields.map((f) => f.component_id) ?? [],
      creditFieldIds: creditCard?.fields.map((f) => f.component_id) ?? [],
    };
  }

  function handleFillTestData(): void {
    const patch = buildFillTestDataPatch(buildTestDataContext());
    setEmploymentMode(patch.modes.employmentMode);
    setBusinessInputMode(patch.modes.businessInputMode);
    setInvestmentMode(patch.modes.investmentMode);
    setOtherMode(patch.modes.otherMode);
    setQpMode(patch.modes.qpMode);
    setCreditMode(patch.modes.creditMode);
    setEmploymentAmounts((prev) => ({ ...prev, ...patch.employmentAmounts }));
    setBusinessAmounts((prev) => ({ ...prev, ...patch.businessAmounts }));
    setInvestmentAmounts((prev) => ({ ...prev, ...patch.investmentAmounts }));
    setOtherAmounts((prev) => ({ ...prev, ...patch.otherAmounts }));
    setQpAmounts((prev) => ({ ...prev, ...patch.qpAmounts }));
    setStatutoryAmounts((prev) => ({ ...prev, ...patch.statutoryAmounts }));
    setCreditAmounts((prev) => ({ ...prev, ...patch.creditAmounts }));
  }

  function handleClearTestData(): void {
    const patch = buildClearTestDataPatch(buildTestDataContext());
    setForm((prev) => ({ ...prev, ...patch.formScalars }));
    setEmploymentAmounts((prev) => ({ ...prev, ...patch.employmentAmounts }));
    setBusinessAmounts((prev) => ({ ...prev, ...patch.businessAmounts }));
    setInvestmentAmounts((prev) => ({ ...prev, ...patch.investmentAmounts }));
    setOtherAmounts((prev) => ({ ...prev, ...patch.otherAmounts }));
    setQpAmounts((prev) => ({ ...prev, ...patch.qpAmounts }));
    setStatutoryAmounts((prev) => ({ ...prev, ...patch.statutoryAmounts }));
    setCreditAmounts((prev) => ({ ...prev, ...patch.creditAmounts }));
    setOtherCustomRows(patch.otherCustomRows);
  }

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setIsCalculating(true);
    setError(null);
    try {
      const bizLines = businessFilingLines();
      const useBizCatalog = bizLines.length > 0 || Boolean(businessCard?.fields.length);
      const filingLines: FilingLine[] = [
        ...linesFromAmounts(employmentMode, employmentAmounts),
        ...bizLines,
        ...linesFromAmounts(investmentMode, investmentAmounts),
        ...otherFilingLines(),
        ...linesFromAmounts(qpMode, qpAmounts),
        ...linesFromAmounts("components", statutoryAmounts).filter(
          (line) =>
            form.resident_status === "resident" ||
            line.component_id !== "relief_solar_panel",
        ),
        ...linesFromAmounts(creditMode, creditAmounts),
      ];

      const body: CalculateTaxRequest = {
        assessment_year: form.assessment_year,
        resident_status: form.resident_status,
        param_set: "current",
        employment_income:
          employmentMode === "components" ? "0" : toMoneyWire(form.employment_income),
        employment_final_withholding:
          employmentMode === "components"
            ? "0"
            : toMoneyWire(form.employment_final_withholding),
        business_income:
          useBizCatalog || businessInputMode === "breakdown"
            ? "0"
            : toMoneyWire(form.business_income),
        business_gross:
          useBizCatalog || businessInputMode === "net"
            ? "0"
            : toMoneyWire(form.business_gross),
        business_deductions:
          useBizCatalog || businessInputMode === "net"
            ? "0"
            : toMoneyWire(form.business_deductions),
        capital_allowances:
          useBizCatalog || businessInputMode === "net"
            ? "0"
            : toMoneyWire(form.capital_allowances),
        investment_income:
          investmentMode === "components" ? "0" : toMoneyWire(form.investment_income),
        investment_final_withholding:
          investmentMode === "components"
            ? "0"
            : toMoneyWire(form.investment_final_withholding),
        other_income:
          otherMode === "components" ? "0" : toMoneyWire(form.other_income),
        other_final_withholding:
          otherMode === "components"
            ? "0"
            : toMoneyWire(form.other_final_withholding),
        qualifying_payments:
          qpMode === "components" ? "0" : toMoneyWire(form.qualifying_payments),
        donations: "0",
        apit_already_paid:
          creditMode === "components" ? "0" : toMoneyWire(form.apit_already_paid),
        other_reliefs: {},
        ...(filingLines.length > 0 ? { filing_lines: filingLines } : {}),
      };
      const resp = await calculateTax(body);
      setResult(resp);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Calculation failed.");
    } finally {
      setIsCalculating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tax calculator</h1>
        <p className="text-muted-foreground">
          Pure-Python rule engine — KG + param JSON, no GPT. Assessment year selects
          that year's rates and Sec 52 cap (2024/25 = 1.2M, 2025/26 = 1.8M).
        </p>
      </div>

      <CalculatedUsingStrip
        versions={result?.knowledge_versions ?? catalogPreviewVersions}
        sticky={Boolean(result)}
      />
      <UnresolvedClaimsBanner claims={result?.unresolved_claims ?? []} />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Inputs</CardTitle>
          <CardDescription>
            Amounts are annual LKR. Personal relief applies to residents only.
            Assessment year selects that year's rates and Sec 52 cap (
            {sec52CapLabel(form.assessment_year)}).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="assessment_year">Assessment year</Label>
                <Select
                  id="assessment_year"
                  value={form.assessment_year}
                  onChange={(event) => {
                    patch(
                      "assessment_year",
                      event.target.value as FormState["assessment_year"],
                    );
                    setResult(null);
                    setCatalogError(null);
                    setError(null);
                  }}
                >
                  <option value="2024_25">2024/25 (Sec 52 cap 1.2M)</option>
                  <option value="2025_26">2025/26 (Sec 52 cap 1.8M)</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="resident_status">Resident status</Label>
                <Select
                  id="resident_status"
                  value={form.resident_status}
                  onChange={(event) =>
                    patch("resident_status", event.target.value as FormState["resident_status"])
                  }
                >
                  <option value="resident">Resident</option>
                  <option value="non_resident">Non-resident</option>
                </Select>
              </div>
            </div>

            <div className="space-y-4">
              <CalculatorGroupHead
                title="Income heads"
                description="Catalog cards for Sections 5–8 — assessable income components."
              />
              <div className="space-y-3">
            <EmploymentIncomeSection
              card={employmentCard}
              mode={employmentMode}
              onModeChange={setEmploymentMode}
              fields={employmentCard?.fields ?? []}
              amounts={employmentAmounts}
              onAmountChange={patchEmploymentAmount}
              form={form}
              onPatch={patch}
              open={employmentOpen}
              onToggle={() => setEmploymentOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
            />
            {catalogError ? (
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Catalog unavailable ({catalogError}). Using single-total income inputs.
              </p>
            ) : null}

            <BusinessIncomeSection
              card={businessCard}
              mode={businessInputMode}
              onModeChange={setBusinessInputMode}
              fields={businessCard?.fields ?? []}
              amounts={businessAmounts}
              onAmountChange={(id, v) =>
                setBusinessAmounts((prev) => ({ ...prev, [id]: v }))
              }
              form={form}
              onPatch={patch}
              open={businessOpen}
              onToggle={() => setBusinessOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
            />

            <InvestmentIncomeSection
              card={investmentCard}
              mode={investmentMode}
              onModeChange={setInvestmentMode}
              fields={investmentCard?.fields ?? []}
              amounts={investmentAmounts}
              onAmountChange={patchInvestmentAmount}
              form={form}
              onPatch={patch}
              open={investmentOpen}
              onToggle={() => setInvestmentOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
            />

            <OtherIncomeSection
              card={otherCard}
              mode={otherMode}
              onModeChange={setOtherMode}
              fields={otherCard?.fields ?? []}
              amounts={otherAmounts}
              onAmountChange={(id, v) =>
                setOtherAmounts((prev) => ({ ...prev, [id]: v }))
              }
              customRows={otherCustomRows}
              onCustomRowsChange={setOtherCustomRows}
              form={form}
              onPatch={patch}
              open={otherOpen}
              onToggle={() => setOtherOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
            />
              </div>
            </div>

            <div className="space-y-4">
              <CalculatorGroupHead
                title="Deductions & credits"
                description="Sec 52 qualifying payments, Fifth Schedule paragraph 2 reliefs, and Sec 89 tax credits."
              />
              <div className="space-y-3">
            <QualifyingPaymentsSection
              card={qpCard}
              mode={qpMode}
              onModeChange={setQpMode}
              fields={qpCard?.fields ?? []}
              amounts={qpAmounts}
              onAmountChange={(id, v) => setQpAmounts((prev) => ({ ...prev, [id]: v }))}
              totalValue={form.qualifying_payments}
              onTotalChange={(v) => patch("qualifying_payments", v)}
              open={qpOpen}
              onToggle={() => setQpOpen((v) => !v)}
              summary={result?.qualifying_payment_summary}
              categoryResults={result?.qualifying_payment_categories}
              assessmentYear={form.assessment_year}
              actVersionLabel={actVersionLabel}
            />

            <DeductionCardSection
              card={statutoryCard}
              title="Statutory reliefs"
              subtitle="Fifth Sch paragraph 2 — not qualifying payments. 2(g) solar (resident, cap Rs 600,000 both YAs) and 2(c) rent (25% of included inv_rents). Put FWH-excluded rent on inv_final_withholding, not also on inv_rents. 2(f) sunset items are not offered."
              mode="components"
              onModeChange={() => undefined}
              fields={(statutoryCard?.fields ?? []).filter(
                (f) =>
                  form.resident_status === "resident" ||
                  f.component_id !== "relief_solar_panel",
              )}
              amounts={statutoryAmounts}
              onAmountChange={(id, v) =>
                setStatutoryAmounts((prev) => ({ ...prev, [id]: v }))
              }
              totalLabel="Statutory reliefs"
              totalValue="0"
              onTotalChange={() => undefined}
              open={statutoryOpen}
              onToggle={() => setStatutoryOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
              componentsOnly
            />

            <DeductionCardSection
              card={creditCard}
              title="Tax Credits"
              subtitle="Sec 89 — APIT / non-final withholding already paid (credits gross liability only)."
              mode={creditMode}
              onModeChange={setCreditMode}
              fields={creditCard?.fields ?? []}
              amounts={creditAmounts}
              onAmountChange={(id, v) =>
                setCreditAmounts((prev) => ({ ...prev, [id]: v }))
              }
              totalLabel="APIT already paid"
              totalValue={form.apit_already_paid}
              onTotalChange={(v) => patch("apit_already_paid", v)}
              open={creditOpen}
              onToggle={() => setCreditOpen((v) => !v)}
              actVersionLabel={actVersionLabel}
              onExplainField={openFieldExplain}
            />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={isCalculating}>
                {isCalculating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Calculator className="h-4 w-4" />
                )}
                Calculate
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={isCalculating}
                onClick={() => {
                  setForm(INITIAL);
                  setBusinessInputMode("net");
                  setBusinessAmounts({});
                  setEmploymentMode("components");
                  setEmploymentOpen(true);
                  setInvestmentMode("components");
                  setInvestmentOpen(false);
                  setOtherMode("components");
                  setOtherOpen(false);
                  setOtherCustomRows([]);
                  setEmploymentAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    if (next.emp_salary !== undefined) next.emp_salary = "1600000";
                    if (next.emp_bonus !== undefined) next.emp_bonus = "200000";
                    return next;
                  });
                  setInvestmentAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    return next;
                  });
                  setOtherAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    return next;
                  });
                  setQpAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    return next;
                  });
                  setStatutoryAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    return next;
                  });
                  setCreditAmounts((prev) => {
                    const next: Record<string, string> = {};
                    for (const key of Object.keys(prev)) next[key] = "0";
                    return next;
                  });
                  setResult(null);
                  setError(null);
                }}
              >
                Reset (ex18)
              </Button>
              {import.meta.env.DEV ? (
                <>
                  <Button
                    type="button"
                    variant="secondary"
                    className="border-dashed text-muted-foreground"
                    disabled={isCalculating}
                    onClick={handleFillTestData}
                  >
                    Fill test data
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    className="border-dashed text-muted-foreground"
                    disabled={isCalculating}
                    onClick={handleClearTestData}
                  >
                    Clear test data
                  </Button>
                </>
              ) : null}
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </form>
        </CardContent>
      </Card>

      {result ? (
        <>
          <TaxpayerResultSummary
            result={result}
            assessmentYear={form.assessment_year}
            calcId={result.calc_id}
          />

          <details className="rounded-xl border bg-card text-card-foreground shadow">
            <summary className="cursor-pointer px-6 py-4 text-sm font-medium">
              Technical details
            </summary>
            <Card className="border-0 shadow-none">
            <CardHeader>
              <CardTitle className="text-lg">Calculation trace</CardTitle>
              <CardDescription>
                Ordered steps with formulas, outputs, and concept / section anchors.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Step</th>
                    <th className="py-2 pr-3 font-medium">Formula</th>
                    <th className="py-2 pr-3 font-medium">Output</th>
                    <th className="py-2 pr-3 font-medium">Concepts / sections</th>
                    <th className="py-2 font-medium">Rule sources</th>
                  </tr>
                </thead>
                <tbody>
                  {result.calculation_trace.map((step) => (
                    <tr key={step.step_id} className="border-b align-top last:border-0">
                      <td className="py-3 pr-3">
                        <div className="font-medium">{step.step_id}</div>
                        <div className="text-xs text-muted-foreground">
                          {step.description}
                        </div>
                      </td>
                      <td className="py-3 pr-3">
                        <code className="whitespace-pre-wrap text-xs">{step.formula}</code>
                      </td>
                      <td className="py-3 pr-3 whitespace-nowrap font-medium">
                        {/^-?\d+(\.\d+)?$/.test(step.output)
                          ? formatLkr(step.output)
                          : step.output}
                      </td>
                      <td className="py-3 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {step.concept_ids.map((id) => (
                            <Chip key={`c-${step.step_id}-${id}`}>{id}</Chip>
                          ))}
                          {step.section_uids.map((uid) => (
                            <Chip key={`s-${step.step_id}-${uid}`}>
                              {uid.split("::").slice(-1)[0] || uid}
                            </Chip>
                          ))}
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          {step.rule_source_ids.map((id) => (
                            <Chip key={`r-${step.step_id}-${id}`}>{id}</Chip>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
            </Card>
          </details>
        </>
      ) : null}

      <FieldExplainDrawer
        field={explainField}
        assessmentYear={form.assessment_year}
        actVersionLabel={actVersionLabel}
        open={explainField !== null}
        onClose={() => setExplainField(null)}
      />
    </div>
  );
}
