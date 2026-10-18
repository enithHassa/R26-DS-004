"""Ingestion API schemas (upload, status, extracted rows)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.shared.schemas.enums import TxnDirection


class UploadedDocumentSummary(BaseModel):
    document_id: UUID
    filename: str
    status: str
    size_bytes: int
    bank_detected: str | None = None
    selected_parser: str | None = None
    extracted_row_count: int = 0
    financial_profile_id: UUID | None = None
    tax_year: str | None = None
    statement_period_from: date | None = None
    statement_period_to: date | None = None
    submitted_by: str = "auditor"
    user_visible: bool = False
    uploaded_at: datetime | None = None


class DocumentSubmitResponse(BaseModel):
    document: UploadedDocumentSummary
    message: str = "Statement submitted to your tax adviser for review."


class DocumentSaveResponse(BaseModel):
    document: UploadedDocumentSummary
    message: str = "Document saved. Select it from the library and click Extract when ready."


class DocumentReleaseResponse(BaseModel):
    document: UploadedDocumentSummary
    message: str = "Document released to taxpayer portal."


class DocumentUploadResponse(BaseModel):
    document: UploadedDocumentSummary
    extraction_run_id: UUID
    metadata_extraction_run_id: UUID | None = None
    router_extraction_run_id: UUID | None = None
    message: str = "Document uploaded; routed and extracted (Phase 3)."


class DocumentBatchUploadResponse(BaseModel):
    documents: list[UploadedDocumentSummary] = Field(default_factory=list)
    extraction_run_ids: list[UUID] = Field(default_factory=list)
    uploaded_count: int


class DocumentListResponse(BaseModel):
    items: list[UploadedDocumentSummary] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DocumentRenameRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)


class DocumentRenameResponse(BaseModel):
    document: UploadedDocumentSummary
    updated_related_transaction_count: int = 0


class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    filename: str
    message: str = "Document removed."


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    filename: str
    content_type: str | None
    status: str
    bank_detected: str | None
    size_bytes: int
    uploaded_at: datetime
    updated_at: datetime
    latest_run_id: UUID | None = None
    latest_run_parser_name: str | None = None
    latest_run_status: str | None = None
    latest_run_started_at: datetime | None = None
    latest_run_finished_at: datetime | None = None
    selected_parser: str | None = None
    bank_detection_confidence: float | None = None
    extracted_row_count: int = 0
    extraction_run_status: str | None = None
    extraction_run_parser: str | None = None
    extraction_error: str | None = None
    extraction_warnings: list[str] = Field(default_factory=list)


class ExtractedTransactionItem(BaseModel):
    """One row from ``extracted_transactions`` for a document."""

    id: UUID
    document_id: UUID
    page_no: int | None = None
    row_no: int | None = None
    tx_date: date
    description: str
    reference_no: str | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal | None = None
    amount_lkr: Decimal
    direction: TxnDirection
    confidence: float | None = None
    raw_row_json: dict | None = None
    is_flagged: bool = False


class ExtractedTransactionsPageResponse(BaseModel):
    document_id: UUID
    total: int
    limit: int
    offset: int
    transactions: list[ExtractedTransactionItem] = Field(default_factory=list)


class StatementTotalItem(BaseModel):
    """Statement-level roll-up extracted with the document (e.g. PDF period + totals)."""

    id: UUID
    document_id: UUID
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    total_debit: Decimal | None = None
    total_credit: Decimal | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None


class StatementTotalsResponse(BaseModel):
    document_id: UUID
    totals: list[StatementTotalItem] = Field(default_factory=list)


class ReExtractDocumentResponse(BaseModel):
    document_id: UUID
    status: str
    bank_detected: str | None
    selected_parser: str
    extracted_row_count: int
    router_extraction_run_id: UUID
    extraction_run_id: UUID
    message: str = "Re-processed from stored file; transaction list and totals were replaced."


class PreviewExtractedTransactionItem(BaseModel):
    row_no: int | None = None
    tx_date: date
    description: str
    amount_lkr: Decimal
    direction: TxnDirection
    debit: Decimal | None = None
    credit: Decimal | None = None
    confidence: float | None = None


class PreviewStatementTotalItem(BaseModel):
    total_debit: Decimal | None = None
    total_credit: Decimal | None = None
    currency: str | None = "LKR"
    period_start: date | None = None
    period_end: date | None = None


class DocumentPreviewResponse(BaseModel):
    filename: str
    content_type: str | None = None
    file_type: str
    bank_detected: str | None = None
    selected_parser: str
    extracted_count: int
    warnings: list[str] = Field(default_factory=list)
    transactions: list[PreviewExtractedTransactionItem] = Field(default_factory=list)
    statement_totals: list[PreviewStatementTotalItem] = Field(default_factory=list)


class ExportPreviewRow(BaseModel):
    document_id: UUID
    filename: str
    bank_detected: str | None = None
    tx_id: UUID
    tx_date: date
    row_no: int | None = None
    description: str
    direction: TxnDirection
    amount_lkr: Decimal
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal | None = None
    confidence: float | None = None


class ExportPreviewResponse(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[ExportPreviewRow] = Field(default_factory=list)
