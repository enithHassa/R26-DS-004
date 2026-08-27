"""Transaction Semantic component — FastAPI entry point.

Phase 0 stub: `/health`, `/v1/transactions/analyze`, and
``GET /api/v1/users/{user_id}/income-snapshot`` (aggregate stub for Component B Option B).
"""

from __future__ import annotations

from datetime import date
import csv
import io
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    IncomeSnapshotV1,
    NarrativeContextHit,
    TaxabilityOutput,
    Transaction,
)
from backend.shared.schemas.enums import TxnDirection as SchemaTxnDirection
from .schemas import DocumentExtractResponse
from .schemas.tax_reasoning import (
    ActivitySummaryGroup,
    ActivitySummaryMember,
    ActivitySummaryRequest,
    ActivitySummaryResponse,
    AnalyzeBatchItemResponse,
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    ApplyClassBatchRequest,
    ApplyClassBatchResponse,
    InflowSummaryResponse,
    IncomeTypeCatalogItem,
    IncomeTypeCatalogResponse,
    TaxableIncomeLineItem,
    TaxableIncomeSummaryRequest,
    TaxableIncomeSummaryResponse,
)
from .schemas import (
    DocumentPreviewResponse,
    DocumentBatchUploadResponse,
    DocumentListResponse,
    DocumentRenameRequest,
    DocumentRenameResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    ExtractedTransactionItem,
    ExtractedTransactionsPageResponse,
    ExportPreviewResponse,
    ExportPreviewRow,
    PreviewExtractedTransactionItem,
    PreviewStatementTotalItem,
    ReExtractDocumentResponse,
    StatementTotalsResponse,
    StatementTotalItem,
    UploadedDocumentSummary,
)
from .services import (
    ExportFilter,
    UnsupportedDocumentTypeError,
    extract_transactions_from_document,
    get_document_status_snapshot,
    ingest_document_metadata,
    list_extracted_transactions_for_export,
    list_document_extracted_transactions,
    list_documents,
    list_statement_totals_for_document,
    preview_extracted_transactions_for_export,
    preview_document_extraction,
    re_extract_document,
    rename_document,
)
from .services.analysis_persistence import persist_transaction_analysis
from .services.rule_engine_service import get_rule_executor
from .services.taxable_income_summary import build_taxable_income_summary
from .services.inflow_summary import (
    PERSONAL_RELIEF_ANNUAL_LKR,
    PERSONAL_RELIEF_MONTHLY_EQUIVALENT_LKR,
    summarize_inflows,
)
from .services.activity_summary import build_activity_summary
from .services.taxonomy_catalog_service import get_income_type_catalog
from .services.narrative_context import get_narrative_context_index
from .services.semantic_classifier import preload_semantic_classifier
from .services.transaction_analyzer import (
    TransactionAnalysisResult,
    TransactionAnalyzeInput,
    analyze_transaction_fields,
    analyze_transactions_batch,
    apply_transactions_class_batch,
)

configure_logging(settings)

