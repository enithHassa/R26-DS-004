import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DocumentListPanel } from "@/features/transaction-semantic/components/document-list-panel";
import { TransactionTaxClassificationPanel } from "@/features/transaction-semantic/components/transaction-tax-classification-panel";
import {
  getDocumentStatus,
  getExtractedTransactions,
  type DocumentStatusResponse,
  type ExtractedTransactionItem,
} from "@/features/transaction-semantic/api";

export function TransactionTaxClassificationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [documentId, setDocumentId] = useState(searchParams.get("document") ?? "");
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [transactions, setTransactions] = useState<ExtractedTransactionItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDocument(id: string): Promise<void> {
    const trimmed = id.trim();
    if (!trimmed) {
      setStatus(null);
      setTransactions([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [statusResp, txResp] = await Promise.all([
        getDocumentStatus(trimmed),
        getExtractedTransactions(trimmed, 500, 0),
      ]);
      setStatus(statusResp);
      setTransactions(txResp.transactions);
    } catch (err) {
      setStatus(null);
      setTransactions([]);
      setError(err instanceof Error ? err.message : "Failed to load document for classification.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const selected = searchParams.get("document") ?? "";
    setDocumentId(selected);
    if (selected) {
      void loadDocument(selected);
    } else {
      setStatus(null);
      setTransactions([]);
    }
  }, [searchParams]);

  function handleSelectDocument(nextId: string): void {
    setSearchParams({ document: nextId });
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Tax classification</h1>
        <p className="text-sm text-muted-foreground">
          Choose a saved document, then classify its extracted rows as taxable, exempt, or needs review.
        </p>
      </div>

      <DocumentListPanel
        selectedDocumentId={documentId || null}
        onSelect={handleSelectDocument}
        onRenamed={(id) => {
          if (id === documentId) {
            void loadDocument(id);
          }
        }}
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {documentId ? (
        <Card>
          <CardHeader>
            <CardTitle>{status?.filename ?? "Selected document"}</CardTitle>
            <CardDescription>
              {isLoading
                ? "Loading extracted rows..."
                : `${transactions.length} extracted row(s) ready for classification.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TransactionTaxClassificationPanel
              transactions={transactions}
              bankCode={status?.bank_detected}
              documentId={documentId}
              documentLabel={status?.filename}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-8 text-sm text-muted-foreground">
            Select a saved document to run tax classification.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
