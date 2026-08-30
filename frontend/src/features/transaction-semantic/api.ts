import axios from "axios";

const BASE_URL =
  import.meta.env.VITE_TRANSACTION_SEMANTIC_API_BASE_URL?.trim() || "/api/v1";

const transactionSemanticApi = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
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
  financial_profile_id?: string | null;
  tax_year?: string | null;
  statement_period_from?: string | null;
  statement_period_to?: string | null;
  submitted_by?: string;
  user_visible?: boolean;
  uploaded_at?: string | null;
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

export interface DocumentListResponse {
  items: UploadedDocumentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentRenameResponse {
  document: UploadedDocumentSummary;
  updated_related_transaction_count: number;
}

export async function listDocuments(
  limit = 50,
  offset = 0,
  financialProfileId?: string | null,
  options?: {
    userVisible?: boolean;
    pendingTaxpayerRelease?: boolean;
    submittedBy?: string;
  },
): Promise<DocumentListResponse> {
  const { data } = await transactionSemanticApi.get<DocumentListResponse>("/documents", {
    params: {
      limit,
      offset,
      ...(financialProfileId ? { financial_profile_id: financialProfileId } : {}),
      ...(options?.userVisible !== undefined ? { user_visible: options.userVisible } : {}),
      ...(options?.pendingTaxpayerRelease
        ? { pending_taxpayer_release: options.pendingTaxpayerRelease }
        : {}),
      ...(options?.submittedBy ? { submitted_by: options.submittedBy } : {}),
    },
  });
  return data;
}

export interface DocumentSubmitResponse {
  document: UploadedDocumentSummary;
  message: string;
}

export interface DocumentReleaseResponse {
  document: UploadedDocumentSummary;
  message: string;
}

export interface DocumentSaveResponse {
  document: UploadedDocumentSummary;
  message: string;
}

export async function saveDocument(
  file: File,
  financialProfileId: string,
  taxYear?: string | null,
): Promise<DocumentSaveResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await transactionSemanticApi.post<DocumentSaveResponse>(
    "/documents/save",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      params: {
        financial_profile_id: financialProfileId,
        ...(taxYear ? { tax_year: taxYear } : {}),
      },
    },
  );
  return data;
}

export async function submitDocumentToAuditor(
  file: File,
  financialProfileId: string,
  taxYear?: string | null,
): Promise<DocumentSubmitResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await transactionSemanticApi.post<DocumentSubmitResponse>(
    "/documents/submit",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      params: {
        financial_profile_id: financialProfileId,
        ...(taxYear ? { tax_year: taxYear } : {}),
      },
    },
  );
  return data;
}

export async function releaseDocumentToTaxpayer(
  documentId: string,
): Promise<DocumentReleaseResponse> {
  const { data } = await transactionSemanticApi.post<DocumentReleaseResponse>(
    `/documents/${documentId}/release-to-taxpayer`,
  );
  return data;
}

export async function renameDocument(
  documentId: string,
  filename: string,
): Promise<DocumentRenameResponse> {
  const { data } = await transactionSemanticApi.patch<DocumentRenameResponse>(
    `/documents/${documentId}`,
    { filename },
  );
  return data;
}

