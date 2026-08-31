import { Info, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { formatMoneyInput } from "./format-lkr";
import type { IncomeCatalogField } from "./income-catalog";

function confidenceLabel(level: string): string {
  if (level === "high") return "High confidence";
  if (level === "medium") return "Medium confidence";
  if (level === "pending") return "Pending";
  return level;
}

function ConfidenceBadge({
  level,
  actLabel,
}: {
  level: string;
  actLabel?: string | null;
}) {
  const tone =
    level === "high"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
      : level === "medium"
        ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
        : "border-border bg-background text-muted-foreground";

  return (
    <span
      className={`inline-flex max-w-full flex-wrap items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] ${tone}`}
    >
      {level === "high" ? <span aria-hidden>✓</span> : null}
      <span>{confidenceLabel(level)}</span>
      {actLabel ? <span className="text-muted-foreground">· {actLabel}</span> : null}
    </span>
  );
}

function treatmentLabel(treatment: string): string {
  switch (treatment) {
    case "include":
      return "Included in assessable income";
    case "deduct":
      return "Deductible";
    case "final_withholding":
      return "Excluded (final withholding / exempt)";
    case "exempt":
      return "Excluded (exempt)";
    default:
      return treatment;
  }
}

function sectionHeading(field: IncomeCatalogField): string {
  if (field.paragraph) {
    return `Section ${field.section}(${field.paragraph})`;
  }
  return field.section ? `Section ${field.section}` : "—";
}

type FieldExplainDrawerProps = {
  field: IncomeCatalogField | null;
  actVersionLabel?: string | null;
  open: boolean;
  onClose: () => void;
};

export function FieldExplainDrawer({
  field,
  actVersionLabel,
  open,
  onClose,
}: FieldExplainDrawerProps) {
  if (!open || !field) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/40"
        aria-label="Close field explain drawer"
        onClick={onClose}
      />
      <aside
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l bg-background shadow-xl"
        role="dialog"
        aria-labelledby="oe-engine-field-explain-title"
      >
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
          <div className="space-y-1">
            <p id="oe-engine-field-explain-title" className="text-sm font-semibold">
              {field.display_name}
            </p>
            <p className="text-xs text-muted-foreground">
              Legal basis · {field.component_id}
            </p>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <ConfidenceBadge level={field.legal_confidence} actLabel={actVersionLabel} />
            <span className="inline-flex rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {treatmentLabel(field.default_treatment)}
            </span>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Section</p>
            <p className="font-medium">{sectionHeading(field)}</p>
            {field.reason_short ? (
              <p className="text-xs text-muted-foreground">{field.reason_short}</p>
            ) : null}
          </div>

          {field.source_quote ? (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Act quote</p>
              <blockquote className="rounded-md border bg-muted/30 px-3 py-2 text-xs leading-relaxed italic">
                “{field.source_quote}”
              </blockquote>
            </div>
          ) : null}

          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Confidence</p>
            <p className="text-xs">
              {field.legal_confidence}
              {field.confidence_reason ? ` — ${field.confidence_reason}` : ""}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

type CatalogFieldRowProps = {
  field: IncomeCatalogField;
  amount: string;
  onAmountChange: (value: string) => void;
  onExplain: () => void;
  treatmentLabel?: (field: IncomeCatalogField) => string;
  hint?: string;
  readOnly?: boolean;
};

export function CatalogFieldRow({
  field,
  amount,
  onAmountChange,
  onExplain,
  treatmentLabel: treatmentFn,
  hint,
  readOnly,
}: CatalogFieldRowProps) {
  const sec = field.paragraph
    ? `Sec ${field.section}(${field.paragraph})`
    : `Sec ${field.section}`;
  const treatment = treatmentFn ? treatmentFn(field) : field.default_treatment;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor={field.component_id}>{field.display_name}</Label>
        <button
          type="button"
          className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          onClick={onExplain}
          aria-label={`Explain ${field.display_name}`}
        >
          <Info className="h-3 w-3" aria-hidden />
          Explain
        </button>
      </div>
      <Input
        id={field.component_id}
        inputMode="numeric"
        value={formatMoneyInput(amount)}
        onChange={(event) => onAmountChange(formatMoneyInput(event.target.value))}
        placeholder="0"
        readOnly={readOnly}
        disabled={readOnly}
      />
      <p className="text-[11px] text-muted-foreground">
        {hint ??
          `${sec} · ${treatment}${field.reason_short ? ` — ${field.reason_short}` : ""}`}
      </p>
    </div>
  );
}
