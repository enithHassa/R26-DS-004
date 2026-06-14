import { useEffect, useMemo, useState } from "react";
import { Info, Scale, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  analyzeTransactionsBatch,
  applyTransactionClassBatch,
  getIncomeTypeCatalog,
  summarizeTaxableIncome,
  type AnalyzeTransactionResponse,
  type ExtractedTransactionItem,
  type IncomeTypeCatalogResponse,
} from "@/features/transaction-semantic/api";
import { formatLkr } from "@/features/transaction-semantic/format-lkr";

type FilterKey = "all" | "taxable" | "exempt" | "review";

export interface TransactionTaxClassificationPanelProps {
  transactions: ExtractedTransactionItem[];
  bankCode?: string | null;
  documentId?: string | null;
  documentLabel?: string;
}

interface ClassifiedRow {
  source: ExtractedTransactionItem;
  analysis: AnalyzeTransactionResponse;
}

interface IncomeBreakdownLine {
  classKey: string;
  count: number;
  amount: number;
}

function isReviewRow(row: ClassifiedRow): boolean {
  const status = row.analysis.taxability.taxability_status;
  return (
    status === "unknown" ||
    status === "partially_taxable" ||
    row.analysis.decision_mode === "human_required" ||
    row.analysis.confidence_report.is_ood
  );
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "taxable":
      return "bg-rose-100 text-rose-900";
    case "exempt":
      return "bg-emerald-100 text-emerald-900";
    case "partially_taxable":
      return "bg-amber-100 text-amber-900";
    default:
      return "bg-slate-100 text-slate-800";
  }
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

const CLASSIFY_BATCH_SIZE = 64;

