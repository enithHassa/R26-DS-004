"""Transaction Semantic component — FastAPI entry point.

Phase 0 stub: `/health`, `/v1/transactions/analyze`, and
``GET /api/v1/users/{user_id}/income-snapshot`` (aggregate stub for Component B Option B).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile
from loguru import logger
from sqlalchemy.orm import Session

from backend.shared.config.settings import settings
from backend.shared.config.database import get_db
from backend.shared.logging import configure_logging
from backend.shared.middleware.request_id import RequestIDMiddleware
from backend.shared.db.enums import TxnDirection as DBTxnDirection
from backend.shared.db.transaction import Transaction as TransactionModel
from backend.shared.schemas import (
    AnalyzeTransactionRequest,
    AnalyzeTransactionResponse,
    ConfidenceReport,
    EvidenceChain,
    EvidenceStep,
    IncomeSnapshotV1,
    TaxabilityOutput,
    TaxabilityStatus,
    Transaction,
)
from backend.shared.schemas.enums import TxnDirection as SchemaTxnDirection
from schemas import DocumentExtractResponse
from schemas import (
    DocumentBatchUploadResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    ExtractedTransactionItem,
    ExtractedTransactionsPageResponse,
    UploadedDocumentSummary,
)
from services import (
    UnsupportedDocumentTypeError,
    extract_transactions_from_document,
    get_document_status_snapshot,
    ingest_document_metadata,
    list_document_extracted_transactions,
)

configure_logging(settings)

app = FastAPI(
    title="Transaction Semantic Reasoning API",
    description="Explainable taxable-income inference from bank transactions (Component 1).",
    version="0.1.0",
)
app.add_middleware(RequestIDMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("health_check_ok")
    return {"status": "ok"}


@app.post("/v1/transactions/analyze", response_model=AnalyzeTransactionResponse)
def analyze_transaction(payload: AnalyzeTransactionRequest) -> AnalyzeTransactionResponse:
    """Stub analysis — replace with preprocessor + classifier + rule map (WP4–WP7)."""
    _ = payload  # unused until pipeline exists
    tid = uuid4()
    logger.bind(transaction_id=str(tid)).info(
        "analyze_transaction_stub_completed semantic_category=salary",
    )
    return AnalyzeTransactionResponse(
        transaction_id=tid,
        semantic_category="salary",
        economic_event="recurring_income",
        tax_rule_code="IRD_SEC_123_STUB",
        taxability=TaxabilityOutput(
            tx_id=tid,
            taxability_status=TaxabilityStatus.TAXABLE,
            taxable_amount=Decimal("45000.00"),
            confidence=0.87,
            evidence=EvidenceChain(
                steps=[
                    EvidenceStep(
                        step="normalize",
                        detail="Whitespace stripped; bank ref masked (stub).",
                    ),
                    EvidenceStep(
                        step="semantic_classifier",
                        detail="Predicted category=salary with softmax prob 0.87 (stub).",
                    ),
                    EvidenceStep(
                        step="tax_rule_mapping",
                        detail="Mapped to stub IRD clause placeholder (stub).",
                    ),
                ],
            ),
            model_version="stub-0.1.0",
            model_run_id=None,
        ),
        confidence_report=ConfidenceReport(
            top_label="salary",
            top_probability=0.87,
            calibrated_probability=0.87,
            entropy=None,
            mc_dropout_variance=None,
            is_ood=False,
        ),
    )


@app.post("/v1/documents/extract", response_model=DocumentExtractResponse)
async def extract_document_transactions(
    file: UploadFile = File(...),
    bank_code: str | None = Query(default=None, max_length=16),
    persist: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> DocumentExtractResponse:
    """Extract transaction rows from uploaded bank documents and optionally persist."""
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        outcome = extract_transactions_from_document(
            filename=file.filename or "uploaded_document",
            content_type=file.content_type,
            payload=payload,
            bank_code_hint=bank_code,
        )
        extracted = outcome.rows
        warnings = outcome.warnings
        file_type = outcome.file_type
        ocr_pending = outcome.ocr_pending
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    persisted_models: list[TransactionModel] = []
    if persist and extracted:
        for row in extracted:
            model = TransactionModel(
                raw_desc=row.raw_desc,
                normalized_desc=None,
                amount_lkr=row.amount_lkr,
                tx_date=date.fromisoformat(row.tx_date),
                direction=DBTxnDirection(row.direction.value),
                bank_code=row.bank_code or bank_code,
                source_type="document_upload",
                raw_payload={
                    "source_filename": file.filename,
                    "content_type": file.content_type,
                    "row_index": row.row_index,
                    "parse_confidence": row.parse_confidence,
                },
            )
            db.add(model)
            persisted_models.append(model)
        db.commit()
        for model in persisted_models:
            db.refresh(model)

    logger.bind(
        document=file.filename,
        extracted_count=len(extracted),
        persisted_count=len(persisted_models),
        ocr_pending=ocr_pending,
    ).info("document_extraction_completed")

    if persisted_models:
        transactions = [Transaction.model_validate(model) for model in persisted_models]
    else:
        # Preview normalized extraction rows even when persist=false for quick QA.
        transactions = [
            Transaction(
                id=None,
                raw_desc=row.raw_desc,
                normalized_desc=None,
                amount_lkr=row.amount_lkr,
                tx_date=date.fromisoformat(row.tx_date),
                direction=row.direction,
                bank_code=row.bank_code or bank_code,
                source_type="document_upload_preview",
                raw_payload={
                    "source_filename": file.filename,
                    "content_type": file.content_type,
                    "row_index": row.row_index,
                    "parse_confidence": row.parse_confidence,
                },
            )
            for row in extracted
        ]

    return DocumentExtractResponse(
        document_name=file.filename or "uploaded_document",
        content_type=file.content_type,
        file_type=file_type,
        bank_code_hint=bank_code,
        ocr_pending=ocr_pending,
        extracted_count=len(extracted),
        persisted_count=len(persisted_models),
        warnings=warnings,
        transactions=transactions,
    )


@app.post("/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    payload = await file.read()
    try:
        result = ingest_document_metadata(db=db, upload=file, content=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document_upload_failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    document = result.document
    return DocumentUploadResponse(
        document=UploadedDocumentSummary(
            document_id=document.id,
            filename=document.filename,
            status=document.status.value,
            size_bytes=document.size_bytes,
            bank_detected=document.bank_detected,
            selected_parser=result.selected_parser,
            extracted_row_count=result.extracted_count,
        ),
        extraction_run_id=result.extract_run.id,
        metadata_extraction_run_id=result.metadata_run.id,
        router_extraction_run_id=result.router_run.id,
    )


@app.post("/v1/documents/upload-batch", response_model=DocumentBatchUploadResponse)
async def upload_document_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> DocumentBatchUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files received.")

    docs: list[UploadedDocumentSummary] = []
    run_ids: list[UUID] = []
    for file in files:
        payload = await file.read()
        try:
            result = ingest_document_metadata(db=db, upload=file, content=payload)
        except ValueError as exc:
            logger.warning(f"batch_upload_skipped filename={file.filename} reason={exc}")
            continue
        document = result.document
        docs.append(
            UploadedDocumentSummary(
                document_id=document.id,
                filename=document.filename,
                status=document.status.value,
                size_bytes=document.size_bytes,
                bank_detected=document.bank_detected,
                selected_parser=result.selected_parser,
                extracted_row_count=result.extracted_count,
            ),
        )
        run_ids.append(result.extract_run.id)

    return DocumentBatchUploadResponse(
        documents=docs,
        extraction_run_ids=run_ids,
        uploaded_count=len(docs),
    )


def _flatten_extraction_warnings(warnings: dict | None) -> list[str]:
    if not warnings:
        return []
    out: list[str] = []
    for key in ("messages", "notes"):
        raw = warnings.get(key)
        if isinstance(raw, list):
            out.extend(str(x) for x in raw)
    return out[:50]


@app.get(
    "/v1/documents/{document_id}/extracted-transactions",
    response_model=ExtractedTransactionsPageResponse,
)
def list_extracted_transactions_for_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ExtractedTransactionsPageResponse:
    """Return persisted rows from Phase 3 extraction for this document."""
    result = list_document_extracted_transactions(
        db,
        document_id,
        limit=limit,
        offset=offset,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    rows, total = result
    items = [
        ExtractedTransactionItem(
            id=r.id,
            document_id=r.document_id,
            page_no=r.page_no,
            row_no=r.row_no,
            tx_date=r.tx_date,
            description=r.description,
            reference_no=r.reference_no,
            debit=r.debit,
            credit=r.credit,
            balance=r.balance,
            amount_lkr=r.amount_lkr,
            direction=SchemaTxnDirection(r.direction.value),
            confidence=r.confidence,
            raw_row_json=r.raw_row_json,
            is_flagged=r.is_flagged,
        )
        for r in rows
    ]
    return ExtractedTransactionsPageResponse(
        document_id=document_id,
        total=total,
        limit=limit,
        offset=offset,
        transactions=items,
    )


@app.get("/v1/documents/{document_id}/status", response_model=DocumentStatusResponse)
def document_status(document_id: UUID, db: Session = Depends(get_db)) -> DocumentStatusResponse:
    snap = get_document_status_snapshot(db, document_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    document = snap.document
    latest_run = snap.latest_run

    selected_parser: str | None = None
    bank_detection_confidence: float | None = None
    if snap.router_run is not None:
        metrics = snap.router_run.metrics or {}
        raw_sel = metrics.get("selected_parser")
        raw_conf = metrics.get("bank_confidence")
        if isinstance(raw_sel, str):
            selected_parser = raw_sel
        if isinstance(raw_conf, (int, float)):
            bank_detection_confidence = float(raw_conf)

    extract_run = snap.extract_run
    extraction_warnings = _flatten_extraction_warnings(extract_run.warnings if extract_run else None)

    return DocumentStatusResponse(
        document_id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status.value,
        bank_detected=document.bank_detected,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
        updated_at=document.updated_at,
        latest_run_id=(latest_run.id if latest_run else None),
        latest_run_parser_name=(latest_run.parser_name if latest_run else None),
        latest_run_status=(latest_run.status.value if latest_run else None),
        latest_run_started_at=(latest_run.started_at if latest_run else None),
        latest_run_finished_at=(latest_run.finished_at if latest_run else None),
        selected_parser=selected_parser,
        bank_detection_confidence=bank_detection_confidence,
        extracted_row_count=snap.extracted_row_count,
        extraction_run_status=(extract_run.status.value if extract_run else None),
        extraction_run_parser=(extract_run.parser_name if extract_run else None),
        extraction_error=(extract_run.error_message if extract_run else None),
        extraction_warnings=extraction_warnings,
    )


api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/users/{user_id}/income-snapshot", response_model=IncomeSnapshotV1)
def income_snapshot(
    user_id: str,
    assessment_year: str = Query(
        ...,
        pattern=r"^\d{4}_\d{2}$",
        description="Assessment year label (e.g. 2024_25).",
    ),
) -> IncomeSnapshotV1:
    """Stub aggregate for Option B — replace with DB-backed rollups from taxability outputs."""
    logger.bind(user_id=user_id, assessment_year=assessment_year).info("income_snapshot_stub_served")
    return IncomeSnapshotV1(
        user_id=user_id,
        assessment_year=assessment_year,
        annual_gross_income=Decimal("2400000"),
        estimated_annual_taxable_income=Decimal("1800000"),
        charity_outflows_annual=None,
        source="component1_stub",
        derivation_summary=(
            "Stub aggregate: fixed demo LKR amounts. Live service will sum "
            "taxable_amount on classified inflows for the window, apply exclusions, "
            "and attach audit metadata."
        ),
        pipeline_version="stub-0.1.0",
        transaction_count=42,
    )


app.include_router(api_v1)
