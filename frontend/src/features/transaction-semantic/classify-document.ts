/**
 * Shared helpers to classify one document's extracted rows (used by single-doc
 * UI and bulk "Classify selected").
 */

import {
  analyzeTransactionsBatch,
  getExtractedTransactions,
  type ExtractedTransactionItem,
} from "@/features/transaction-semantic/api";

export const CLASSIFY_BATCH_SIZE = 64;
const EXTRACT_PAGE_SIZE = 500;

export type ClassifyDocumentArgs = {
  documentId: string;
  bankCode?: string | null;
  financialProfileId: string;
  taxpayerId: string;
  onProgress?: (doneRows: number, totalRows: number) => void;
};

export type ClassifyDocumentResult = {
  documentId: string;
  rowCount: number;
};

/** Page through all extracted transactions for a document. */
export async function loadAllExtractedTransactions(
  documentId: string,
): Promise<ExtractedTransactionItem[]> {
  const all: ExtractedTransactionItem[] = [];
  let offset = 0;
  let total = Number.POSITIVE_INFINITY;
  while (offset < total) {
    const page = await getExtractedTransactions(documentId, EXTRACT_PAGE_SIZE, offset);
    total = page.total;
    all.push(...page.transactions);
    if (page.transactions.length === 0) break;
    offset += page.transactions.length;
  }
  return all;
}

/** Classify and persist all extracted rows for one document. */
export async function classifyDocumentExtractedRows(
  args: ClassifyDocumentArgs,
): Promise<ClassifyDocumentResult> {
  const transactions = await loadAllExtractedTransactions(args.documentId);
  if (transactions.length === 0) {
    return { documentId: args.documentId, rowCount: 0 };
  }

  args.onProgress?.(0, transactions.length);
  let done = 0;
  for (let offset = 0; offset < transactions.length; offset += CLASSIFY_BATCH_SIZE) {
    const chunk = transactions.slice(offset, offset + CLASSIFY_BATCH_SIZE);
    await analyzeTransactionsBatch({
      bank_code: args.bankCode ?? undefined,
      document_type: "bank_statement",
      document_id: args.documentId,
      financial_profile_id: args.financialProfileId,
      persist_classifications: true,
      taxpayer_id: args.taxpayerId,
      items: chunk.map((tx) => ({
        row_id: tx.id,
        raw_desc: tx.description,
        amount_lkr: tx.amount_lkr,
        tx_date: tx.tx_date,
        direction: tx.direction,
        facts: { taxpayer_id: args.taxpayerId },
      })),
    });
    done = offset + chunk.length;
    args.onProgress?.(done, transactions.length);
  }

  return { documentId: args.documentId, rowCount: transactions.length };
}
