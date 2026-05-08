import { useMemo, useState } from "react";
import { Database, FileUp, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  exportFilteredDocumentsCsv,
  exportSingleDocumentCsv,
  getDocumentStatus,
  getExtractedTransactions,
  getStatementTotals,
  previewFilteredDocuments,
  previewDocument,
  reExtractDocument,
  uploadDocument,
  type DocumentStatusResponse,
  type DocumentPreviewResponse,
  type ExportPreviewRow,
  type ExtractedTransactionItem,
  type StatementTotalItem,
} from "@/features/transaction-semantic/api";

function formatMoney(value: string | null): string {
  if (value === null) return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 2,
  }).format(n);
}

export function TransactionDocumentExtractionPage() {
  const [file, setFile] = useState<File | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [bankCodeOverride, setBankCodeOverride] = useState("");
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [transactions, setTransactions] = useState<ExtractedTransactionItem[]>([]);
  const [statementTotals, setStatementTotals] = useState<StatementTotalItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isReExtracting, setIsReExtracting] = useState(false);
  const [isExportingDoc, setIsExportingDoc] = useState(false);
  const [isExportingFiltered, setIsExportingFiltered] = useState(false);
  const [isPreviewingFiltered, setIsPreviewingFiltered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [previewMeta, setPreviewMeta] = useState<DocumentPreviewResponse | null>(null);
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterBank, setFilterBank] = useState("");
  const [filterDirection, setFilterDirection] = useState("");
  const [filterMinAmount, setFilterMinAmount] = useState("");
  const [filterMaxAmount, setFilterMaxAmount] = useState("");
  const [filterText, setFilterText] = useState("");
  const [exportPreviewRows, setExportPreviewRows] = useState<ExportPreviewRow[]>([]);
  const [exportPreviewTotal, setExportPreviewTotal] = useState(0);

  const hasLoadedDocument = documentId.trim().length > 0;

  const summaryCards = useMemo(
    () => [
      { label: "Document ID", value: status?.document_id ?? "-" },
      { label: "Status", value: status?.status ?? (previewMeta ? "preview_only" : "-") },
      {
        label: "Detected Bank",
        value: status?.bank_detected ?? previewMeta?.bank_detected ?? "unknown",
      },
      {
        label: "Selected Parser",
        value: status?.selected_parser ?? previewMeta?.selected_parser ?? "-",
      },
      {
        label: "Extracted Rows",
        value: String(status?.extracted_row_count ?? previewMeta?.extracted_count ?? 0),
      },
      { label: "Extraction Run", value: status?.extraction_run_status ?? (previewMeta ? "preview" : "-") },
    ],
    [previewMeta, status],
  );

  async function refreshAll(id: string): Promise<void> {
    setIsRefreshing(true);
    setError(null);
    try {
      const [statusResp, txResp, totalsResp] = await Promise.all([
        getDocumentStatus(id),
        getExtractedTransactions(id, 500, 0),
        getStatementTotals(id),
      ]);
      setStatus(statusResp);
      setTransactions(txResp.transactions);
      setStatementTotals(totalsResp.totals);
      setPreviewMeta(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load document details.";
      setError(msg);
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleUpload(): Promise<void> {
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setIsUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const resp = await uploadDocument(file);
      setDocumentId(resp.document.document_id);
      setSuccess(resp.message);
      setPreviewMeta(null);
      await refreshAll(resp.document.document_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  }

  async function handlePreview(): Promise<void> {
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setIsPreviewing(true);
    setError(null);
    setSuccess(null);
    try {
      const preview = await previewDocument(file, bankCodeOverride);
      setPreviewMeta(preview);
      setStatus(null);
      setDocumentId("");
      setTransactions(
        preview.transactions.map((row, idx) => ({
          id: `preview-${idx}`,
          document_id: "preview",
          page_no: null,
          row_no: row.row_no,
          tx_date: row.tx_date,
          description: row.description,
          debit: row.debit,
          credit: row.credit,
          balance: null,
          amount_lkr: row.amount_lkr,
          direction: row.direction,
          confidence: row.confidence,
          is_flagged: false,
        })),
      );
      setStatementTotals(
        preview.statement_totals.map((row, idx) => ({
          id: `preview-total-${idx}`,
          document_id: "preview",
          opening_balance: null,
          closing_balance: null,
          total_debit: row.total_debit,
          total_credit: row.total_credit,
          currency: row.currency,
          period_start: row.period_start,
          period_end: row.period_end,
        })),
      );
      setSuccess("Preview generated. Click 'Save Extracted Data' to persist.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Preview failed.";
      setError(msg);
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleLoadById(): Promise<void> {
    if (!hasLoadedDocument) {
      setError("Enter a document ID.");
      return;
    }
    setSuccess(null);
    await refreshAll(documentId.trim());
  }

  async function handleReExtract(): Promise<void> {
    if (!hasLoadedDocument) {
      setError("Load a document first.");
      return;
    }
    setIsReExtracting(true);
    setError(null);
    setSuccess(null);
    try {
      const resp = await reExtractDocument(documentId.trim(), bankCodeOverride);
      setSuccess(resp.message);
      await refreshAll(resp.document_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Re-extract failed.";
      setError(msg);
    } finally {
      setIsReExtracting(false);
    }
  }

  function triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExportCurrentDocument(): Promise<void> {
    if (!hasLoadedDocument) {
      setError("Load a document first.");
      return;
    }
    setIsExportingDoc(true);
    setError(null);
    try {
      const blob = await exportSingleDocumentCsv(documentId.trim());
      triggerDownload(blob, `document_${documentId.trim()}_extracted.csv`);
      setSuccess("Current document export downloaded.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Document export failed.";
      setError(msg);
    } finally {
      setIsExportingDoc(false);
    }
  }

  async function handleExportFiltered(): Promise<void> {
    setIsExportingFiltered(true);
    setError(null);
    try {
      const blob = await exportFilteredDocumentsCsv({
        date_from: filterDateFrom || undefined,
        date_to: filterDateTo || undefined,
        bank_code: filterBank || undefined,
        direction: (filterDirection as "CR" | "DR") || undefined,
        min_amount: filterMinAmount || undefined,
        max_amount: filterMaxAmount || undefined,
        text_query: filterText || undefined,
      });
      triggerDownload(blob, "documents_filtered_export.csv");
      setSuccess("Filtered export downloaded.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Filtered export failed.";
      setError(msg);
    } finally {
      setIsExportingFiltered(false);
    }
  }

  async function handlePreviewFilteredExport(): Promise<void> {
    setIsPreviewingFiltered(true);
    setError(null);
    try {
      const preview = await previewFilteredDocuments({
        date_from: filterDateFrom || undefined,
        date_to: filterDateTo || undefined,
        bank_code: filterBank || undefined,
        direction: (filterDirection as "CR" | "DR") || undefined,
        min_amount: filterMinAmount || undefined,
        max_amount: filterMaxAmount || undefined,
        text_query: filterText || undefined,
        limit: 100,
        offset: 0,
      });
      setExportPreviewRows(preview.rows);
      setExportPreviewTotal(preview.total);
      setSuccess(`Preview loaded: ${preview.total} matching row(s).`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Preview failed.";
      setError(msg);
    } finally {
      setIsPreviewingFiltered(false);
    }
  }

  function handleClearFilters(): void {
    setFilterDateFrom("");
    setFilterDateTo("");
    setFilterBank("");
    setFilterDirection("");
    setFilterMinAmount("");
    setFilterMaxAmount("");
    setFilterText("");
    setExportPreviewRows([]);
    setExportPreviewTotal(0);
    setError(null);
    setSuccess("Filters cleared.");
  }

  function handleHidePreview(): void {
    setExportPreviewRows([]);
    setExportPreviewTotal(0);
    setError(null);
    setSuccess("Preview hidden.");
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Transaction Document Extractor</h1>
        <p className="text-sm text-muted-foreground">
          Upload a bank statement (PDF, CSV, Excel, text, or PNG/JPG via OCR), extract rows, review
          statement totals, and re-process if needed.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileUp className="h-4 w-4" /> Upload & Process
          </CardTitle>
          <CardDescription>
            Uses backend routes: upload, status, extracted-transactions, statement-totals, and
            re-extract.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="statement-file">Statement file</Label>
              <Input
                id="statement-file"
                type="file"
                accept=".pdf,.csv,.xlsx,.xls,.txt,.png,.jpg,.jpeg,image/png,image/jpeg,application/pdf,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => void handlePreview()} disabled={isPreviewing || !file}>
                {isPreviewing ? "Previewing..." : "Preview Extract"}
              </Button>
              <Button onClick={() => void handleUpload()} disabled={isUploading || !file}>
                {isUploading ? "Saving..." : "Save Extracted Data"}
              </Button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Label htmlFor="document-id">Existing document ID</Label>
              <Input
                id="document-id"
                value={documentId}
                onChange={(e) => setDocumentId(e.target.value)}
                placeholder="Paste document UUID to load previous extraction"
              />
            </div>
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => void handleLoadById()}>
                Load
              </Button>
              <Button
                variant="outline"
                onClick={() => void refreshAll(documentId.trim())}
                disabled={!hasLoadedDocument || isRefreshing}
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                {isRefreshing ? "Refreshing..." : "Refresh"}
              </Button>
            </div>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {summaryCards.map((card) => (
          <Card key={card.label}>
            <CardHeader className="pb-2">
              <CardDescription>{card.label}</CardDescription>
              <CardTitle className="text-base break-all">{card.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-4 w-4" /> Statement Totals
          </CardTitle>
          <CardDescription>Summary rows extracted from the statement.</CardDescription>
        </CardHeader>
        <CardContent>
          {statementTotals.length === 0 ? (
            <p className="text-sm text-muted-foreground">No statement totals available yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Period</th>
                    <th className="p-2">Opening</th>
                    <th className="p-2">Closing</th>
                    <th className="p-2">Total Debit</th>
                    <th className="p-2">Total Credit</th>
                    <th className="p-2">Currency</th>
                  </tr>
                </thead>
                <tbody>
                  {statementTotals.map((row) => (
                    <tr key={row.id} className="border-b align-top">
                      <td className="p-2">
                        {row.period_start ?? "-"} to {row.period_end ?? "-"}
                      </td>
                      <td className="p-2">{formatMoney(row.opening_balance)}</td>
                      <td className="p-2">{formatMoney(row.closing_balance)}</td>
                      <td className="p-2">{formatMoney(row.total_debit)}</td>
                      <td className="p-2">{formatMoney(row.total_credit)}</td>
                      <td className="p-2">{row.currency ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Extracted Transactions</CardTitle>
          <CardDescription>
            Parsed rows from your uploaded document. Showing up to first 500 rows.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No extracted transactions found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[950px] text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">#</th>
                    <th className="p-2">Date</th>
                    <th className="p-2">Description</th>
                    <th className="p-2">Direction</th>
                    <th className="p-2">Amount</th>
                    <th className="p-2">Debit</th>
                    <th className="p-2">Credit</th>
                    <th className="p-2">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="border-b align-top">
                      <td className="p-2">{tx.row_no ?? "-"}</td>
                      <td className="p-2">{tx.tx_date}</td>
                      <td className="p-2 max-w-[420px] whitespace-normal">{tx.description}</td>
                      <td className="p-2">{tx.direction}</td>
                      <td className="p-2">{formatMoney(tx.amount_lkr)}</td>
                      <td className="p-2">{formatMoney(tx.debit)}</td>
                      <td className="p-2">{formatMoney(tx.credit)}</td>
                      <td className="p-2">{tx.confidence?.toFixed(2) ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Re-extract</CardTitle>
          <CardDescription>
            Reprocess the already uploaded file (no need to upload again). You can force a bank code
            when routing is wrong.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-[240px_auto]">
          <div className="space-y-2">
            <Label htmlFor="bank-code">Optional bank code override</Label>
            <Input
              id="bank-code"
              value={bankCodeOverride}
              onChange={(e) => setBankCodeOverride(e.target.value)}
              placeholder="NTB / SAMPATH / ..."
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={() => void handleReExtract()}
              disabled={!hasLoadedDocument || isReExtracting}
            >
              {isReExtracting ? "Re-processing..." : "Re-extract Document"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Export</CardTitle>
          <CardDescription>
            Preview filtered rows first, then download CSV when it looks correct.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => void handleExportCurrentDocument()}
              disabled={!hasLoadedDocument || isExportingDoc}
            >
              {isExportingDoc ? "Exporting..." : "Export Current Document CSV"}
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="space-y-1">
              <Label htmlFor="f-date-from">From date</Label>
              <Input id="f-date-from" type="date" value={filterDateFrom} onChange={(e) => setFilterDateFrom(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-date-to">To date</Label>
              <Input id="f-date-to" type="date" value={filterDateTo} onChange={(e) => setFilterDateTo(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-bank">Bank</Label>
              <Input id="f-bank" value={filterBank} onChange={(e) => setFilterBank(e.target.value)} placeholder="NTB / SAMPATH" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-direction">Direction</Label>
              <Input id="f-direction" value={filterDirection} onChange={(e) => setFilterDirection(e.target.value.toUpperCase())} placeholder="CR or DR" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-min">Min amount</Label>
              <Input id="f-min" value={filterMinAmount} onChange={(e) => setFilterMinAmount(e.target.value)} placeholder="0.00" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-max">Max amount</Label>
              <Input id="f-max" value={filterMaxAmount} onChange={(e) => setFilterMaxAmount(e.target.value)} placeholder="500000.00" />
            </div>
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor="f-text">Description contains</Label>
              <Input id="f-text" value={filterText} onChange={(e) => setFilterText(e.target.value)} placeholder="CEFTS / salary / refund ..." />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void handlePreviewFilteredExport()} disabled={isPreviewingFiltered}>
              {isPreviewingFiltered ? "Previewing..." : "Preview Filtered Data"}
            </Button>
            <Button onClick={() => void handleExportFiltered()} disabled={isExportingFiltered}>
              {isExportingFiltered ? "Exporting..." : "Export Filtered CSV"}
            </Button>
            <Button variant="secondary" onClick={handleClearFilters}>
              Clear Filters
            </Button>
            <Button variant="ghost" onClick={handleHidePreview} disabled={exportPreviewRows.length === 0}>
              Hide Preview
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Preview rows shown: {exportPreviewRows.length} / total matches: {exportPreviewTotal}
          </p>
          {exportPreviewRows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Document</th>
                    <th className="p-2">Date</th>
                    <th className="p-2">Description</th>
                    <th className="p-2">Dir</th>
                    <th className="p-2">Amount</th>
                    <th className="p-2">Bank</th>
                  </tr>
                </thead>
                <tbody>
                  {exportPreviewRows.map((row) => (
                    <tr key={row.tx_id} className="border-b align-top">
                      <td className="p-2">{row.filename}</td>
                      <td className="p-2">{row.tx_date}</td>
                      <td className="p-2 max-w-[480px] whitespace-normal">{row.description}</td>
                      <td className="p-2">{row.direction}</td>
                      <td className="p-2">{formatMoney(row.amount_lkr)}</td>
                      <td className="p-2">{row.bank_detected ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
