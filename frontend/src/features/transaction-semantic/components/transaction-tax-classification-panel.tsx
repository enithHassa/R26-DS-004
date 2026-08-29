import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Info, Scale, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ActivitySummaryPanel } from "@/features/transaction-semantic/components/activity-summary-panel";
import {
  analyzeTransactionsBatch,
  applyTransactionClassBatch,
  getDocumentClassifications,
  getIncomeTypeCatalog,
  summarizeActivity,
  type ActivitySummaryGroup,
  type AnalyzeTransactionResponse,
  type ClassificationFacts,
  type ExtractedTransactionItem,
  type IncomeTypeCatalogResponse,
} from "@/features/transaction-semantic/api";
import { formatLkr } from "@/features/transaction-semantic/format-lkr";
import { useAuditorTaxpayerId } from "@/hooks/use-auditor-taxpayer-id";
import { useActiveProfileId } from "@/features/personalized-recommendation/store/dashboard-store";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

type FilterKey = "all" | "taxable" | "exempt" | "review";
type ListViewKey = "all" | "summarised";

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
  if (row.analysis.certainty_tier === "indeterminate") {
    return true;
  }
  if (row.analysis.certainty_tier === "guaranteed_taxable" || row.analysis.certainty_tier === "guaranteed_non_taxable") {
    return false;
  }
  const status = row.analysis.taxability.taxability_status;
  return (
    status === "unknown" ||
    status === "partially_taxable" ||
    row.analysis.decision_mode === "human_required" ||
    row.analysis.confidence_report.is_ood
  );
}

