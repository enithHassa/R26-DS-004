import { useMemo, useState } from "react";
import { Database, FileUp, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getDocumentStatus,
  getExtractedTransactions,
  getStatementTotals,
  reExtractDocument,
  uploadDocument,
  type DocumentStatusResponse,
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
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isReExtracting, setIsReExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const hasLoadedDocument = documentId.trim().length > 0;

  const summaryCards = useMemo(
    () => [
      { label: "Document ID", value: status?.document_id ?? "-" },
      { label: "Status", value: status?.status ?? "-" },
      { label: "Detected Bank", value: status?.bank_detected ?? "unknown" },
      { label: "Selected Parser", value: status?.selected_parser ?? "-" },
      { label: "Extracted Rows", value: String(status?.extracted_row_count ?? 0) },
      { label: "Extraction Run", value: status?.extraction_run_status ?? "-" },
    ],
    [status],
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
      await refreshAll(resp.document.document_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setError(msg);
    } finally {
      setIsUploading(false);
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

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Transaction Document Extractor</h1>
        <p className="text-sm text-muted-foreground">
          Upload a bank statement soft copy, extract rows, review statement totals, and re-process if
          needed.
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
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={() => void handleUpload()} disabled={isUploading || !file}>
                {isUploading ? "Uploading..." : "Upload & Extract"}
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
    </div>
  );
}
