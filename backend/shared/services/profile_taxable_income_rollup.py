"""Recompute monthly taxable income buckets from saved document classifications."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.shared.db.enums import TxnDirection
from backend.shared.db.financial_profile_ref import FinancialProfileRef  # noqa: F401
from backend.shared.db.profile_taxable_income_monthly import ProfileTaxableIncomeMonthly

_DB_ROOT = Path(__file__).resolve().parents[2] / "comp-transaction-sementic" / "db"
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


def _month_start(tx_date: date) -> date:
    return tx_date.replace(day=1)


@dataclass(frozen=True)
class MonthlyRollupBucket:
    tax_year: str | None
    calendar_month: date
    class_key: str
    taxable_amount_lkr: Decimal
    transaction_count: int
    source_document_ids: list[str]


def _collect_rollup_buckets(db: Session, financial_profile_id: uuid.UUID) -> list[MonthlyRollupBucket]:
    _load_db_package()
    ClassifiedExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.classified_extracted_transaction",
    ).ClassifiedExtractedTransaction
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document

    stmt = (
        select(
            ClassifiedExtractedTransaction,
            ExtractedTransaction,
            Document.tax_year,
        )
        .join(
            ExtractedTransaction,
            ExtractedTransaction.id == ClassifiedExtractedTransaction.extracted_transaction_id,
        )
        .join(Document, Document.id == ClassifiedExtractedTransaction.document_id)
        .where(
            ClassifiedExtractedTransaction.financial_profile_id == financial_profile_id,
            ClassifiedExtractedTransaction.is_current.is_(True),
            ExtractedTransaction.direction == TxnDirection.CR,
            ClassifiedExtractedTransaction.taxable_amount_lkr > 0,
        )
    )
    rows = db.execute(stmt).all()

    buckets: dict[tuple[str | None, date, str], dict] = defaultdict(
        lambda: {
            "taxable_amount_lkr": Decimal("0.00"),
            "transaction_count": 0,
            "source_document_ids": set(),
        },
    )
    for classification, extracted, tax_year in rows:
        normalized_tax_year = tax_year or ""
        key = (
            normalized_tax_year,
            _month_start(extracted.tx_date),
            classification.semantic_category,
        )
        bucket = buckets[key]
        bucket["taxable_amount_lkr"] += Decimal(classification.taxable_amount_lkr)
        bucket["transaction_count"] += 1
        bucket["source_document_ids"].add(str(classification.document_id))

    return [
        MonthlyRollupBucket(
            tax_year=tax_year or None,
            calendar_month=calendar_month,
            class_key=class_key,
            taxable_amount_lkr=values["taxable_amount_lkr"].quantize(Decimal("0.01")),
            transaction_count=values["transaction_count"],
            source_document_ids=sorted(values["source_document_ids"]),
        )
        for (tax_year, calendar_month, class_key), values in sorted(
            buckets.items(),
            key=lambda item: (item[0][1], item[0][2]),
        )
    ]


def recompute_profile_monthly_taxable_income(
    db: Session,
    *,
    financial_profile_id: uuid.UUID,
) -> int:
    """Replace monthly rollup rows for a profile from current classifications."""
    buckets = _collect_rollup_buckets(db, financial_profile_id)
    db.execute(
        delete(ProfileTaxableIncomeMonthly).where(
            ProfileTaxableIncomeMonthly.financial_profile_id == financial_profile_id,
        ),
    )
    for bucket in buckets:
        db.add(
            ProfileTaxableIncomeMonthly(
                financial_profile_id=financial_profile_id,
                tax_year=bucket.tax_year or None,
                calendar_month=bucket.calendar_month,
                class_key=bucket.class_key,
                taxable_amount_lkr=bucket.taxable_amount_lkr,
                transaction_count=bucket.transaction_count,
                source_document_ids=bucket.source_document_ids,
            ),
        )
    if buckets:
        db.commit()
    else:
        db.commit()
    return len(buckets)
