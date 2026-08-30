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
    ProfileTaxableIncomeMonthCoverage,
    ProfileTaxableIncomeMonthDetailLine,
    ProfileTaxableIncomeMonthDetailResponse,
    ProfileTaxableIncomeMonthlyLine,
    ProfileTaxableIncomeMonthlyResponse,
)
from app.models.profile import FinancialProfile as FinancialProfileORM
from backend.shared.db.profile_taxable_income_monthly import ProfileTaxableIncomeMonthly
from backend.shared.utils.assessment_year import (
    month_start,
    ya_bounds_from_orm_tax_year,
    ya_calendar_month_starts,
    ya_label_from_orm_tax_year,
)

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


def _resolve_tax_year(
    db: Session,
    profile_id: uuid.UUID,
    tax_year: str | None,
) -> str | None:
    if tax_year:
        return tax_year
    profile = db.get(FinancialProfileORM, profile_id)
    if profile is None:
        return None
    return profile.tax_year or None


def _month_activity_for_ya(
    db: Session,
    *,
    profile_id: uuid.UUID,
    ya_start: date,
    ya_end: date,
    user_visible_only: bool = False,
) -> dict[date, dict[str, Decimal | int]]:
    """Per-month counts from all extracted rows on profile-owned documents."""
    _load_db_package()
    ClassifiedExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.classified_extracted_transaction",
    ).ClassifiedExtractedTransaction
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document

    def _empty_bucket() -> dict[str, Decimal | int]:
        return {
            "extracted_transaction_count": 0,
            "classified_transaction_count": 0,
            "taxable_credit_count": 0,
            "taxable_amount_lkr": Decimal("0.00"),
        }

    activity: dict[date, dict[str, Decimal | int]] = {}

    extracted_stmt = (
        select(ExtractedTransaction.tx_date)
        .join(Document, Document.id == ExtractedTransaction.document_id)
        .where(
            Document.financial_profile_id == profile_id,
            ExtractedTransaction.tx_date >= ya_start,
            ExtractedTransaction.tx_date <= ya_end,
        )
    )
    if user_visible_only:
        extracted_stmt = extracted_stmt.where(Document.user_visible.is_(True))
    for (tx_date,) in db.execute(extracted_stmt).all():
        bucket_month = month_start(tx_date)
        entry = activity.setdefault(bucket_month, _empty_bucket())
        entry["extracted_transaction_count"] = int(entry["extracted_transaction_count"]) + 1

    classified_stmt = (
        select(
            ExtractedTransaction.tx_date,
            ClassifiedExtractedTransaction.taxable_amount_lkr,
        )
        .join(
            ExtractedTransaction,
            ExtractedTransaction.id == ClassifiedExtractedTransaction.extracted_transaction_id,
        )
        .join(Document, Document.id == ClassifiedExtractedTransaction.document_id)
        .where(
            ClassifiedExtractedTransaction.financial_profile_id == profile_id,
            ClassifiedExtractedTransaction.is_current.is_(True),
            ExtractedTransaction.tx_date >= ya_start,
            ExtractedTransaction.tx_date <= ya_end,
        )
    )
    if user_visible_only:
        classified_stmt = classified_stmt.where(Document.user_visible.is_(True))
    for tx_date, taxable_raw in db.execute(classified_stmt).all():
        bucket_month = month_start(tx_date)
        entry = activity.setdefault(bucket_month, _empty_bucket())
        entry["classified_transaction_count"] = int(entry["classified_transaction_count"]) + 1
        taxable = Decimal(taxable_raw or 0)
        if taxable > 0:
            entry["taxable_credit_count"] = int(entry["taxable_credit_count"]) + 1
            entry["taxable_amount_lkr"] = Decimal(entry["taxable_amount_lkr"]) + taxable
    return activity


