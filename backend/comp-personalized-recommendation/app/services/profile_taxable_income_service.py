"""Read monthly taxable income rollups stored per financial profile."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.taxable_income_monthly import (
    ProfileTaxableIncomeMonthDetailLine,
    ProfileTaxableIncomeMonthDetailResponse,
    ProfileTaxableIncomeMonthlyLine,
    ProfileTaxableIncomeMonthlyResponse,
)
from backend.shared.db.profile_taxable_income_monthly import ProfileTaxableIncomeMonthly

_DB_ROOT = Path(__file__).resolve().parents[3] / "comp-transaction-sementic" / "db"
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


def list_monthly_taxable_income(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str | None = None,
) -> ProfileTaxableIncomeMonthlyResponse:
    stmt = select(ProfileTaxableIncomeMonthly).where(
        ProfileTaxableIncomeMonthly.financial_profile_id == profile_id,
    )
    if tax_year is not None:
        stmt = stmt.where(ProfileTaxableIncomeMonthly.tax_year == tax_year)
    rows = list(
        db.scalars(
            stmt.order_by(
                ProfileTaxableIncomeMonthly.calendar_month.asc(),
                ProfileTaxableIncomeMonthly.class_key.asc(),
            ),
        ).all(),
    )
    lines = [
        ProfileTaxableIncomeMonthlyLine(
            tax_year=row.tax_year,
            calendar_month=row.calendar_month,
            class_key=row.class_key,
            taxable_amount_lkr=row.taxable_amount_lkr,
            transaction_count=row.transaction_count,
            source_document_ids=list(row.source_document_ids or []),
            computed_at=row.computed_at,
        )
        for row in rows
    ]
    total = sum((line.taxable_amount_lkr for line in lines), Decimal("0.00"))
    return ProfileTaxableIncomeMonthlyResponse(
        financial_profile_id=str(profile_id),
        tax_year=tax_year,
        total_taxable_lkr=total.quantize(Decimal("0.01")),
        lines=lines,
    )


def get_monthly_taxable_income_detail(
    db: Session,
    *,
    profile_id: uuid.UUID,
    calendar_month: date,
    tax_year: str | None = None,
) -> ProfileTaxableIncomeMonthDetailResponse:
    _load_db_package()
    ClassifiedExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.classified_extracted_transaction",
    ).ClassifiedExtractedTransaction
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document

    if calendar_month.month == 12:
        next_month = calendar_month.replace(year=calendar_month.year + 1, month=1, day=1)
    else:
        next_month = calendar_month.replace(month=calendar_month.month + 1, day=1)

    stmt = (
        select(ClassifiedExtractedTransaction, ExtractedTransaction, Document.tax_year)
        .join(
            ExtractedTransaction,
            ExtractedTransaction.id == ClassifiedExtractedTransaction.extracted_transaction_id,
        )
        .join(Document, Document.id == ClassifiedExtractedTransaction.document_id)
        .where(
            ClassifiedExtractedTransaction.financial_profile_id == profile_id,
            ClassifiedExtractedTransaction.is_current.is_(True),
            ExtractedTransaction.tx_date >= calendar_month,
            ExtractedTransaction.tx_date < next_month,
            ClassifiedExtractedTransaction.taxable_amount_lkr > 0,
        )
        .order_by(ExtractedTransaction.tx_date.asc(), ExtractedTransaction.row_no.asc())
    )
    if tax_year is not None:
        stmt = stmt.where(Document.tax_year == tax_year)

    rows = db.execute(stmt).all()
    detail_lines: list[ProfileTaxableIncomeMonthDetailLine] = []
    total = Decimal("0.00")
    for classification, extracted, _doc_tax_year in rows:
        taxable = Decimal(classification.taxable_amount_lkr)
        total += taxable
        detail_lines.append(
            ProfileTaxableIncomeMonthDetailLine(
                extracted_transaction_id=str(classification.extracted_transaction_id),
                document_id=str(classification.document_id),
                tx_date=extracted.tx_date,
                description=extracted.description,
                gross_amount_lkr=Decimal(classification.gross_amount_lkr),
                taxable_amount_lkr=taxable,
                class_key=classification.semantic_category,
                taxability_status=classification.taxability_status,
            ),
        )

    return ProfileTaxableIncomeMonthDetailResponse(
        financial_profile_id=str(profile_id),
        calendar_month=calendar_month,
        tax_year=tax_year,
        total_taxable_lkr=total.quantize(Decimal("0.01")),
        lines=detail_lines,
    )