export async function uploadDocument(
  file: File,
  options?: { financialProfileId?: string | null; taxYear?: string | null },
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await transactionSemanticApi.post<DocumentUploadResponse>(
    "/documents/upload",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      params: {
        ...(options?.financialProfileId
          ? { financial_profile_id: options.financialProfileId }
          : {}),
        ...(options?.taxYear ? { tax_year: options.taxYear } : {}),
      },
    },
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

export interface ClassificationFacts {
  counterparty_type?: string | null;
  has_supporting_receipt?: boolean | null;
  taxpayer_id?: string | null;
  auditor_evidence?: string | null;
}

export interface AnalyzeTransactionRequest {
  raw_desc: string;
  amount_lkr: string;
  tx_date: string;
  direction: "CR" | "DR";
  bank_code?: string | null;
  document_type?: string | null;
  facts?: ClassificationFacts | null;
  persist?: boolean;
}

export interface TaxabilityOutput {
  tx_id: string;
  taxability_status: "taxable" | "exempt" | "partially_taxable" | "unknown";
  taxable_amount: string | null;
  confidence: number | null;
  model_version: string | null;
  treatment: string | null;
  taxable_fraction: string | null;
}

export interface NarrativeContextHit {
  class_key: string;
  score: number;
  description: string;
  default_taxability_status: string;
}

export interface AnalyzeTransactionResponse {
  transaction_id: string;
  semantic_category: string;
  economic_event: string | null;
  tax_rule_code: string | null;
  taxability: TaxabilityOutput;
  confidence_report: {
    top_label: string;
    top_probability: number;
    calibrated_probability: number;
    is_ood: boolean;
  };
  taxonomy_version: string;
  rulebook_version: string;
  decision_mode: string;
  rule_reference: string;
  explanation: string;
  review_reason: string | null;
  condition_id_matched: string | null;
  model_semantic_category: string | null;
  class_source: "model" | "narrative" | "manual" | "deterministic" | string;
  narrative_interpretation: string | null;
  narrative_hits: NarrativeContextHit[];
  certainty_tier?: "guaranteed_taxable" | "guaranteed_non_taxable" | "indeterminate" | string | null;
  intent_tag?: string | null;
  channel?: string | null;
  evidence_needed?: string | null;
  layer1_note?: string | null;
}

export interface IncomeTypeCatalogItem {
  class_key: string;
  group: string;
  description: string;
  tax_rule_code: string;
  default_taxability_status: string;
  default_taxable_fraction: number;
  treatment: string | null;
  rule_reference: string;
  explanation: string;
  is_conditional: boolean;
}

export interface IncomeTypeCatalogResponse {
  taxonomy_version: string;
  rulebook_version: string;
  items: IncomeTypeCatalogItem[];
  by_taxability_status: Record<string, IncomeTypeCatalogItem[]>;
}

export interface TaxableIncomeLineItem {
  class_key: string;
  tax_rule_code: string | null;
  taxability_status: string;
  transaction_count: number;
  gross_amount_lkr: string;
  taxable_amount_lkr: string;
}

export interface TaxableIncomeSummaryRequest {
  date_from: string;
  date_to: string;
  bank_code?: string | null;
}

export interface TaxableIncomeSummaryResponse {
  date_from: string;
  date_to: string;
  total_taxable_lkr: string;
  total_excluded_lkr: string;
  review_count: number;
  transaction_count: number;
  taxable_lines: TaxableIncomeLineItem[];
  non_taxable_lines: TaxableIncomeLineItem[];
  review_lines: TaxableIncomeLineItem[];
}

export interface AnalyzeBatchItemRequest {
  row_id?: string | null;
  raw_desc: string;
  amount_lkr: string;
  tx_date: string;
  direction: "CR" | "DR";
  facts?: ClassificationFacts | null;
}

export interface AnalyzeBatchRequest {
  bank_code?: string | null;
  document_type?: string | null;
  document_id?: string | null;
  persist?: boolean;
  persist_classifications?: boolean;
  financial_profile_id?: string | null;
  taxpayer_id?: string | null;
  items: AnalyzeBatchItemRequest[];
}

export interface AnalyzeBatchItemResponse {
  row_id: string | null;
  result: AnalyzeTransactionResponse;
}

export interface InflowSummary {
  guaranteed_taxable_inflows_lkr: string;
  guaranteed_non_taxable_inflows_lkr: string;
  indeterminate_inflows_lkr: string;
  outflow_lkr: string;
  credit_count: number;
  debit_count: number;
  indeterminate_credit_count: number;
  potential_assessable_if_indet_is_income_lkr: string;
  exceeds_annual_personal_relief_if_indet_is_income: boolean;
  exceeds_monthly_relief_equivalent_if_indet_is_income: boolean;
  personal_relief_annual_lkr: string;
  personal_relief_monthly_equivalent_lkr: string;
  relief_hint: string;
}

export interface AnalyzeBatchResponse {
  results: AnalyzeBatchItemResponse[];
  processed_count: number;
  inflow_summary?: InflowSummary | null;
}

export interface ActivitySummaryItemRequest {
  row_id?: string | null;
  raw_desc: string;
  amount_lkr: string;
  tx_date?: string | null;
  direction: "CR" | "DR";
}

export interface ActivitySummaryRequest {
  items: ActivitySummaryItemRequest[];
}

export interface ActivitySummaryMember {
  row_id: string | null;
  tx_date: string | null;
  description: string;
  direction: "CR" | "DR";
  amount_lkr: string;
}

export interface ActivitySummaryGroup {
  group_key: string;
  label: string;
  hint: string;
  direction: "CR" | "DR";
  intent_tag: string;
  merchant_family: string | null;
  count: number;
  total_lkr: string;
  members: ActivitySummaryMember[];
}

export interface ActivitySummaryResponse {
  group_count: number;
  transaction_count: number;
  groups: ActivitySummaryGroup[];
}

export async function summarizeActivity(
  body: ActivitySummaryRequest,
): Promise<ActivitySummaryResponse> {
  const { data } = await transactionSemanticApi.post<ActivitySummaryResponse>(
    "/transactions/activity-summary",
    body,
  );
  return data;
}

export async function getDocumentClassifications(
  documentId: string,
  financialProfileId?: string | null,
): Promise<DocumentClassificationsResponse> {
  const { data } = await transactionSemanticApi.get<DocumentClassificationsResponse>(
    `/documents/${documentId}/classifications`,
    {
      params: financialProfileId ? { financial_profile_id: financialProfileId } : undefined,
    },
  );
  return data;
}

export interface DocumentClassificationItem {
  extracted_transaction_id: string;
  result: AnalyzeTransactionResponse;
}

export interface DocumentClassificationsResponse {
  document_id: string;
  financial_profile_id: string | null;
  items: DocumentClassificationItem[];
  total: number;
}

export async function analyzeTransaction(
  body: AnalyzeTransactionRequest,
): Promise<AnalyzeTransactionResponse> {
  const { data } = await transactionSemanticApi.post<AnalyzeTransactionResponse>(
    "/transactions/analyze",
    body,
  );
  return data;
}

export async function analyzeTransactionsBatch(
  body: AnalyzeBatchRequest,
): Promise<AnalyzeBatchResponse> {
  const { data } = await transactionSemanticApi.post<AnalyzeBatchResponse>(
    "/transactions/analyze-batch",
    body,
    { timeout: 300_000 },
  );
  return data;
}

export interface ApplyClassBatchItemRequest {
  row_id?: string | null;
  raw_desc: string;
  amount_lkr: string;
  tx_date: string;
  direction: "CR" | "DR";
  class_key: string;
  facts?: ClassificationFacts | null;
  model_semantic_category?: string | null;
}

export interface ApplyClassBatchRequest {
  bank_code?: string | null;
  document_type?: string | null;
  document_id?: string | null;
  financial_profile_id?: string | null;
  persist_classifications?: boolean;
  items: ApplyClassBatchItemRequest[];
}

export async function applyTransactionClassBatch(
  body: ApplyClassBatchRequest,
): Promise<AnalyzeBatchResponse> {
  const { data } = await transactionSemanticApi.post<AnalyzeBatchResponse>(
    "/transactions/apply-class-batch",
    body,
  );
  return data;
}

export async function getIncomeTypeCatalog(): Promise<IncomeTypeCatalogResponse> {
  const { data } = await transactionSemanticApi.get<IncomeTypeCatalogResponse>(
    "/taxonomy/income-types",
  );
  return data;
}

export async function summarizeTaxableIncome(
  body: TaxableIncomeSummaryRequest,
): Promise<TaxableIncomeSummaryResponse> {
  const { data } = await transactionSemanticApi.post<TaxableIncomeSummaryResponse>(
    "/taxable-income/summary",
    body,
  );
  return data;
}