def _build_month_coverage(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str,
    rollup_lines: list[ProfileTaxableIncomeMonthlyLine],
    user_visible_only: bool = False,
) -> tuple[list[ProfileTaxableIncomeMonthCoverage], date, date]:
    ya_start, ya_end = ya_bounds_from_orm_tax_year(tax_year)
    activity = _month_activity_for_ya(
        db,
        profile_id=profile_id,
        ya_start=ya_start,
        ya_end=ya_end,
        user_visible_only=user_visible_only,
    )

    taxable_by_month: dict[date, Decimal] = {}
    for line in rollup_lines:
        month = month_start(line.calendar_month)
        taxable_by_month[month] = taxable_by_month.get(month, Decimal("0.00")) + line.taxable_amount_lkr

    coverage: list[ProfileTaxableIncomeMonthCoverage] = []
    for month in ya_calendar_month_starts(tax_year):
        stats = activity.get(month)
        extracted_count = int(stats["extracted_transaction_count"]) if stats else 0
        classified_count = int(stats["classified_transaction_count"]) if stats else 0
        taxable_count = int(stats["taxable_credit_count"]) if stats else 0
        taxable_amount = taxable_by_month.get(month, Decimal("0.00"))
        if taxable_amount <= 0 and stats:
            taxable_amount = Decimal(stats["taxable_amount_lkr"]).quantize(Decimal("0.01"))

        coverage.append(
            ProfileTaxableIncomeMonthCoverage(
                calendar_month=month,
                month_label=month.strftime("%b %Y"),
                status="covered" if extracted_count > 0 else "missing",
                extracted_transaction_count=extracted_count,
                classified_transaction_count=classified_count,
                taxable_credit_count=taxable_count,
                taxable_amount_lkr=taxable_amount.quantize(Decimal("0.01")),
            ),
        )
    return coverage, ya_start, ya_end


def list_monthly_taxable_income(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str | None = None,
) -> ProfileTaxableIncomeMonthlyResponse:
    effective_tax_year = _resolve_tax_year(db, profile_id, tax_year)

    stmt = select(ProfileTaxableIncomeMonthly).where(
        ProfileTaxableIncomeMonthly.financial_profile_id == profile_id,
    )
    rows = list(
        db.scalars(
            stmt.order_by(
                ProfileTaxableIncomeMonthly.calendar_month.asc(),
                ProfileTaxableIncomeMonthly.class_key.asc(),
            ),
        ).all(),
    )
    if effective_tax_year and "_" in effective_tax_year:
        try:
            ya_start, ya_end = ya_bounds_from_orm_tax_year(effective_tax_year)
            first_month = date(ya_start.year, ya_start.month, 1)
            last_month = date(ya_end.year, ya_end.month, 1)
            rows = [
                row
                for row in rows
                if first_month <= row.calendar_month <= last_month
            ]
        except ValueError:
            pass
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

    month_coverage: list[ProfileTaxableIncomeMonthCoverage] = []
    ya_period_start: date | None = None
    ya_period_end: date | None = None
    assessment_year_label: str | None = None
    covered_month_count = 0
    missing_month_count = 0

    if effective_tax_year and "_" in effective_tax_year:
        try:
            month_coverage, ya_period_start, ya_period_end = _build_month_coverage(
                db,
                profile_id=profile_id,
                tax_year=effective_tax_year,
                rollup_lines=lines,
            )
            assessment_year_label = ya_label_from_orm_tax_year(effective_tax_year)
            covered_month_count = sum(1 for row in month_coverage if row.status == "covered")
            missing_month_count = sum(1 for row in month_coverage if row.status == "missing")
        except ValueError:
            month_coverage = []

    return ProfileTaxableIncomeMonthlyResponse(
        financial_profile_id=str(profile_id),
        tax_year=effective_tax_year,
        assessment_year_label=assessment_year_label,
        ya_period_start=ya_period_start,
        ya_period_end=ya_period_end,
        total_taxable_lkr=total.quantize(Decimal("0.01")),
        covered_month_count=covered_month_count,
        missing_month_count=missing_month_count,
        month_coverage=month_coverage,
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
        try:
            ya_start, ya_end = ya_bounds_from_orm_tax_year(tax_year)
            stmt = stmt.where(
                ExtractedTransaction.tx_date >= ya_start,
                ExtractedTransaction.tx_date <= ya_end,
            )
        except ValueError:
            pass

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