function auditorFacts(
  evidence: string,
  taxpayerId: string | null,
): { classKey: string; facts: ClassificationFacts } {
  const taxpayerFact = taxpayerId ? { taxpayer_id: taxpayerId } : {};
  switch (evidence) {
    case "invoice":
      return {
        classKey: "freelance_service",
        facts: {
          auditor_evidence: "invoice",
          has_supporting_receipt: true,
          ...taxpayerFact,
        },
      };
    case "loan":
      return {
        classKey: "loan_received",
        facts: { auditor_evidence: "loan", ...taxpayerFact },
      };
    case "gift":
      return {
        classKey: "gift_received",
        facts: {
          auditor_evidence: "gift",
          counterparty_type: "relative",
          ...taxpayerFact,
        },
      };
    case "shared_expense":
      return {
        classKey: "reimbursement",
        facts: {
          auditor_evidence: "shared_expense",
          has_supporting_receipt: true,
          ...taxpayerFact,
        },
      };
    case "own_transfer":
      return {
        classKey: "inter_account_transfer",
        facts: { auditor_evidence: "own_transfer", ...taxpayerFact },
      };
    default:
      return { classKey: "unknown", facts: taxpayerFact };
  }
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
  const taxpayerId = useAuditorTaxpayerId();
  const activeProfileId = useActiveProfileId();
  const isLocked = useAuditorWorkspaceStore((s) => s.isLocked);
  const navigate = useNavigate();
  const persistClassifications = Boolean(activeProfileId && taxpayerId);
  const setPendingTransactionBreakdown = useAuditorWorkspaceStore(
    (s) => s.setPendingTransactionBreakdown,
  );
  const [classifiedRows, setClassifiedRows] = useState<ClassifiedRow[]>([]);
  const [catalog, setCatalog] = useState<IncomeTypeCatalogResponse | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [listView, setListView] = useState<ListViewKey>("all");
  const [isClassifying, setIsClassifying] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [serverSummary, setServerSummary] = useState<string | null>(null);

  const totals = useMemo(() => {
    let excluded = 0;
    let review = 0;
    let internalTransferExempt = 0;
    let taxableInflows = 0;
    let nonTaxableInflows = 0;
    let indeterminateInflows = 0;
    let outflow = 0;
    for (const row of classifiedRows) {
      const status = row.analysis.taxability.taxability_status;
      const amount = Number(row.source.amount_lkr);
      const taxableAmount = Number(row.analysis.taxability.taxable_amount ?? 0);
      const isCredit = row.source.direction === "CR";
      if (!isCredit) {
        outflow += Number.isNaN(amount) ? 0 : amount;
      } else if (row.analysis.certainty_tier === "guaranteed_taxable") {
        taxableInflows += Number.isNaN(taxableAmount) ? 0 : taxableAmount;
      } else if (row.analysis.certainty_tier === "guaranteed_non_taxable") {
        nonTaxableInflows += Number.isNaN(amount) ? 0 : amount;
      } else {
        indeterminateInflows += Number.isNaN(amount) ? 0 : amount;
      }
      if (isReviewRow(row)) {
        review += 1;
      }
      if (status === "exempt" && !isReviewRow(row)) {
        excluded += Number.isNaN(amount) ? 0 : amount;
        if (row.analysis.semantic_category === "inter_account_transfer") {
          internalTransferExempt += 1;
        }
      }
    }
    const potential = taxableInflows + indeterminateInflows;
    return {
      excluded,
      review,
      internalTransferExempt,
      taxableInflows,
      nonTaxableInflows,
      indeterminateInflows,
      outflow,
      potential,
      exceedsAnnual: potential > 1_800_000,
      exceedsMonthly: potential > 150_000,
      taxable: potential,
    };
  }, [classifiedRows]);

  const bucketRows = useMemo(() => {
    const guaranteedTaxable: ClassifiedRow[] = [];
    const guaranteedNonTaxable: ClassifiedRow[] = [];
    const indeterminate: ClassifiedRow[] = [];
    for (const row of classifiedRows) {
      if (row.source.direction !== "CR") continue;
      const tier = row.analysis.certainty_tier;
      if (tier === "guaranteed_taxable") guaranteedTaxable.push(row);
      else if (tier === "guaranteed_non_taxable") guaranteedNonTaxable.push(row);
      else indeterminate.push(row);
    }
    const byAmountDesc = (a: ClassifiedRow, b: ClassifiedRow) =>
      Number(b.source.amount_lkr) - Number(a.source.amount_lkr);
    return {
      guaranteedTaxable: [...guaranteedTaxable].sort(byAmountDesc),
      guaranteedNonTaxable: [...guaranteedNonTaxable].sort(byAmountDesc),
      indeterminate: [...indeterminate].sort(byAmountDesc),
    };
  }, [classifiedRows]);

  const incomeBreakdown = useMemo<IncomeBreakdownLine[]>(() => {
    const byClass = new Map<string, IncomeBreakdownLine>();
    for (const row of classifiedRows) {
      if (row.source.direction !== "CR") {
        continue;
      }
      if (row.analysis.certainty_tier === "guaranteed_non_taxable") {
        continue;
      }
      const amount = Number(row.analysis.taxability.taxable_amount ?? row.source.amount_lkr);
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
    let rows: ClassifiedRow[];
    if (filter === "all") rows = classifiedRows;
    else if (filter === "taxable") {
      rows = classifiedRows.filter((row) => {
        const amount = Number(row.analysis.taxability.taxable_amount ?? 0);
        return row.source.direction === "CR" && !Number.isNaN(amount) && amount > 0;
      });
    } else if (filter === "exempt") {
      rows = classifiedRows.filter(
        (row) => row.analysis.taxability.taxability_status === "exempt",
      );
    } else {
      rows = classifiedRows.filter((row) => isReviewRow(row));
    }
    if (filter === "review") {
      return [...rows].sort((a, b) => Number(b.source.amount_lkr) - Number(a.source.amount_lkr));
    }
    return rows;
  }, [classifiedRows, filter]);

  const reviewRowIds = useMemo(
    () => classifiedRows.filter((row) => isReviewRow(row)).map((row) => row.source.id),
    [classifiedRows],
  );

  const activityTransactions = useMemo(
    () =>
      classifiedRows.length > 0
        ? classifiedRows.map((row) => row.source)
        : transactions,
    [classifiedRows, transactions],
  );

  const modelVersion = classifiedRows[0]?.analysis.taxability.model_version ?? null;

  useEffect(() => {
    void getIncomeTypeCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  useEffect(() => {
    setClassifiedRows([]);
    setSuccess(null);
    setError(null);
  }, [documentId]);

  useEffect(() => {
    if (!documentId || !activeProfileId || transactions.length === 0) {
      return;
    }
    let cancelled = false;
    void getDocumentClassifications(documentId, activeProfileId)
      .then((response) => {
        if (cancelled || response.items.length === 0) {
          return;
        }
        const byExtractedId = new Map(
          response.items.map((item) => [item.extracted_transaction_id, item.result]),
        );
        const restored: ClassifiedRow[] = [];
        for (const tx of transactions) {
          const analysis = byExtractedId.get(tx.id);
          if (analysis) {
            restored.push({ source: tx, analysis });
          }
        }
        if (restored.length > 0) {
          setClassifiedRows(restored);
          setSuccess(`Loaded ${restored.length} saved classification(s) for this document.`);
        }
      })
      .catch(() => {
        // No saved classifications yet — normal on first visit.
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, activeProfileId, transactions]);

  async function handleClassChange(
    row: ClassifiedRow,
    classKey: string,
    facts?: ClassificationFacts,
  ): Promise<void> {
    await handleBulkClassChange([row], classKey, facts);
  }

  async function handleBulkClassChange(
    rows: ClassifiedRow[],
    classKey: string,
    facts?: ClassificationFacts,
  ): Promise<void> {
    if (rows.length === 0) {
      return;
    }
    const targets = facts
      ? rows
      : rows.filter((row) => row.analysis.semantic_category !== classKey);
    if (targets.length === 0) {
      return;
    }
    try {
      const response = await applyTransactionClassBatch({
        bank_code: bankCode ?? undefined,
        document_type: "bank_statement",
        document_id: documentId ?? undefined,
        financial_profile_id: activeProfileId ?? undefined,
        persist_classifications: persistClassifications,
        items: targets.map((row) => ({
          row_id: row.source.id,
          raw_desc: row.source.description,
          amount_lkr: row.source.amount_lkr,
          tx_date: row.source.tx_date,
          direction: row.source.direction,
          class_key: classKey,
          facts: facts ?? (taxpayerId ? { taxpayer_id: taxpayerId } : undefined),
          model_semantic_category:
            row.analysis.model_semantic_category ?? row.analysis.semantic_category,
        })),
      });
      const byRowId = new Map<string, AnalyzeTransactionResponse>();
      for (let i = 0; i < targets.length; i += 1) {
        const updated = response.results[i]?.result;
        if (updated) {
          byRowId.set(targets[i].source.id, updated);
        }
      }
      if (byRowId.size === 0) {
        return;
      }
      setClassifiedRows((current) =>
        current.map((entry) => {
          const updated = byRowId.get(entry.source.id);
          return updated ? { ...entry, analysis: updated } : entry;
        }),
      );
      setSuccess(
        targets.length === 1
          ? "Override applied."
          : `Applied override to ${targets.length} selected row(s).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply class override.");
    }
  }

  async function handleClassify(): Promise<void> {
    if (!taxpayerId) {
      setError("Select and lock a taxpayer profile before classifying.");
      return;
    }
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
          financial_profile_id: activeProfileId ?? undefined,
          persist_classifications: persistClassifications,
          taxpayer_id: taxpayerId,
          items: chunk.map((tx) => ({
            row_id: tx.id,
            raw_desc: tx.description,
            amount_lkr: tx.amount_lkr,
            tx_date: tx.tx_date,
            direction: tx.direction,
            facts: { taxpayer_id: taxpayerId },
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
      setListView("all");
      setFilter("all");
      setSuccess(
        `Classified ${analyzed.length} row(s)${documentLabel ? ` from ${documentLabel}` : ""}${
          persistClassifications ? " — saved to profile." : "."
        } Showing all rows — switch to Summarised for grouped review.`,
      );
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
            Layer 1 bank codes and the linked-account graph settle guaranteed rows. DistilBERT
            predicts intent only when the narration is not already tri-state. This screen does not
            compute tax, personal relief, or s.11 deductions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <StatusRow
            transactions={transactions.length}
            classified={classifiedRows.length}
            modelVersion={modelVersion}
          />
          <ActionRow
            persistClassifications={persistClassifications}
            isLocked={isLocked}
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
          taxableInflows={totals.taxableInflows}
          nonTaxableInflows={totals.nonTaxableInflows}
          indeterminateInflows={totals.indeterminateInflows}
          outflow={totals.outflow}
          potential={totals.potential}
          exceedsAnnual={totals.exceedsAnnual}
          exceedsMonthly={totals.exceedsMonthly}
          breakdown={incomeBreakdown}
          guaranteedTaxableRows={bucketRows.guaranteedTaxable}
          guaranteedNonTaxableRows={bucketRows.guaranteedNonTaxable}
          indeterminateRows={bucketRows.indeterminate}
        />
      ) : null}

      {incomeBreakdown.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-3">
          <p className="flex-1 text-sm text-muted-foreground">
            Send classified taxable inflow buckets to Optimization Engine income (additive merge).
          </p>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => {
              setPendingTransactionBreakdown(
                incomeBreakdown.map((line) => ({
                  classKey: line.classKey,
                  amount: line.amount,
                })),
              );
              navigate("/optimization-explainable-engine/income");
            }}
          >
            Send totals to Optimization
          </Button>
        </div>
      ) : null}

      {activityTransactions.length > 0 ? (
        <ActivitySummaryPanel
          variant="tax"
          transactions={activityTransactions}
          reviewRowIds={reviewRowIds}
          defaultScope={classifiedRows.length > 0 ? "review" : "all"}
        />
      ) : null}

      {classifiedRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Classified transactions</CardTitle>
            <CardDescription>
              Use <span className="font-medium text-foreground">All</span> for the full one-by-one
              list, or <span className="font-medium text-foreground">Summarised</span> for similar
              groups with bulk override.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant={listView === "all" ? "default" : "outline"}
                onClick={() => setListView("all")}
              >
                All
              </Button>
              <Button
                size="sm"
                variant={listView === "summarised" ? "default" : "outline"}
                onClick={() => {
                  setListView("summarised");
                  setFilter("all");
                }}
              >
                Summarised
              </Button>
              {listView === "summarised" ? (
                <>
                  <span className="mx-1 h-4 w-px bg-border" aria-hidden />
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
                </>
              ) : null}
            </div>

            {listView === "all" ? (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Full one-by-one list ({classifiedRows.length} row
                  {classifiedRows.length === 1 ? "" : "s"}).
                </p>
                {classifiedRows.map((row) => (
                  <TransactionClassificationRow
                    key={row.source.id}
                    row={row}
                    catalog={catalog}
                    onClassChange={(classKey) => void handleClassChange(row, classKey)}
                    onAuditorEvidence={(evidence) => {
                      const mapped = auditorFacts(evidence, taxpayerId);
                      void handleClassChange(row, mapped.classKey, mapped.facts);
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Similar movements grouped for filter “{filter}”. Expand a group, select rows, then
                  apply bulk class or auditor override.
                </p>
                <ClassifiedGroupedList
                  rows={filteredRows}
                  catalog={catalog}
                  onClassChange={(row, classKey) => void handleClassChange(row, classKey)}
                  onAuditorEvidence={(row, evidence) => {
                    const mapped = auditorFacts(evidence, taxpayerId);
                    void handleClassChange(row, mapped.classKey, mapped.facts);
                  }}
                  onBulkClassChange={(rows, classKey) => void handleBulkClassChange(rows, classKey)}
                  onBulkAuditorEvidence={(rows, evidence) => {
                    const mapped = auditorFacts(evidence, taxpayerId);
                    void handleBulkClassChange(rows, mapped.classKey, mapped.facts);
                  }}
                />
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function ClassifiedGroupedList({
  rows,
  catalog,
  onClassChange,
  onAuditorEvidence,
  onBulkClassChange,
  onBulkAuditorEvidence,
}: {
  rows: ClassifiedRow[];
  catalog: IncomeTypeCatalogResponse | null;
  onClassChange: (row: ClassifiedRow, classKey: string) => void;
  onAuditorEvidence: (row: ClassifiedRow, evidence: string) => void;
  onBulkClassChange: (rows: ClassifiedRow[], classKey: string) => void;
  onBulkAuditorEvidence: (rows: ClassifiedRow[], evidence: string) => void;
}) {
  const [activityGroups, setActivityGroups] = useState<ActivitySummaryGroup[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (rows.length === 0) {
      setActivityGroups([]);
      setSelectedIds(new Set());
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void summarizeActivity({
      items: rows.map((row) => ({
        row_id: row.source.id,
        raw_desc: row.source.description,
        amount_lkr: row.source.amount_lkr,
        tx_date: row.source.tx_date,
        direction: row.source.direction,
      })),
    })
      .then((resp) => {
        if (cancelled) return;
        setActivityGroups(resp.groups);
        const next: Record<string, boolean> = {};
        if (resp.groups.length === 1) {
          next[resp.groups[0].group_key] = true;
        }
        setExpanded(next);
        setSelectedIds(new Set());
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not group classified rows.");
        setActivityGroups([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [rows]);

  const byId = useMemo(() => {
    const map = new Map<string, ClassifiedRow>();
    for (const row of rows) {
      map.set(row.source.id, row);
    }
    return map;
  }, [rows]);

  const grouped = useMemo(() => {
    if (activityGroups.length === 0) {
      return [
        {
          group_key: "flat",
          label: "All matching rows",
          hint: "Ungrouped list",
          direction: "CR" as const,
          count: rows.length,
          total_lkr: String(
            rows.reduce((sum, row) => sum + Number(row.source.amount_lkr || 0), 0),
          ),
          reviewCount: rows.filter((row) => isReviewRow(row)).length,
          members: rows,
        },
      ];
    }
    return activityGroups
      .map((group) => {
        const members = group.members
          .map((m) => (m.row_id ? byId.get(m.row_id) : undefined))
          .filter((row): row is ClassifiedRow => row != null);
        if (members.length === 0) return null;
        const total = members.reduce((sum, row) => sum + Number(row.source.amount_lkr || 0), 0);
        const reviewCount = members.filter((row) => isReviewRow(row)).length;
        return {
          group_key: group.group_key,
          label: group.label,
          hint: group.hint,
          direction: group.direction,
          count: members.length,
          total_lkr: String(total),
          reviewCount,
          members,
        };
      })
      .filter((g): g is NonNullable<typeof g> => g != null);
  }, [activityGroups, byId, rows]);

  const selectedRows = useMemo(
    () => rows.filter((row) => selectedIds.has(row.source.id)),
    [rows, selectedIds],
  );

  function toggleRow(id: string): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setGroupSelection(memberIds: string[], select: boolean): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of memberIds) {
        if (select) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }

  function selectAllFiltered(): void {
    setSelectedIds(new Set(rows.map((row) => row.source.id)));
  }

  function clearSelection(): void {
    setSelectedIds(new Set());
  }

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No rows match this filter.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-slate-50/80 px-3 py-2">
        <span className="text-xs text-muted-foreground">
          {selectedRows.length} selected
        </span>
        <Button size="sm" variant="outline" onClick={selectAllFiltered}>
          Select all ({rows.length})
        </Button>
        <Button size="sm" variant="ghost" onClick={clearSelection} disabled={selectedRows.length === 0}>
          Clear
        </Button>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Label className="text-xs text-muted-foreground">Bulk class</Label>
          <ClassSelect
            value=""
            placeholder="Apply class to selected…"
            options={catalog?.items ?? []}
            onChange={(classKey) => {
              if (selectedRows.length === 0) {
                setError("Select at least one row first.");
                return;
              }
              onBulkClassChange(selectedRows, classKey);
            }}
          />
          <Select
            value=""
            onChange={(event) => {
              if (!event.target.value) return;
              if (selectedRows.length === 0) {
                setError("Select at least one row first.");
                return;
              }
              onBulkAuditorEvidence(selectedRows, event.target.value);
              event.target.value = "";
            }}
          >
            <option value="">Bulk auditor override…</option>
            <option value="invoice">Invoice / service contract (taxable business)</option>
            <option value="loan">Loan agreement (non-taxable principal)</option>
            <option value="gift">Gift / family support (Sec 8)</option>
            <option value="shared_expense">Shared expense / reimbursement</option>
            <option value="own_transfer">Own-account transfer</option>
          </Select>
        </div>
      </div>

      {isLoading ? <p className="text-sm text-muted-foreground">Grouping similar rows…</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="space-y-2">
        {grouped.map((group) => {
          const open = Boolean(expanded[group.group_key]);
          const reviewCount = group.reviewCount ?? 0;
          const memberIds = group.members.map((row) => row.source.id);
          const selectedInGroup = memberIds.filter((id) => selectedIds.has(id)).length;
          const allSelected = memberIds.length > 0 && selectedInGroup === memberIds.length;

          return (
            <div key={group.group_key} className="rounded-xl border bg-white">
              <div className="flex items-start gap-2 px-3 py-3">
                <div
                  className="pt-1"
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  <Checkbox
                    checked={allSelected}
                    onChange={(event) => setGroupSelection(memberIds, event.target.checked)}
                    aria-label={`Select all in ${group.label}`}
                  />
                </div>
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-start gap-3 text-left hover:opacity-90"
                  onClick={() =>
                    setExpanded((prev) => ({
                      ...prev,
                      [group.group_key]: !prev[group.group_key],
                    }))
                  }
                >
                  <span className="mt-0.5 text-muted-foreground">
                    {open ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{group.label}</p>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                        {group.direction}
                      </span>
                      <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-muted-foreground">
                        {group.count} row{group.count === 1 ? "" : "s"}
                      </span>
                      {selectedInGroup > 0 ? (
                        <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-900">
                          {selectedInGroup} selected
                        </span>
                      ) : null}
                      {reviewCount > 0 ? (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-900">
                          {reviewCount} need review
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{group.hint}</p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold tabular-nums text-foreground">
                    {formatLkr(group.total_lkr)}
                  </p>
                </button>
              </div>
              {open ? (
                <div className="space-y-3 border-t px-3 py-3">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setGroupSelection(memberIds, true)}
                    >
                      Select all in group
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setGroupSelection(memberIds, false)}
                    >
                      Clear group
                    </Button>
                  </div>
                  {group.members.map((row) => (
                    <TransactionClassificationRow
                      key={row.source.id}
                      row={row}
                      catalog={catalog}
                      selected={selectedIds.has(row.source.id)}
                      onToggleSelect={() => toggleRow(row.source.id)}
                      onClassChange={(classKey) => onClassChange(row, classKey)}
                      onAuditorEvidence={(evidence) => onAuditorEvidence(row, evidence)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TaxIncomeSummary({
  assessable,
  excluded,
  reviewCount,
  internalTransferCount,
  taxableInflows,
  nonTaxableInflows,
  indeterminateInflows,
  outflow,
  potential,
  exceedsAnnual,
  exceedsMonthly,
  breakdown,
  guaranteedTaxableRows,
  guaranteedNonTaxableRows,
  indeterminateRows,
}: {
  assessable: number;
  excluded: number;
  reviewCount: number;
  internalTransferCount: number;
  taxableInflows: number;
  nonTaxableInflows: number;
  indeterminateInflows: number;
  outflow: number;
  potential: number;
  exceedsAnnual: boolean;
  exceedsMonthly: boolean;
  breakdown: IncomeBreakdownLine[];
  guaranteedTaxableRows: ClassifiedRow[];
  guaranteedNonTaxableRows: ClassifiedRow[];
  indeterminateRows: ClassifiedRow[];
}) {
  const [openBucket, setOpenBucket] = useState<
    "non_taxable" | "taxable" | "indeterminate" | null
  >("non_taxable");

  function toggleBucket(key: "non_taxable" | "taxable" | "indeterminate"): void {
    setOpenBucket((prev) => (prev === key ? null : key));
  }

  const openRows =
    openBucket === "non_taxable"
      ? guaranteedNonTaxableRows
      : openBucket === "taxable"
        ? guaranteedTaxableRows
        : openBucket === "indeterminate"
          ? indeterminateRows
          : [];

  const openTitle =
    openBucket === "non_taxable"
      ? "Guaranteed non-taxable inflows — how they were excluded"
      : openBucket === "taxable"
        ? "Guaranteed taxable inflows — why they are assessable"
        : openBucket === "indeterminate"
          ? "Indeterminate inflows — still in presumptive assessable"
          : "";

  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <CardHeader className="border-b bg-slate-50/80">
        <CardTitle>Presumptive assessable inflows</CardTitle>
        <CardDescription>
          Unproven credits are included in the taxable total until you override them as loan, gift,
          shared expense, or own transfer. Debits are never income here. Personal relief is Comp 2/5.
          Click a bucket below to see the contributing credits and Layer-1 / rule reasons.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 p-6">
        <div className="rounded-2xl border border-rose-100 bg-gradient-to-br from-rose-50 via-white to-white p-6">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-rose-700/80">
            Presumptive assessable (includes unproven credits)
          </p>
          <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
            {formatLkr(String(assessable))}
          </p>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Bank-coded income {formatLkr(String(taxableInflows))} plus unproven credits{" "}
            {formatLkr(String(indeterminateInflows))}. Override a review row to take it out of this
            total.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryMetric
            label="Guaranteed non-taxable inflows"
            value={formatLkr(String(nonTaxableInflows))}
            hint={`${guaranteedNonTaxableRows.length} credit(s) · own top-ups, reversals, linked accounts`}
            active={openBucket === "non_taxable"}
            onClick={() => toggleBucket("non_taxable")}
          />
          <SummaryMetric
            label="Indeterminate inflows"
            value={formatLkr(String(indeterminateInflows))}
            hint={`${reviewCount} rows still in review — included in the taxable total until overridden`}
            active={openBucket === "indeterminate"}
            onClick={() => toggleBucket("indeterminate")}
          />
          <SummaryMetric
            label="Outflows (memo)"
            value={formatLkr(String(outflow))}
            hint="Not income; s.11 deductibility is Comp 2 if business is declared"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={openBucket === "taxable" ? "default" : "outline"}
            onClick={() => toggleBucket("taxable")}
          >
            Show bank-coded taxable ({guaranteedTaxableRows.length})
          </Button>
        </div>

        {openBucket && openRows.length > 0 ? (
          <BucketDetailTable title={openTitle} rows={openRows} bucket={openBucket} />
        ) : openBucket && openRows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No credits in this bucket.</p>
        ) : null}

        {exceedsMonthly ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            {exceedsAnnual
              ? `Presumptive assessable inflows (${formatLkr(String(potential))}) exceed the LKR 1,800,000 annual personal relief. Override unproven credits to exclude them. Comp 2/5 apply relief — Comp 1 does not compute tax.`
              : `Presumptive assessable inflows (${formatLkr(String(potential))}) exceed the LKR 150,000 monthly equivalent of personal relief. Unproven credits are already in this total. Override to exclude; Comp 1 does not compute tax payable.`}
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <SummaryMetric
            label="Exempt movements (all directions)"
            value={formatLkr(String(excluded))}
            hint="Includes spend and fees, not a tax-free allowance"
          />
          <SummaryMetric
            label="Internal transfers"
            value={String(internalTransferCount)}
            hint="Linked-account / own top-up credits and matching debits"
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

function BucketDetailTable({
  title,
  rows,
  bucket,
}: {
  title: string;
  rows: ClassifiedRow[];
  bucket: "non_taxable" | "taxable" | "indeterminate";
}) {
  const total = rows.reduce((sum, row) => sum + Number(row.source.amount_lkr || 0), 0);
  return (
    <div className="space-y-3 rounded-xl border border-emerald-100 bg-emerald-50/30 p-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">
            {bucket === "non_taxable"
              ? "These credits are excluded from assessable income (not a tax deduction). Reason comes from Layer 1 / IRA mapping."
              : bucket === "taxable"
                ? "Layer-1 income codes included in assessable income."
                : "Unproven credits still counted in the presumptive taxable total until overridden."}
          </p>
        </div>
        <p className="text-sm font-semibold tabular-nums">
          {rows.length} row{rows.length === 1 ? "" : "s"} · {formatLkr(String(total))}
        </p>
      </div>
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="p-2 font-medium">Date</th>
              <th className="p-2 font-medium">Description</th>
              <th className="p-2 font-medium">Class</th>
              <th className="p-2 font-medium">Why</th>
              <th className="p-2 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.source.id} className="border-b align-top last:border-0">
                <td className="p-2 whitespace-nowrap">{row.source.tx_date}</td>
                <td className="p-2 max-w-[280px] whitespace-normal">{row.source.description}</td>
                <td className="p-2 whitespace-nowrap">{row.analysis.semantic_category}</td>
                <td className="p-2 max-w-[320px] text-xs text-muted-foreground">
                  {row.analysis.layer1_note ||
                    row.analysis.explanation ||
                    row.analysis.rule_reference ||
                    "—"}
                </td>
                <td className="p-2 tabular-nums whitespace-nowrap">
                  {formatLkr(row.source.amount_lkr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryMetric({
  label,
  value,
  hint,
  active,
  onClick,
}: {
  label: string;
  value: string;
  hint: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      {onClick ? (
        <p className="mt-2 text-xs font-medium text-sky-800">
          {active ? "Hide breakdown ▲" : "View contributing credits ▼"}
        </p>
      ) : null}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`rounded-xl border bg-white p-4 text-left transition-colors hover:bg-slate-50 ${
          active ? "border-sky-300 ring-1 ring-sky-200" : ""
        }`}
      >
        {body}
      </button>
    );
  }

  return <div className="rounded-xl border bg-white p-4">{body}</div>;
}

function TransactionClassificationRow({
  row,
  catalog,
  onClassChange,
  onAuditorEvidence,
  selected,
  onToggleSelect,
}: {
  row: ClassifiedRow;
  catalog: IncomeTypeCatalogResponse | null;
  onClassChange: (classKey: string) => void;
  onAuditorEvidence: (evidence: string) => void;
  selected?: boolean;
  onToggleSelect?: () => void;
}) {
  const status = row.analysis.taxability.taxability_status;
  const taxableAmount = Number(row.analysis.taxability.taxable_amount ?? 0);
  const showAssessable =
    row.source.direction === "CR" &&
    status !== "exempt" &&
    !Number.isNaN(taxableAmount) &&
    taxableAmount > 0;
  const certainty = row.analysis.certainty_tier;

  return (
    <div
      className={`rounded-xl border bg-white p-4 shadow-sm ${selected ? "border-sky-300 ring-1 ring-sky-200" : ""}`}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {onToggleSelect ? (
              <Checkbox
                checked={Boolean(selected)}
                onChange={() => onToggleSelect()}
                aria-label="Select row for bulk override"
              />
            ) : null}
            <span className="font-medium text-foreground">{row.source.tx_date}</span>
            <span>{row.source.direction}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusBadgeClass(status)}`}
            >
              {statusLabel(status)}
            </span>
            {certainty ? (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                {certainty.replaceAll("_", " ")}
              </span>
            ) : null}
            {row.analysis.class_source ? (
              <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px]">
                {row.analysis.class_source}
              </span>
            ) : null}
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
          {row.analysis.evidence_needed ? (
            <p className="text-xs text-amber-800">
              Needs evidence: {row.analysis.evidence_needed.replaceAll("_", " ")}
            </p>
          ) : null}
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

      <div className="mt-4 grid gap-4 border-t pt-4 md:grid-cols-2">
        <div>
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
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Auditor override
          </p>
          <Select
            value=""
            onChange={(event) => {
              if (event.target.value) {
                onAuditorEvidence(event.target.value);
              }
            }}
          >
            <option value="">Substantiate this row…</option>
            <option value="invoice">Invoice / service contract (taxable business)</option>
            <option value="loan">Loan agreement (non-taxable principal)</option>
            <option value="gift">Gift / family support (Sec 8)</option>
            <option value="shared_expense">Shared expense / reimbursement</option>
            <option value="own_transfer">Own-account transfer</option>
          </Select>
        </div>
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
  placeholder,
}: {
  value: string;
  options: IncomeTypeCatalogResponse["items"];
  onChange: (classKey: string) => void;
  placeholder?: string;
}) {
  if (options.length === 0 && !placeholder) {
    return <span>{value}</span>;
  }
  const selectOptions = options.some((item) => item.class_key === value) || !value
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
    <Select
      value={value}
      onChange={(event) => {
        if (event.target.value) {
          onChange(event.target.value);
        }
      }}
    >
      {placeholder ? <option value="">{placeholder}</option> : null}
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
  persistClassifications,
  isLocked,
  isClassifying,
  progress,
  onClassify,
}: {
  persistClassifications: boolean;
  isLocked: boolean;
  isClassifying: boolean;
  progress: { done: number; total: number };
  onClassify: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Button onClick={onClassify} disabled={isClassifying || !persistClassifications}>
        <Sparkles className="mr-2 h-4 w-4" />
        {isClassifying
          ? `Classifying ${progress.done}/${progress.total}...`
          : "Classify extracted rows"}
      </Button>
      {persistClassifications ? (
        <p className="text-sm text-muted-foreground">
          Results auto-save to the active taxpayer{isLocked ? " (locked)" : ""}.
        </p>
      ) : (
        <p className="text-sm text-amber-800">
          Select a taxpayer in the right panel before classifying.
        </p>
      )}
    </div>
  );
}