export function TransactionTaxClassificationPanel({
  transactions,
  bankCode,
  documentId,
  documentLabel,
}: TransactionTaxClassificationPanelProps) {
  const [classifiedRows, setClassifiedRows] = useState<ClassifiedRow[]>([]);
  const [catalog, setCatalog] = useState<IncomeTypeCatalogResponse | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [persist, setPersist] = useState(false);
  const [isClassifying, setIsClassifying] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [serverSummary, setServerSummary] = useState<string | null>(null);

  const totals = useMemo(() => {
    let taxable = 0;
    let excluded = 0;
    let review = 0;
    let internalTransferExempt = 0;
    for (const row of classifiedRows) {
      const status = row.analysis.taxability.taxability_status;
      const amount = Number(row.source.amount_lkr);
      const taxableAmount = Number(row.analysis.taxability.taxable_amount ?? 0);
      if (isReviewRow(row)) {
        review += 1;
        continue;
      }
      if (status === "exempt") {
        excluded += Number.isNaN(amount) ? 0 : amount;
        if (row.analysis.semantic_category === "inter_account_transfer") {
          internalTransferExempt += 1;
        }
      } else {
        taxable += Number.isNaN(taxableAmount) ? 0 : taxableAmount;
      }
    }
    return { taxable, excluded, review, internalTransferExempt };
  }, [classifiedRows]);

  const incomeBreakdown = useMemo<IncomeBreakdownLine[]>(() => {
    const byClass = new Map<string, IncomeBreakdownLine>();
    for (const row of classifiedRows) {
      if (isReviewRow(row)) {
        continue;
      }
      if (row.analysis.taxability.taxability_status === "exempt") {
        continue;
      }
      const amount = Number(row.analysis.taxability.taxable_amount ?? 0);
      if (Number.isNaN(amount) || amount <= 0) {
        continue;
      }
      const classKey = row.analysis.semantic_category;
      const existing = byClass.get(classKey) ?? { classKey, count: 0, amount: 0 };
      existing.count += 1;
      existing.amount += amount;
      byClass.set(classKey, existing);
    }
    return [...byClass.values()].sort((left, right) => right.amount - left.amount);
  }, [classifiedRows]);

  const filteredRows = useMemo(() => {
    if (filter === "all") return classifiedRows;
    if (filter === "taxable") {
      return classifiedRows.filter(
        (row) =>
          !isReviewRow(row) &&
          row.analysis.taxability.taxability_status !== "exempt",
      );
    }
    if (filter === "exempt") {
      return classifiedRows.filter(
        (row) => row.analysis.taxability.taxability_status === "exempt",
      );
    }
    return classifiedRows.filter((row) => isReviewRow(row));
  }, [classifiedRows, filter]);

  const modelVersion = classifiedRows[0]?.analysis.taxability.model_version ?? null;

  useEffect(() => {
    void getIncomeTypeCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  async function handleClassChange(row: ClassifiedRow, classKey: string): Promise<void> {
    if (classKey === row.analysis.semantic_category) {
      return;
    }
    try {
      const response = await applyTransactionClassBatch({
        bank_code: bankCode ?? undefined,
        document_type: "bank_statement",
        items: [
          {
            row_id: row.source.id,
            raw_desc: row.source.description,
            amount_lkr: row.source.amount_lkr,
            tx_date: row.source.tx_date,
            direction: row.source.direction,
            class_key: classKey,
            model_semantic_category:
              row.analysis.model_semantic_category ?? row.analysis.semantic_category,
          },
        ],
      });
      const updated = response.results[0]?.result;
      if (!updated) {
        return;
      }
      setClassifiedRows((current) =>
        current.map((entry) =>
          entry.source.id === row.source.id ? { ...entry, analysis: updated } : entry,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply class override.");
    }
  }

  async function handleClassify(): Promise<void> {
    if (transactions.length === 0) {
      setError("Extract transactions first, then run tax classification.");
      return;
    }
    setIsClassifying(true);
    setError(null);
    setSuccess(null);
    setServerSummary(null);
    setProgress({ done: 0, total: transactions.length });
    try {
      const analyzed: ClassifiedRow[] = [];
      for (let offset = 0; offset < transactions.length; offset += CLASSIFY_BATCH_SIZE) {
        const chunk = transactions.slice(offset, offset + CLASSIFY_BATCH_SIZE);
        const response = await analyzeTransactionsBatch({
          bank_code: bankCode ?? undefined,
          document_type: "bank_statement",
          document_id: documentId ?? undefined,
          persist,
          items: chunk.map((tx) => ({
            row_id: tx.id,
            raw_desc: tx.description,
            amount_lkr: tx.amount_lkr,
            tx_date: tx.tx_date,
            direction: tx.direction,
          })),
        });
        for (let index = 0; index < chunk.length; index += 1) {
          analyzed.push({
            source: chunk[index],
            analysis: response.results[index].result,
          });
        }
        setProgress({ done: offset + chunk.length, total: transactions.length });
      }
      setClassifiedRows(analyzed);
      setFilter("review");
      setSuccess(
        `Classified ${analyzed.length} row(s)${documentLabel ? ` from ${documentLabel}` : ""}. Review queue opened first.`,
      );

      if (persist) {
        const dates = transactions.map((tx) => tx.tx_date).sort();
        const summary = await summarizeTaxableIncome({
          date_from: dates[0],
          date_to: dates[dates.length - 1],
          bank_code: bankCode ?? undefined,
        });
        setServerSummary(
          `Persisted summary: taxable ${formatLkr(summary.total_taxable_lkr)}, excluded ${formatLkr(summary.total_excluded_lkr)}, review ${summary.review_count}.`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tax classification failed.");
    } finally {
      setIsClassifying(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Scale className="h-4 w-4" /> Taxable vs non-taxable
          </CardTitle>
          <CardDescription>
            Narrative context and DistilBERT feed IRA rules for the final taxable outcome. Change the
            class on any row to override the model quietly.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <StatusRow
            transactions={transactions.length}
            classified={classifiedRows.length}
            modelVersion={modelVersion}
          />
          <ActionRow
            persist={persist}
            setPersist={setPersist}
            isClassifying={isClassifying}
            progress={progress}
            onClassify={() => void handleClassify()}
          />
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
          {serverSummary ? <p className="text-sm text-muted-foreground">{serverSummary}</p> : null}
        </CardContent>
      </Card>

      {classifiedRows.length > 0 ? (
        <TaxIncomeSummary
          assessable={totals.taxable}
          excluded={totals.excluded}
          reviewCount={totals.review}
          internalTransferCount={totals.internalTransferExempt}
          breakdown={incomeBreakdown}
        />
      ) : null}

      {classifiedRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Classified transactions</CardTitle>
            <CardDescription>
              Review classifications and override the class when needed. Hover the info icon for the
              narrative interpretation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(["all", "taxable", "exempt", "review"] as const).map((key) => (
                <Button
                  key={key}
                  size="sm"
                  variant={filter === key ? "default" : "outline"}
                  onClick={() => setFilter(key)}
                >
                  {key}
                </Button>
              ))}
            </div>
            <div className="space-y-3">
              {filteredRows.map((row) => (
                <TransactionClassificationRow
                  key={row.source.id}
                  row={row}
                  catalog={catalog}
                  onClassChange={(classKey) => void handleClassChange(row, classKey)}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function TaxIncomeSummary({
  assessable,
  excluded,
  reviewCount,
  internalTransferCount,
  breakdown,
}: {
  assessable: number;
  excluded: number;
  reviewCount: number;
  internalTransferCount: number;
  breakdown: IncomeBreakdownLine[];
}) {
  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <CardHeader className="border-b bg-slate-50/80">
        <CardTitle>Taxable income summary</CardTitle>
        <CardDescription>
          Assessable totals use IRA rule taxable amounts. Excluded gross sums exempt movements and is
          not your personal tax-free allowance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 p-6">
        <div className="rounded-2xl border border-rose-100 bg-gradient-to-br from-rose-50 via-white to-white p-6">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-rose-700/80">
            Assessable taxable portion
          </p>
          <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
            {formatLkr(String(assessable))}
          </p>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            This is the amount that counts toward taxable income after rule-based treatment, not the
            gross value of every bank movement.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryMetric
            label="Excluded movements"
            value={formatLkr(String(excluded))}
            hint="Gross exempt line amounts"
          />
          <SummaryMetric
            label="Needs review"
            value={String(reviewCount)}
            hint="Rows flagged for manual review"
          />
          <SummaryMetric
            label="Internal transfers"
            value={String(internalTransferCount)}
            hint="Auto-classified exempt transfers"
          />
        </div>

        {breakdown.length > 0 ? (
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium text-foreground">Assessable by class</h3>
              <p className="text-sm text-muted-foreground">
                Taxable amounts grouped by the applied income class.
              </p>
            </div>
            <div className="divide-y rounded-xl border bg-white">
              {breakdown.map((line) => (
                <div
                  key={line.classKey}
                  className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
                >
                  <div>
                    <p className="font-medium text-foreground">{line.classKey}</p>
                    <p className="text-xs text-muted-foreground">
                      {line.count} transaction{line.count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <p className="font-medium tabular-nums text-foreground">
                    {formatLkr(String(line.amount))}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SummaryMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function TransactionClassificationRow({
  row,
  catalog,
  onClassChange,
}: {
  row: ClassifiedRow;
  catalog: IncomeTypeCatalogResponse | null;
  onClassChange: (classKey: string) => void;
}) {
  const status = row.analysis.taxability.taxability_status;
  const taxableAmount = Number(row.analysis.taxability.taxable_amount ?? 0);
  const showAssessable =
    !isReviewRow(row) && status !== "exempt" && !Number.isNaN(taxableAmount) && taxableAmount > 0;

  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{row.source.tx_date}</span>
            <span>{row.source.direction}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusBadgeClass(status)}`}
            >
              {statusLabel(status)}
            </span>
          </div>
          <div className="flex items-start gap-2">
            <p className="min-w-0 flex-1 text-sm leading-6 text-foreground">
              {row.source.description}
            </p>
            <NarrativeInsight interpretation={row.analysis.narrative_interpretation} />
          </div>
          <p className="text-xs text-muted-foreground">
            {row.analysis.tax_rule_code}
            {row.analysis.rule_reference ? ` · ${row.analysis.rule_reference}` : ""}
          </p>
        </div>

        <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-[24rem] lg:shrink-0">
          <div className="rounded-lg border bg-slate-50/70 p-3">
            <p className="text-xs text-muted-foreground">Movement amount</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">
              {formatLkr(row.source.amount_lkr)}
            </p>
          </div>
          <div className="rounded-lg border bg-slate-50/70 p-3">
            <p className="text-xs text-muted-foreground">Assessable portion</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">
              {showAssessable ? formatLkr(row.analysis.taxability.taxable_amount) : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 border-t pt-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Applied class
        </p>
        <ClassSelect
          value={row.analysis.semantic_category}
          options={catalog?.items ?? []}
          onChange={onClassChange}
        />
        {row.analysis.model_semantic_category &&
        row.analysis.model_semantic_category !== row.analysis.semantic_category ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Model suggestion: {row.analysis.model_semantic_category}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function NarrativeInsight({ interpretation }: { interpretation: string | null }) {
  if (!interpretation) {
    return null;
  }

  return (
    <span className="group/narrative relative inline-flex shrink-0">
      <button
        type="button"
        className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
        aria-label="Show narrative interpretation"
      >
        <Info className="h-4 w-4" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute right-0 top-full z-20 mt-2 hidden w-72 rounded-lg border bg-white p-3 text-left text-xs leading-5 text-foreground shadow-lg group-hover/narrative:block group-focus-within/narrative:block"
      >
        <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Narrative interpretation
        </span>
        {interpretation}
      </span>
    </span>
  );
}

function ClassSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: IncomeTypeCatalogResponse["items"];
  onChange: (classKey: string) => void;
}) {
  if (options.length === 0) {
    return <span>{value}</span>;
  }
  const selectOptions = options.some((item) => item.class_key === value)
    ? options
    : [
        {
          class_key: value,
          group: "",
          description: value,
          tax_rule_code: "",
          default_taxability_status: "unknown",
          default_taxable_fraction: 0,
          treatment: null,
          rule_reference: "",
          explanation: "",
          is_conditional: false,
        },
        ...options,
      ];
  return (
    <Select value={value} onChange={(event) => onChange(event.target.value)}>
      {selectOptions.map((item) => (
        <option key={item.class_key} value={item.class_key}>
          {item.class_key}
        </option>
      ))}
    </Select>
  );
}

function StatusRow({
  transactions,
  classified,
  modelVersion,
}: {
  transactions: number;
  classified: number;
  modelVersion: string | null;
}) {
  return (
    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
      <span>Extracted rows: {transactions}</span>
      <span>Classified: {classified}</span>
      {modelVersion ? <span>Model: {modelVersion}</span> : null}
    </div>
  );
}

function ActionRow({
  persist,
  setPersist,
  isClassifying,
  progress,
  onClassify,
}: {
  persist: boolean;
  setPersist: (value: boolean) => void;
  isClassifying: boolean;
  progress: { done: number; total: number };
  onClassify: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Button onClick={onClassify} disabled={isClassifying}>
        <Sparkles className="mr-2 h-4 w-4" />
        {isClassifying
          ? `Classifying ${progress.done}/${progress.total}...`
          : "Classify extracted rows"}
      </Button>
      <div className="flex items-center gap-2">
        <Checkbox
          id="persist-tax-analysis"
          checked={persist}
          onChange={(event) => setPersist(event.target.checked)}
        />
        <Label htmlFor="persist-tax-analysis">Persist each row to the database</Label>
      </div>
    </div>
  );
}