app = FastAPI(
    title="Transaction Semantic Reasoning API",
    description="Explainable taxable-income inference from bank transactions (Component 1).",
    version="0.1.0",
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_semantic_classifier() -> None:
    try:
        preload_semantic_classifier()
        get_narrative_context_index()
        logger.info("semantic_classifier_preloaded")
    except FileNotFoundError as exc:
        logger.warning("semantic_classifier_not_preloaded: {}", exc)


def _with_taxpayer_id(
    facts: dict[str, Any] | None,
    taxpayer_id: str | None,
) -> dict[str, Any]:
    merged = dict(facts or {})
    if taxpayer_id and "taxpayer_id" not in merged:
        merged["taxpayer_id"] = taxpayer_id
    if "taxpayer_id" not in merged:
        merged["taxpayer_id"] = "taxpayer_00001"
    return merged


def _to_analyze_response(analysis: TransactionAnalysisResult) -> AnalyzeTransactionResponse:
    return AnalyzeTransactionResponse(
        transaction_id=analysis.transaction_id,
        semantic_category=analysis.semantic_category,
        economic_event=analysis.economic_event,
        tax_rule_code=analysis.tax_rule_code,
        taxability=TaxabilityOutput(
            tx_id=analysis.transaction_id,
            taxability_status=analysis.taxability_status,
            taxable_amount=analysis.taxable_amount_lkr,
            confidence=analysis.confidence_report.top_probability,
            evidence=analysis.evidence,
            model_version=analysis.model_version,
            model_run_id=None,
            treatment=analysis.treatment,
            taxable_fraction=analysis.taxable_fraction,
        ),
        confidence_report=analysis.confidence_report,
        taxonomy_version=analysis.taxonomy_version,
        rulebook_version=analysis.rulebook_version,
        decision_mode=analysis.decision_mode,
        rule_reference=analysis.rule_reference,
        explanation=analysis.explanation,
        review_reason=analysis.review_reason,
        condition_id_matched=analysis.condition_id_matched,
        model_semantic_category=analysis.model_semantic_category,
        class_source=analysis.class_source,
        narrative_interpretation=analysis.narrative_interpretation,
        narrative_hits=[
            NarrativeContextHit(
                class_key=hit.class_key,
                score=hit.score,
                description=hit.description,
                default_taxability_status=hit.default_taxability_status,
            )
            for hit in analysis.narrative_hits
        ],
        certainty_tier=analysis.certainty_tier,
        intent_tag=analysis.intent_tag,
        channel=analysis.channel,
        evidence_needed=analysis.evidence_needed,
        layer1_note=analysis.layer1_note,
    )


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("health_check_ok")
    return {"status": "ok"}


@app.post("/v1/transactions/analyze", response_model=AnalyzeTransactionResponse)
def analyze_transaction(
    payload: AnalyzeTransactionRequest,
    db: Session = Depends(get_db),
) -> AnalyzeTransactionResponse:
    """Normalize, classify, and apply deterministic IRA tax rules."""
    facts = _with_taxpayer_id(
        payload.facts.model_dump(exclude_none=True) if payload.facts else None,
        payload.facts.taxpayer_id if payload.facts else None,
    )
    analysis = analyze_transaction_fields(
        raw_desc=payload.raw_desc,
        amount_lkr=payload.amount_lkr,
        direction=payload.direction,
        bank_code=payload.bank_code,
        document_type=payload.document_type,
        facts=facts,
    )
    if payload.persist:
        persist_transaction_analysis(
            db,
            raw_desc=payload.raw_desc,
            amount_lkr=payload.amount_lkr,
            tx_date=payload.tx_date,
            direction=payload.direction.value,
            bank_code=payload.bank_code,
            source_type="api_analyze",
            analysis=analysis,
            raw_payload={"facts": facts, "document_type": payload.document_type},
        )

    logger.bind(
        transaction_id=str(analysis.transaction_id),
        semantic_category=analysis.semantic_category,
        tax_rule_code=analysis.tax_rule_code,
        taxability_status=analysis.taxability_status.value,
    ).info("analyze_transaction_completed")

    return _to_analyze_response(analysis)


@app.post("/v1/transactions/analyze-batch", response_model=AnalyzeBatchResponse)
def analyze_transactions_batch_endpoint(
    payload: AnalyzeBatchRequest,
    db: Session = Depends(get_db),
) -> AnalyzeBatchResponse:
    """Classify many rows in one request (shared model load + batched inference)."""
    inputs = [
        TransactionAnalyzeInput(
            raw_desc=item.raw_desc,
            amount_lkr=item.amount_lkr,
            tx_date=item.tx_date,
            direction=item.direction,
            facts=_with_taxpayer_id(
                item.facts.model_dump(exclude_none=True) if item.facts else None,
                payload.taxpayer_id,
            ),
            row_id=item.row_id,
        )
        for item in payload.items
    ]
    analyses = analyze_transactions_batch(
        inputs,
        bank_code=payload.bank_code,
        document_type=payload.document_type,
    )
    document_filename: str | None = None
    if payload.document_id is not None:
        snap = get_document_status_snapshot(db, payload.document_id)
        if snap is not None:
            document_filename = snap.document.filename

    results: list[AnalyzeBatchItemResponse] = []
    for item, analysis in zip(payload.items, analyses, strict=True):
        facts = item.facts.model_dump(exclude_none=True) if item.facts else None
        if payload.persist:
            raw_payload: dict[str, object] = {
                "facts": facts,
                "document_type": payload.document_type,
                "row_id": item.row_id,
            }
            if payload.document_id is not None:
                raw_payload["document_id"] = str(payload.document_id)
            if document_filename is not None:
                raw_payload["document_filename"] = document_filename
                raw_payload["source_filename"] = document_filename
            persist_transaction_analysis(
                db,
                raw_desc=item.raw_desc,
                amount_lkr=item.amount_lkr,
                tx_date=item.tx_date,
                direction=item.direction.value,
                bank_code=payload.bank_code,
                source_type="api_analyze_batch",
                analysis=analysis,
                raw_payload=raw_payload,
            )
        results.append(
            AnalyzeBatchItemResponse(
                row_id=item.row_id,
                result=_to_analyze_response(analysis),
            ),
        )

    logger.bind(processed_count=len(results)).info("analyze_transactions_batch_completed")
    rollup = summarize_inflows(inputs, analyses)
    return AnalyzeBatchResponse(
        results=results,
        processed_count=len(results),
        inflow_summary=InflowSummaryResponse(
            guaranteed_taxable_inflows_lkr=rollup.guaranteed_taxable_inflows_lkr,
            guaranteed_non_taxable_inflows_lkr=rollup.guaranteed_non_taxable_inflows_lkr,
            indeterminate_inflows_lkr=rollup.indeterminate_inflows_lkr,
            outflow_lkr=rollup.outflow_lkr,
            credit_count=rollup.credit_count,
            debit_count=rollup.debit_count,
            indeterminate_credit_count=rollup.indeterminate_credit_count,
            potential_assessable_if_indet_is_income_lkr=rollup.potential_assessable_if_indet_is_income_lkr,
            exceeds_annual_personal_relief_if_indet_is_income=(
                rollup.exceeds_annual_personal_relief_if_indet_is_income
            ),
            exceeds_monthly_relief_equivalent_if_indet_is_income=(
                rollup.exceeds_monthly_relief_equivalent_if_indet_is_income
            ),
            personal_relief_annual_lkr=PERSONAL_RELIEF_ANNUAL_LKR,
            personal_relief_monthly_equivalent_lkr=PERSONAL_RELIEF_MONTHLY_EQUIVALENT_LKR,
            relief_hint=rollup.relief_hint,
        ),
    )


@app.post("/v1/transactions/apply-class-batch", response_model=ApplyClassBatchResponse)
def apply_transactions_class_batch_endpoint(
    payload: ApplyClassBatchRequest,
) -> ApplyClassBatchResponse:
    """Re-run IRA rules for manually selected taxonomy classes."""
    inputs = [
        TransactionAnalyzeInput(
            raw_desc=item.raw_desc,
            amount_lkr=item.amount_lkr,
            tx_date=item.tx_date,
            direction=item.direction,
            facts=item.facts.model_dump(exclude_none=True) if item.facts else None,
            row_id=item.row_id,
        )
        for item in payload.items
    ]
    analyses = apply_transactions_class_batch(
        inputs,
        class_keys=[item.class_key for item in payload.items],
        bank_code=payload.bank_code,
        document_type=payload.document_type,
        model_semantic_categories=[item.model_semantic_category for item in payload.items],
    )
    results = [
        AnalyzeBatchItemResponse(
            row_id=item.row_id,
            result=_to_analyze_response(analysis),
        )
        for item, analysis in zip(payload.items, analyses, strict=True)
    ]
    logger.bind(processed_count=len(results)).info("apply_transactions_class_batch_completed")
    return ApplyClassBatchResponse(results=results, processed_count=len(results))


@app.get("/v1/taxonomy/income-types", response_model=IncomeTypeCatalogResponse)
def list_income_types() -> IncomeTypeCatalogResponse:
    """Reference catalog of semantic classes and default IRA taxability."""
    executor = get_rule_executor()
    entries = get_income_type_catalog()
    items = [
        IncomeTypeCatalogItem(
            class_key=entry.class_key,
            group=entry.group,
            description=entry.description,
            tax_rule_code=entry.tax_rule_code,
            default_taxability_status=entry.default_taxability_status,
            default_taxable_fraction=entry.default_taxable_fraction,
            treatment=entry.treatment,
            rule_reference=entry.rule_reference,
            explanation=entry.explanation,
            is_conditional=entry.is_conditional,
        )
        for entry in entries
    ]
    grouped: dict[str, list[IncomeTypeCatalogItem]] = {}
    for item in items:
        grouped.setdefault(item.default_taxability_status, []).append(item)
    return IncomeTypeCatalogResponse(
        taxonomy_version=executor.taxonomy_version,
        rulebook_version=executor.rulebook_version,
        items=items,
        by_taxability_status=grouped,
    )


@app.post("/v1/taxable-income/summary", response_model=TaxableIncomeSummaryResponse)
def summarize_taxable_income(
    payload: TaxableIncomeSummaryRequest,
    db: Session = Depends(get_db),
) -> TaxableIncomeSummaryResponse:
    """Aggregate persisted taxability outputs into taxable / non-taxable / review lines."""
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    summary = build_taxable_income_summary(
        db,
        date_from=payload.date_from,
        date_to=payload.date_to,
        bank_code=payload.bank_code,
    )

    def _map_lines(lines):
        return [
            TaxableIncomeLineItem(
                class_key=line.class_key,
                tax_rule_code=line.tax_rule_code,
                taxability_status=line.taxability_status,
                transaction_count=line.transaction_count,
                gross_amount_lkr=line.gross_amount_lkr,
                taxable_amount_lkr=line.taxable_amount_lkr,
            )
            for line in lines
        ]

    return TaxableIncomeSummaryResponse(
        date_from=summary.date_from,
        date_to=summary.date_to,
        total_taxable_lkr=summary.total_taxable_lkr,
        total_excluded_lkr=summary.total_excluded_lkr,
        review_count=summary.review_count,
        transaction_count=summary.transaction_count,
        taxable_lines=_map_lines(summary.taxable_lines),
        non_taxable_lines=_map_lines(summary.non_taxable_lines),
        review_lines=_map_lines(summary.review_lines),
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


@app.get("/v1/documents", response_model=DocumentListResponse)
def list_uploaded_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List persisted uploads (newest first)."""
    rows, total = list_documents(db, limit=limit, offset=offset)
    items = [
        UploadedDocumentSummary(
            document_id=document.id,
            filename=document.filename,
            status=document.status.value,
            size_bytes=document.size_bytes,
            bank_detected=document.bank_detected,
            selected_parser=selected_parser,
            extracted_row_count=row_count,
        )
        for document, row_count, selected_parser in rows
    ]
    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@app.patch("/v1/documents/{document_id}", response_model=DocumentRenameResponse)
def rename_uploaded_document(
    document_id: UUID,
    payload: DocumentRenameRequest,
    db: Session = Depends(get_db),
) -> DocumentRenameResponse:
    """Rename a stored document and sync linked persisted transaction metadata."""
    try:
        result = rename_document(db, document_id=document_id, filename=payload.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    document, row_count, updated_related, selected_parser = result
    return DocumentRenameResponse(
        document=UploadedDocumentSummary(
            document_id=document.id,
            filename=document.filename,
            status=document.status.value,
            size_bytes=document.size_bytes,
            bank_detected=document.bank_detected,
            selected_parser=selected_parser,
            extracted_row_count=row_count,
        ),
        updated_related_transaction_count=updated_related,
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


@app.post("/v1/documents/preview", response_model=DocumentPreviewResponse)
async def preview_document(
    file: UploadFile = File(...),
    bank_code: str | None = Query(
        default=None,
        max_length=32,
        description="Optional bank code (e.g. NTB) to force parser routing for preview.",
    ),
) -> DocumentPreviewResponse:
    """Extract statement rows without persisting document, runs, or rows."""
    payload = await file.read()
    try:
        preview = preview_document_extraction(
            filename=file.filename or "uploaded_document",
            content_type=file.content_type,
            content=payload,
            bank_code_override=bank_code,
        )
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document_preview_failed")
        raise HTTPException(status_code=500, detail=f"Preview failed: {exc}") from exc

    transactions = [
        PreviewExtractedTransactionItem(
            row_no=row.row_index,
            tx_date=date.fromisoformat(row.tx_date),
            description=row.raw_desc,
            amount_lkr=row.amount_lkr,
            direction=SchemaTxnDirection(row.direction.value),
            debit=(row.amount_lkr if row.direction.value == "DR" else None),
            credit=(row.amount_lkr if row.direction.value == "CR" else None),
            confidence=row.parse_confidence,
        )
        for row in preview.extracted_rows
    ]
    totals: list[PreviewStatementTotalItem] = []
    if (
        preview.total_debit is not None
        or preview.total_credit is not None
        or preview.period_start is not None
        or preview.period_end is not None
    ):
        totals = [
            PreviewStatementTotalItem(
                total_debit=preview.total_debit,
                total_credit=preview.total_credit,
                currency="LKR",
                period_start=preview.period_start,
                period_end=preview.period_end,
            )
        ]

    return DocumentPreviewResponse(
        filename=preview.filename,
        content_type=preview.content_type,
        file_type=preview.file_type,
        bank_detected=preview.bank_detected,
        selected_parser=preview.selected_parser,
        extracted_count=len(transactions),
        warnings=preview.warnings,
        transactions=transactions,
        statement_totals=totals,
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


def _build_export_csv_response(
    filename: str,
    rows: list[tuple[object, object]],
) -> StreamingResponse:
    buff = io.StringIO()
    writer = csv.writer(buff)
    writer.writerow(
        [
            "document_id",
            "filename",
            "bank_detected",
            "tx_id",
            "tx_date",
            "row_no",
            "description",
            "direction",
            "amount_lkr",
            "debit",
            "credit",
            "balance",
            "confidence",
            "is_flagged",
        ]
    )
    for tx, doc in rows:
        writer.writerow(
            [
                str(doc.id),
                doc.filename,
                doc.bank_detected or "",
                str(tx.id),
                tx.tx_date.isoformat(),
                tx.row_no if tx.row_no is not None else "",
                tx.description,
                tx.direction.value,
                str(tx.amount_lkr),
                str(tx.debit) if tx.debit is not None else "",
                str(tx.credit) if tx.credit is not None else "",
                str(tx.balance) if tx.balance is not None else "",
                f"{tx.confidence:.4f}" if tx.confidence is not None else "",
                "true" if tx.is_flagged else "false",
            ]
        )
    buff.seek(0)
    return StreamingResponse(
        iter([buff.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/v1/transactions/activity-summary", response_model=ActivitySummaryResponse)
def activity_summary_for_rows(payload: ActivitySummaryRequest) -> ActivitySummaryResponse:
    """Group extracted (or preview) rows by bank intent + merchant family for auditors."""
    groups = build_activity_summary(
        [
            {
                "row_id": item.row_id,
                "raw_desc": item.raw_desc,
                "amount_lkr": item.amount_lkr,
                "tx_date": item.tx_date.isoformat() if item.tx_date else None,
                "direction": item.direction.value,
            }
            for item in payload.items
        ],
    )
    return ActivitySummaryResponse(
        group_count=len(groups),
        transaction_count=sum(g.count for g in groups),
        groups=[
            ActivitySummaryGroup(
                group_key=g.group_key,
                label=g.label,
                hint=g.hint,
                direction=SchemaTxnDirection(g.direction),
                intent_tag=g.intent_tag,
                merchant_family=g.merchant_family,
                count=g.count,
                total_lkr=g.total_lkr,
                members=[
                    ActivitySummaryMember(
                        row_id=m.row_id,
                        tx_date=date.fromisoformat(m.tx_date) if m.tx_date else None,
                        description=m.description,
                        direction=SchemaTxnDirection(m.direction),
                        amount_lkr=m.amount_lkr,
                    )
                    for m in g.members
                ],
            )
            for g in groups
        ],
    )


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


@app.get("/v1/documents/{document_id}/export.csv")
def export_single_document_csv(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = list_extracted_transactions_for_export(db, document_id=document_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No extracted rows found for this document.")
    return _build_export_csv_response(f"document_{document_id}_extracted.csv", rows)


@app.get("/v1/documents/export.csv")
def export_filtered_documents_csv(
    db: Session = Depends(get_db),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    bank_code: str | None = Query(default=None, max_length=32),
    direction: str | None = Query(default=None, pattern="^(CR|DR)$"),
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
    text_query: str | None = Query(default=None, max_length=200),
) -> StreamingResponse:
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=400, detail="min_amount must be <= max_amount")
    filters = ExportFilter(
        date_from=date_from,
        date_to=date_to,
        bank_code=bank_code,
        direction=direction,
        min_amount=min_amount,
        max_amount=max_amount,
        text_query=text_query,
    )
    rows = list_extracted_transactions_for_export(db, filters=filters)
    if not rows:
        raise HTTPException(status_code=404, detail="No extracted rows match the provided filters.")
    return _build_export_csv_response("documents_filtered_export.csv", rows)


@app.get("/v1/documents/export/preview", response_model=ExportPreviewResponse)
def preview_filtered_export(
    db: Session = Depends(get_db),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    bank_code: str | None = Query(default=None, max_length=32),
    direction: str | None = Query(default=None, pattern="^(CR|DR)$"),
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
    text_query: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> ExportPreviewResponse:
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=400, detail="min_amount must be <= max_amount")
    filters = ExportFilter(
        date_from=date_from,
        date_to=date_to,
        bank_code=bank_code,
        direction=direction,
        min_amount=min_amount,
        max_amount=max_amount,
        text_query=text_query,
    )
    rows, total = preview_extracted_transactions_for_export(
        db,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    result_rows = [
        ExportPreviewRow(
            document_id=doc.id,
            filename=doc.filename,
            bank_detected=doc.bank_detected,
            tx_id=tx.id,
            tx_date=tx.tx_date,
            row_no=tx.row_no,
            description=tx.description,
            direction=SchemaTxnDirection(tx.direction.value),
            amount_lkr=tx.amount_lkr,
            debit=tx.debit,
            credit=tx.credit,
            balance=tx.balance,
            confidence=tx.confidence,
        )
        for tx, doc in rows
    ]
    return ExportPreviewResponse(total=total, limit=limit, offset=offset, rows=result_rows)


@app.get(
    "/v1/documents/{document_id}/statement-totals",
    response_model=StatementTotalsResponse,
)
def get_statement_totals(document_id: UUID, db: Session = Depends(get_db)) -> StatementTotalsResponse:
    """Return statement-level summary rows (period, computed debit/credit totals when available)."""
    rows = list_statement_totals_for_document(db, document_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    items = [
        StatementTotalItem(
            id=r.id,
            document_id=r.document_id,
            opening_balance=r.opening_balance,
            closing_balance=r.closing_balance,
            total_debit=r.total_debit,
            total_credit=r.total_credit,
            currency=r.currency,
            period_start=r.period_start,
            period_end=r.period_end,
        )
        for r in rows
    ]
    return StatementTotalsResponse(document_id=document_id, totals=items)


@app.post(
    "/v1/documents/{document_id}/re-extract",
    response_model=ReExtractDocumentResponse,
)
def post_re_extract_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    bank_code: str | None = Query(
        default=None,
        max_length=32,
        description="Optional bank code (e.g. NTB) to force parser routing and extraction hint.",
    ),
) -> ReExtractDocumentResponse:
    """Re-run bank routing and row extraction from the stored file without a new upload."""
    try:
        result = re_extract_document(db=db, document_id=document_id, bank_code_override=bank_code)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Stored source file is missing: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("re_extract_failed")
        raise HTTPException(status_code=500, detail=f"Re-extract failed: {exc}") from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = result.document
    return ReExtractDocumentResponse(
        document_id=doc.id,
        status=doc.status.value,
        bank_detected=doc.bank_detected,
        selected_parser=result.selected_parser,
        extracted_row_count=result.extracted_count,
        router_extraction_run_id=result.router_run.id,
        extraction_run_id=result.extract_run.id,
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
