import axios from "axios";

const BASE_URL =
  import.meta.env.VITE_TRANSACTION_SEMANTIC_API_BASE_URL?.trim() || "/api/v1";

const transactionSemanticApi = axios.create({
  baseURL: BASE_URL,
  timeout: 45_000,
});

transactionSemanticApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail =
      error?.response?.data?.detail ??
      error?.response?.data?.error ??
      error?.message ??
      "Unknown error";
    return Promise.reject(new Error(String(detail)));
  },
);

export interface UploadedDocumentSummary {
  document_id: string;
  filename: string;
  status: string;
  size_bytes: number;
  bank_detected: string | null;
  selected_parser: string | null;
  extracted_row_count: number;
}

export interface DocumentUploadResponse {
  document: UploadedDocumentSummary;
  extraction_run_id: string;
  metadata_extraction_run_id: string | null;
  router_extraction_run_id: string | null;
  message: string;
}

export interface DocumentStatusResponse {
  document_id: string;
  filename: string;
  content_type: string | null;
  status: string;
  bank_detected: string | null;
  selected_parser: string | null;
  extracted_row_count: number;
  extraction_run_status: string | null;
  extraction_error: string | null;
  extraction_warnings: string[];
}

export interface ExtractedTransactionItem {
  id: string;
  document_id: string;
  page_no: number | null;
  row_no: number | null;
  tx_date: string;
  description: string;
  debit: string | null;
  credit: string | null;
  balance: string | null;
  amount_lkr: string;
  direction: "CR" | "DR";
  confidence: number | null;
  is_flagged: boolean;
}

export interface ExtractedTransactionsResponse {
  document_id: string;
  total: number;
  limit: number;
  offset: number;
  transactions: ExtractedTransactionItem[];
}

export interface StatementTotalItem {
  id: string;
  document_id: string;
  opening_balance: string | null;
  closing_balance: string | null;
  total_debit: string | null;
  total_credit: string | null;
  currency: string | null;
  period_start: string | null;
  period_end: string | null;
}

export interface StatementTotalsResponse {
  document_id: string;
  totals: StatementTotalItem[];
}

export interface ReExtractResponse {
  document_id: string;
  status: string;
  bank_detected: string | null;
  selected_parser: string;
  extracted_row_count: number;
  router_extraction_run_id: string;
  extraction_run_id: string;
  message: string;
}

export interface PreviewExtractedTransactionItem {
  row_no: number | null;
  tx_date: string;
  description: string;
  amount_lkr: string;
  direction: "CR" | "DR";
  debit: string | null;
  credit: string | null;
  confidence: number | null;
}

export interface PreviewStatementTotalItem {
  total_debit: string | null;
  total_credit: string | null;
  currency: string | null;
  period_start: string | null;
  period_end: string | null;
}

export interface DocumentPreviewResponse {
  filename: string;
  content_type: string | null;
  file_type: string;
  bank_detected: string | null;
  selected_parser: string;
  extracted_count: number;
  warnings: string[];
  transactions: PreviewExtractedTransactionItem[];
  statement_totals: PreviewStatementTotalItem[];
}

export interface ExportFilters {
  date_from?: string;
  date_to?: string;
  bank_code?: string;
  direction?: "CR" | "DR";
  min_amount?: string;
  max_amount?: string;
  text_query?: string;
  limit?: number;
  offset?: number;
}

export interface ExportPreviewRow {
  document_id: string;
  filename: string;
  bank_detected: string | null;
  tx_id: string;
  tx_date: string;
  row_no: number | null;
  description: string;
  direction: "CR" | "DR";
  amount_lkr: string;
  debit: string | null;
  credit: string | null;
  balance: string | null;
  confidence: number | null;
}

export interface ExportPreviewResponse {
  total: number;
  limit: number;
  offset: number;
  rows: ExportPreviewRow[];
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await transactionSemanticApi.post<DocumentUploadResponse>(
    "/documents/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function previewDocument(
  file: File,
  bankCode?: string,
): Promise<DocumentPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await transactionSemanticApi.post<DocumentPreviewResponse>(
    "/documents/preview",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      params: bankCode?.trim() ? { bank_code: bankCode.trim().toUpperCase() } : undefined,
    },
  );
  return data;
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  const { data } = await transactionSemanticApi.get<DocumentStatusResponse>(
    `/documents/${documentId}/status`,
  );
  return data;
}

export async function getExtractedTransactions(
  documentId: string,
  limit = 500,
  offset = 0,
): Promise<ExtractedTransactionsResponse> {
  const { data } = await transactionSemanticApi.get<ExtractedTransactionsResponse>(
    `/documents/${documentId}/extracted-transactions`,
    { params: { limit, offset } },
  );
  return data;
}

export async function getStatementTotals(documentId: string): Promise<StatementTotalsResponse> {
  const { data } = await transactionSemanticApi.get<StatementTotalsResponse>(
    `/documents/${documentId}/statement-totals`,
  );
  return data;
}

export async function reExtractDocument(
  documentId: string,
  bankCode?: string,
): Promise<ReExtractResponse> {
  const { data } = await transactionSemanticApi.post<ReExtractResponse>(
    `/documents/${documentId}/re-extract`,
    undefined,
    { params: bankCode?.trim() ? { bank_code: bankCode.trim().toUpperCase() } : undefined },
  );
  return data;
}

export async function exportSingleDocumentCsv(documentId: string): Promise<Blob> {
  const { data } = await transactionSemanticApi.get(`/documents/${documentId}/export.csv`, {
    responseType: "blob",
  });
  return data as Blob;
}

export async function exportFilteredDocumentsCsv(filters: ExportFilters): Promise<Blob> {
  const { data } = await transactionSemanticApi.get("/documents/export.csv", {
    params: filters,
    responseType: "blob",
  });
  return data as Blob;
}

export async function previewFilteredDocuments(
  filters: ExportFilters,
): Promise<ExportPreviewResponse> {
  const { data } = await transactionSemanticApi.get<ExportPreviewResponse>(
    "/documents/export/preview",
    { params: filters },
  );
  return data;
}
