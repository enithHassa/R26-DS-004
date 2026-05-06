"""Document ingestion: metadata, bank routing (Phase 2), and row extraction (Phase 3)."""

from __future__ import annotations

import io
import re
import uuid
import sys
import importlib
import importlib.util
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.shared.config.settings import PROJECT_ROOT
from backend.shared.db.enums import TxnDirection as DBTxnDirection
from backend.shared.schemas.enums import TxnDirection as SchemaTxnDirection

from .bank_detection import BankDetectionResult, detect_bank
from .document_extractor import (
    UnsupportedDocumentTypeError,
    extract_transactions_from_document,
)
from .parser_router import resolve_file_format, select_parser


UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads" / "comp-transaction-sementic"
_DB_ROOT = Path(__file__).resolve().parents[2] / "db"
_DB_ALIAS = "comp_transaction_sementic_db_runtime"

ROUTER_PARSER_NAME = "parser_router_v2"
ROUTER_PARSER_VERSION = "2.0.0"
METADATA_PARSER_NAME = "ingestion_metadata_v1"
EXTRACTION_PARSER_VERSION = "1.0.0"
SKIP_EXTRACT_PARSERS = frozenset({"image_ocr_pending_v1", "generic_unknown_v1"})


def _load_db_package() -> None:
    if _DB_ALIAS in sys.modules:
        return
    init_file = _DB_ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        _DB_ALIAS,
        init_file,
        submodule_search_locations=[str(_DB_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load db package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DB_ALIAS] = module
    spec.loader.exec_module(module)


_load_db_package()
Document = importlib.import_module(f"{_DB_ALIAS}.document").Document
DocumentPage = importlib.import_module(f"{_DB_ALIAS}.document_page").DocumentPage
ExtractionRun = importlib.import_module(f"{_DB_ALIAS}.extraction_run").ExtractionRun
ExtractedTransaction = importlib.import_module(
    f"{_DB_ALIAS}.extracted_transaction",
).ExtractedTransaction
StatementTotal = importlib.import_module(f"{_DB_ALIAS}.statement_total").StatementTotal
_enums = importlib.import_module(f"{_DB_ALIAS}.enums")
DocumentStatus = _enums.DocumentStatus
ExtractionRunStatus = _enums.ExtractionRunStatus

_SYSTEM_PARSER_NAMES = frozenset({METADATA_PARSER_NAME, ROUTER_PARSER_NAME})


class IngestionResult(NamedTuple):
    document: Document
    metadata_run: ExtractionRun
    router_run: ExtractionRun
    extract_run: ExtractionRun
    selected_parser: str
    extracted_count: int


class ReExtractResult(NamedTuple):
    document: Document
    router_run: ExtractionRun
    extract_run: ExtractionRun
    selected_parser: str
    extracted_count: int


@dataclass
class DocumentStatusSnapshot:
    document: Document
    latest_run: ExtractionRun | None
    router_run: ExtractionRun | None
    extract_run: ExtractionRun | None
    extracted_row_count: int


def ingest_document_metadata(
    *,
    db: Session,
    upload: UploadFile,
    content: bytes,
) -> IngestionResult:
    """Create document, metadata extraction run, page stubs, then router run (Phase 2)."""
    if not content:
        raise ValueError("Uploaded file is empty.")

    doc_id = uuid.uuid4()
    safe_name = _sanitize_filename(upload.filename or "uploaded_file.bin")
    storage_dir = UPLOAD_ROOT / datetime.now(timezone.utc).strftime("%Y/%m/%d")
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{doc_id}_{safe_name}"
    storage_path.write_bytes(content)

    document = Document(
        id=doc_id,
        filename=upload.filename or safe_name,
        content_type=upload.content_type,
        size_bytes=len(content),
        bank_detected=None,
        status=DocumentStatus.PROCESSING,
        storage_path=str(storage_path),
    )
    db.add(document)
    db.flush()

    run = ExtractionRun(
        document_id=document.id,
        parser_name=METADATA_PARSER_NAME,
        parser_version="1.0.0",
        status=ExtractionRunStatus.STARTED,
        warnings={"notes": ["Metadata + routing + extraction (Phase 3)."]},
        metrics={"size_bytes": len(content)},
    )
    db.add(run)
    db.flush()

    pages = _extract_document_pages(upload.content_type, content, document.id)
    for page in pages:
        db.add(page)

    run.status = ExtractionRunStatus.COMPLETED
    run.finished_at = datetime.now(timezone.utc)
    run.metrics = {"size_bytes": len(content), "page_count": len(pages)}

    text_probe = _build_text_probe(
        filename=document.filename,
        content_type=upload.content_type,
        content=content,
        pages=pages,
    )
    detection = detect_bank(
        filename=document.filename,
        text_probe=text_probe,
        raw_bytes_probe=content,
    )
    file_format = resolve_file_format(document.filename, document.content_type)
    selected_parser, router_notes = select_parser(detection=detection, file_format=file_format)

    document.bank_detected = detection.bank_code
    document.updated_at = datetime.now(timezone.utc)

    router_run = ExtractionRun(
        document_id=document.id,
        parser_name=ROUTER_PARSER_NAME,
        parser_version=ROUTER_PARSER_VERSION,
        status=ExtractionRunStatus.COMPLETED,
        warnings=None,
        metrics={
            "selected_parser": selected_parser,
            "bank_code": detection.bank_code,
            "bank_confidence": detection.confidence,
            "signals": detection.signals,
            "file_format": file_format,
            **router_notes,
        },
        finished_at=datetime.now(timezone.utc),
    )
    db.add(router_run)

    extract_run, extracted_count = _persist_extraction_phase(
        db=db,
        document=document,
        content=content,
        selected_parser=selected_parser,
    )

    document.status = DocumentStatus.COMPLETED
    document.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    db.refresh(run)
    db.refresh(router_run)
    db.refresh(extract_run)
    return IngestionResult(
        document=document,
        metadata_run=run,
        router_run=router_run,
        extract_run=extract_run,
        selected_parser=selected_parser,
        extracted_count=extracted_count,
    )


def list_statement_totals_for_document(
    db: Session,
    document_id: uuid.UUID,
) -> list[StatementTotal] | None:
    """Return stored statement summaries, or None if the document does not exist."""
    if db.get(Document, document_id) is None:
        return None
    return list(
        db.scalars(
            select(StatementTotal)
            .where(StatementTotal.document_id == document_id)
            .order_by(StatementTotal.period_start.asc().nulls_last(), StatementTotal.id.asc()),
        ).all(),
    )


def re_extract_document(
    *,
    db: Session,
    document_id: uuid.UUID,
    bank_code_override: str | None = None,
) -> ReExtractResult | None:
    """Re-run routing + extraction from the stored file; replaces parsed rows and pages.

    Keeps the original document record and file on disk; appends new router/extract runs.
    """
    document = db.get(Document, document_id)
    if document is None:
        return None

    path = Path(document.storage_path)
    if not path.is_file():
        raise FileNotFoundError(document.storage_path)

    content = path.read_bytes()
    if not content:
        raise ValueError("Stored file is empty.")

    try:
        document.status = DocumentStatus.PROCESSING
        document.updated_at = datetime.now(timezone.utc)
        db.flush()

        _clear_document_parse_artifacts(db, document.id)

        pages = _extract_document_pages(document.content_type, content, document.id)
        for page in pages:
            db.add(page)

        text_probe = _build_text_probe(
            filename=document.filename,
            content_type=document.content_type,
            content=content,
            pages=pages,
        )
        if bank_code_override and bank_code_override.strip():
            hint = bank_code_override.strip().upper()[:32]
            detection = BankDetectionResult(
                bank_code=hint,
                confidence=1.0,
                signals=["bank_code_override"],
            )
        else:
            detection = detect_bank(
                filename=document.filename,
                text_probe=text_probe,
                raw_bytes_probe=content,
            )

        document.bank_detected = detection.bank_code
        file_format = resolve_file_format(document.filename, document.content_type)
        selected_parser, router_notes = select_parser(detection=detection, file_format=file_format)

        router_run = ExtractionRun(
            document_id=document.id,
            parser_name=ROUTER_PARSER_NAME,
            parser_version=ROUTER_PARSER_VERSION,
            status=ExtractionRunStatus.COMPLETED,
            warnings=None,
            metrics={
                "selected_parser": selected_parser,
                "bank_code": detection.bank_code,
                "bank_confidence": detection.confidence,
                "signals": detection.signals,
                "file_format": file_format,
                "re_extract": True,
                **router_notes,
            },
            finished_at=datetime.now(timezone.utc),
        )
        db.add(router_run)

        extract_run, extracted_count = _persist_extraction_phase(
            db=db,
            document=document,
            content=content,
            selected_parser=selected_parser,
        )

        document.status = DocumentStatus.COMPLETED
        document.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(document)
    db.refresh(router_run)
    db.refresh(extract_run)
    return ReExtractResult(
        document=document,
        router_run=router_run,
        extract_run=extract_run,
        selected_parser=selected_parser,
        extracted_count=extracted_count,
    )


def _clear_document_parse_artifacts(db: Session, document_id: uuid.UUID) -> None:
    db.execute(delete(ExtractedTransaction).where(ExtractedTransaction.document_id == document_id))
    db.execute(delete(StatementTotal).where(StatementTotal.document_id == document_id))
    db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
    db.flush()


def list_document_extracted_transactions(
    db: Session,
    document_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ExtractedTransaction], int] | None:
    """Return (rows, total_count) or None if the document does not exist."""
    if db.get(Document, document_id) is None:
        return None

    total = db.scalar(
        select(func.count()).select_from(ExtractedTransaction).where(
            ExtractedTransaction.document_id == document_id,
        ),
    )
    total_i = int(total or 0)

    rows = list(
        db.scalars(
            select(ExtractedTransaction)
            .where(ExtractedTransaction.document_id == document_id)
            .order_by(
                ExtractedTransaction.tx_date.asc(),
                ExtractedTransaction.row_no.asc().nulls_last(),
                ExtractedTransaction.id.asc(),
            )
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return rows, total_i


def get_document_status_snapshot(db: Session, document_id: uuid.UUID) -> DocumentStatusSnapshot | None:
    document = db.get(Document, document_id)
    if document is None:
        return None

    runs = list(
        db.scalars(
            select(ExtractionRun)
            .where(ExtractionRun.document_id == document_id)
            .order_by(ExtractionRun.started_at.desc()),
        ).all(),
    )
    latest_run = runs[0] if runs else None
    router_run = next((r for r in runs if r.parser_name == ROUTER_PARSER_NAME), None)
    extract_run = next(
        (r for r in runs if r.parser_name not in _SYSTEM_PARSER_NAMES),
        None,
    )

    row_count = db.scalar(
        select(func.count()).select_from(ExtractedTransaction).where(
            ExtractedTransaction.document_id == document_id,
        ),
    )
    extracted_row_count = int(row_count or 0)

    return DocumentStatusSnapshot(
        document=document,
        latest_run=latest_run,
        router_run=router_run,
        extract_run=extract_run,
        extracted_row_count=extracted_row_count,
    )


def _persist_extraction_phase(
    *,
    db: Session,
    document: Document,
    content: bytes,
    selected_parser: str,
) -> tuple[ExtractionRun, int]:
    now = datetime.now(timezone.utc)
    extract_run = ExtractionRun(
        document_id=document.id,
        parser_name=selected_parser,
        parser_version=EXTRACTION_PARSER_VERSION,
        status=ExtractionRunStatus.STARTED,
    )
    db.add(extract_run)
    db.flush()

    if selected_parser in SKIP_EXTRACT_PARSERS:
        extract_run.status = ExtractionRunStatus.COMPLETED
        extract_run.finished_at = now
        extract_run.metrics = {"row_count": 0, "extract_skipped": True, "reason": selected_parser}
        extract_run.warnings = {"notes": [f"Extraction not run for parser {selected_parser}."]}
        return extract_run, 0

    try:
        outcome = extract_transactions_from_document(
            filename=document.filename,
            content_type=document.content_type,
            payload=content,
            bank_code_hint=document.bank_detected,
        )
    except UnsupportedDocumentTypeError as exc:
        extract_run.status = ExtractionRunStatus.FAILED
        extract_run.finished_at = now
        extract_run.error_message = str(exc)[:4000]
        extract_run.metrics = {"row_count": 0}
        return extract_run, 0
    except Exception as exc:
        extract_run.status = ExtractionRunStatus.FAILED
        extract_run.finished_at = now
        extract_run.error_message = str(exc)[:4000]
        extract_run.metrics = {"row_count": 0}
        return extract_run, 0

    total_dr = sum(
        (r.amount_lkr for r in outcome.rows if r.direction == SchemaTxnDirection.DR),
        Decimal("0"),
    )
    total_cr = sum(
        (r.amount_lkr for r in outcome.rows if r.direction == SchemaTxnDirection.CR),
        Decimal("0"),
    )

    for row in outcome.rows:
        debit = row.amount_lkr if row.direction == SchemaTxnDirection.DR else None
        credit = row.amount_lkr if row.direction == SchemaTxnDirection.CR else None
        db.add(
            ExtractedTransaction(
                document_id=document.id,
                page_no=None,
                row_no=row.row_index,
                tx_date=date.fromisoformat(row.tx_date),
                description=row.raw_desc,
                reference_no=None,
                debit=debit,
                credit=credit,
                balance=None,
                amount_lkr=row.amount_lkr,
                direction=DBTxnDirection(row.direction.value),
                confidence=row.parse_confidence,
                raw_row_json={
                    "bank_code": row.bank_code,
                    "file_type": outcome.file_type,
                },
            )
        )

    ctx = outcome.statement_context
    if ctx and (ctx.period_start or ctx.period_end):
        existing = db.scalar(
            select(StatementTotal.id).where(StatementTotal.document_id == document.id).limit(1),
        )
        if existing is None:
            db.add(
                StatementTotal(
                    document_id=document.id,
                    opening_balance=None,
                    closing_balance=None,
                    total_debit=total_dr if total_dr > 0 else None,
                    total_credit=total_cr if total_cr > 0 else None,
                    currency="LKR",
                    period_start=ctx.period_start,
                    period_end=ctx.period_end,
                ),
            )

    extract_run.status = ExtractionRunStatus.COMPLETED
    extract_run.finished_at = now
    extract_run.metrics = {
        "row_count": len(outcome.rows),
        "file_type": outcome.file_type,
        "ocr_pending": outcome.ocr_pending,
        "totals_debit_lkr": str(total_dr),
        "totals_credit_lkr": str(total_cr),
    }
    extract_run.warnings = {"messages": outcome.warnings} if outcome.warnings else None
    return extract_run, len(outcome.rows)


def _sanitize_filename(filename: str) -> str:
    base = filename.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "", base) or "uploaded_file.bin"


def _build_text_probe(
    *,
    filename: str,
    content_type: str | None,
    content: bytes,
    pages: list[DocumentPage],
) -> str:
    parts: list[str] = []
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "csv" or (content_type and "csv" in content_type):
        line = content.splitlines()[0].decode("utf-8", errors="ignore") if content else ""
        if line:
            parts.append(line)

    excerpts = [p.text_excerpt for p in pages if p.text_excerpt]
    if excerpts:
        parts.append(" ".join(excerpts))

    if not parts and content:
        parts.append(content[:8000].decode("utf-8", errors="ignore"))

    probe = "\n".join(parts)
    return probe[:6000]


def _extract_document_pages(content_type: str | None, content: bytes, document_id: uuid.UUID) -> list[DocumentPage]:
    if content_type and "pdf" in content_type:
        try:
            from pypdf import PdfReader
        except Exception:
            return [
                DocumentPage(
                    document_id=document_id,
                    page_no=1,
                    text_excerpt=None,
                    ocr_used=False,
                    quality_score=None,
                ),
            ]

        from pypdf import PdfReader

        pdf = PdfReader(io.BytesIO(content))
        pages: list[DocumentPage] = []
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            limit = 1600 if i == 1 else 400
            excerpt = re.sub(r"\s+", " ", text)[:limit] if text else None
            pages.append(
                DocumentPage(
                    document_id=document_id,
                    page_no=i,
                    text_excerpt=excerpt,
                    ocr_used=False,
                    quality_score=1.0 if excerpt else 0.2,
                ),
            )
        return pages or [
            DocumentPage(
                document_id=document_id,
                page_no=1,
                text_excerpt=None,
                ocr_used=False,
                quality_score=None,
            ),
        ]

    return [
        DocumentPage(
            document_id=document_id,
            page_no=1,
            text_excerpt=None,
            ocr_used=bool(content_type and content_type.startswith("image/")),
            quality_score=None,
        ),
    ]
