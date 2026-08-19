import { useEffect, useState } from "react";
import { Info, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  getFilingCatalogExplain,
  type FilingCatalogExplain,
  type FilingCatalogField,
} from "../api";
import { formatMoneyInput } from "../format-lkr";

export function confidenceLabel(level: string): string {
  if (level === "high") return "High confidence";
  if (level === "medium") return "Medium confidence";
  if (level === "pending") return "Pending";
  return level;
}

export function ConfidenceBadge({
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
      {actLabel ? (
        <span className="text-muted-foreground">· {actLabel}</span>
      ) : null}
    </span>
  );
}

function treatmentLabel(treatment: string): string {
  switch (treatment) {
    case "include":
      return "Included in assessable income";
    case "deduct":
      return "Deductible (relief)";
    case "final_withholding":
      return "Excluded (final withholding / exempt)";
    case "exempt":
      return "Excluded (exempt)";
    case "credit":
      return "Tax credit";
    default:
      return treatment;
  }
}

function sectionHeading(payload: FilingCatalogExplain): string {
  if (payload.paragraph) {
    const p = payload.paragraph.trim();
    if (/^fifth\s+sch/i.test(p)) return p;
    return `Section ${payload.section ?? "?"}(${payload.paragraph})`;
  }
  return payload.section ? `Section ${payload.section}` : "—";
}

type FieldExplainDrawerProps = {
  field: FilingCatalogField | null;
  assessmentYear: "2024_25" | "2025_26";
  actVersionLabel?: string | null;
  open: boolean;
  onClose: () => void;
};

export function FieldExplainDrawer({
  field,
  assessmentYear,
  actVersionLabel,
  open,
  onClose,
}: FieldExplainDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<FilingCatalogExplain | null>(null);

  useEffect(() => {
    if (!open || !field) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getFilingCatalogExplain(field.component_id, assessmentYear)
      .then((data) => {
        if (!cancelled) setPayload(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load field explain.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, field?.component_id, assessmentYear]);

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
        aria-labelledby="field-explain-title"
      >
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
          <div className="space-y-1">
            <p id="field-explain-title" className="text-sm font-semibold">
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

        <div className="flex-1 overflow-y-auto px-4 py-4 text-sm space-y-4">
          {loading ? (
            <p className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading Act evidence…
            </p>
          ) : null}
          {error ? <p className="text-destructive text-xs">{error}</p> : null}

          {payload ? (
            <>
              <div className="flex flex-wrap gap-2">
                <ConfidenceBadge
                  level={payload.legal_confidence}
                  actLabel={payload.act_version_label ?? actVersionLabel}
                />
                <span className="inline-flex rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {treatmentLabel(payload.treatment)}
                </span>
              </div>

              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Section</p>
                <p className="font-medium">{sectionHeading(payload)}</p>
                {payload.reason_short ? (
                  <p className="text-xs text-muted-foreground">{payload.reason_short}</p>
                ) : null}
              </div>

              {payload.statutory_scope ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    Statutory scope
                  </p>
                  <p className="text-xs">{payload.statutory_scope}</p>
                </div>
              ) : null}

              {payload.source_quote ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    Act quote (catalog / bootstrap)
                  </p>
                  <blockquote className="rounded-md border bg-muted/30 px-3 py-2 text-xs italic leading-relaxed">
                    &ldquo;{payload.source_quote}&rdquo;
                  </blockquote>
                </div>
              ) : null}

              {payload.evidence_chunks && payload.evidence_chunks.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    Corpus evidence (Chroma)
                  </p>
                  {payload.evidence_chunks.map((ch) => (
                    <blockquote
                      key={ch.chunk_id}
                      className="rounded-md border bg-muted/20 px-3 py-2 text-[11px] leading-relaxed"
                    >
                      {ch.text.slice(0, 480)}
                      {ch.text.length > 480 ? "…" : ""}
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        {ch.section_ref ?? ch.source_doc_id ?? ch.chunk_id}
                      </p>
                    </blockquote>
                  ))}
                </div>
              ) : null}

              {payload.kg_nodes && payload.kg_nodes.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    Knowledge graph nodes
                  </p>
                  <ul className="space-y-1 text-[11px] font-mono">
                    {payload.kg_nodes.map((node) => (
                      <li key={`${node.node_type}:${node.node_id}`}>
                        {node.node_type}: {node.node_id}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Confidence</p>
                <p className="text-xs">
                  {payload.legal_confidence}
                  {payload.confidence_basis
                    ? ` (${payload.confidence_basis.replace(/_/g, " ")})`
                    : ""}
                  {payload.confidence_reason ? ` — ${payload.confidence_reason}` : ""}
                </p>
              </div>

              <div className="space-y-1 text-xs text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">Source: </span>
                  {payload.source_label ?? payload.source_doc_id ?? "—"}
                </p>
                {payload.rule_source_id ? (
                  <p>
                    <span className="font-medium text-foreground">Provenance: </span>
                    {payload.rule_source_id}
                  </p>
                ) : null}
                {payload.engine_handler ? (
                  <p>
                    <span className="font-medium text-foreground">Engine: </span>
                    {payload.engine_handler}
                  </p>
                ) : null}
              </div>

              {payload.evidence_warnings && payload.evidence_warnings.length > 0 ? (
                <p className="text-[10px] text-muted-foreground">
                  Evidence notes: {payload.evidence_warnings.join("; ")}
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      </aside>
    </>
  );
}

type CatalogFieldRowProps = {
  field: FilingCatalogField;
  amount: string;
  onAmountChange: (value: string) => void;
  actVersionLabel?: string | null;
  onExplain: () => void;
  treatmentLabel?: (field: FilingCatalogField) => string;
  hint?: string;
};

export function CatalogFieldRow({
  field,
  amount,
  onAmountChange,
  onExplain,
  treatmentLabel: treatmentFn,
  hint,
}: CatalogFieldRowProps) {
  const sec = field.paragraph
    ? `Sec ${field.section}(${field.paragraph})`
    : `Sec ${field.section}`;
  const treatment = treatmentFn
    ? treatmentFn(field)
    : field.default_treatment;

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
        onChange={(event) =>
          onAmountChange(formatMoneyInput(event.target.value))
        }
        placeholder="0"
      />
      <p className="text-[11px] text-muted-foreground">
        {hint ?? `${sec} · ${treatment}${field.reason_short ? ` — ${field.reason_short}` : ""}`}
      </p>
    </div>
  );
}
