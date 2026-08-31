"""Persist and reload classifications tied to extracted document rows."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.shared.schemas.analyze import AnalyzeTransactionResponse

from backend.shared.services.profile_taxable_income_rollup import (
    recompute_profile_monthly_taxable_income,
)

from .transaction_analyzer import TransactionAnalysisResult

_DB_ROOT = Path(__file__).resolve().parents[2] / "db"
_DB_ALIAS = "comp_transaction_sementic_db_runtime"


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
ClassifiedExtractedTransaction = importlib.import_module(
    f"{_DB_ALIAS}.classified_extracted_transaction",
).ClassifiedExtractedTransaction


def _parse_extracted_id(row_id: str | None) -> uuid.UUID | None:
    if not row_id:
        return None
    try:
        return uuid.UUID(str(row_id))
    except ValueError:
        return None


def persist_extracted_classifications(
    db: Session,
    *,
    financial_profile_id: uuid.UUID,
    document_id: uuid.UUID,
    rows: list[
        tuple[str | None, TransactionAnalysisResult, AnalyzeTransactionResponse, Decimal]
    ],
    classified_by: str | None = None,
) -> int:
    """Mark prior rows non-current and insert the latest classification per extracted row."""
    saved = 0

    for row_id, analysis, response, gross_amount_lkr in rows:
        extracted_id = _parse_extracted_id(row_id)
        if extracted_id is None:
            continue

        db.execute(
            update(ClassifiedExtractedTransaction)
            .where(
                ClassifiedExtractedTransaction.extracted_transaction_id == extracted_id,
                ClassifiedExtractedTransaction.is_current.is_(True),
            )
            .values(is_current=False),
        )

        db.add(
            ClassifiedExtractedTransaction(
                financial_profile_id=financial_profile_id,
                document_id=document_id,
                extracted_transaction_id=extracted_id,
                semantic_category=analysis.semantic_category,
                economic_event=analysis.economic_event,
                tax_rule_code=analysis.tax_rule_code,
                taxability_status=analysis.taxability_status.value,
                taxable_amount_lkr=analysis.taxable_amount_lkr,
                gross_amount_lkr=gross_amount_lkr,
                certainty_tier=analysis.certainty_tier,
                class_source=analysis.class_source,
                decision_mode=analysis.decision_mode,
                model_semantic_category=analysis.model_semantic_category,
                analysis_payload=response.model_dump(mode="json"),
                is_current=True,
                classified_by=classified_by,
            ),
        )
        saved += 1

    if saved:
        db.commit()
        recompute_profile_monthly_taxable_income(db, financial_profile_id=financial_profile_id)
    return saved


def load_current_classifications(
    db: Session,
    *,
    document_id: uuid.UUID,
    financial_profile_id: uuid.UUID | None = None,
) -> list[tuple[uuid.UUID, AnalyzeTransactionResponse]]:
    stmt = select(ClassifiedExtractedTransaction).where(
        ClassifiedExtractedTransaction.document_id == document_id,
        ClassifiedExtractedTransaction.is_current.is_(True),
    )
    if financial_profile_id is not None:
        stmt = stmt.where(
            ClassifiedExtractedTransaction.financial_profile_id == financial_profile_id,
        )

    rows = list(db.scalars(stmt.order_by(ClassifiedExtractedTransaction.classified_at.desc())).all())
    results: list[tuple[uuid.UUID, AnalyzeTransactionResponse]] = []
    seen: set[uuid.UUID] = set()
    for row in rows:
        if row.extracted_transaction_id in seen:
            continue
        seen.add(row.extracted_transaction_id)
        results.append(
            (
                row.extracted_transaction_id,
                AnalyzeTransactionResponse.model_validate(row.analysis_payload),
            ),
        )
    return results
