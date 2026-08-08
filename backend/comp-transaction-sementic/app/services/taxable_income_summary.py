"""Aggregate taxable / non-taxable income lines for a date window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from backend.shared.db.transaction import Transaction as TransactionModel
from backend.shared.schemas.enums import TaxabilityStatus

from .component_db import taxability_output_model, transaction_label_model

TaxabilityOutputORM = taxability_output_model()
TransactionLabel = transaction_label_model()


@dataclass(frozen=True)
class TaxableIncomeLine:
    class_key: str
    tax_rule_code: str | None
    taxability_status: str
    transaction_count: int
    gross_amount_lkr: Decimal
    taxable_amount_lkr: Decimal


@dataclass(frozen=True)
class TaxableIncomeSummary:
    date_from: date
    date_to: date
    total_taxable_lkr: Decimal
    total_excluded_lkr: Decimal
    review_count: int
    transaction_count: int
    taxable_lines: list[TaxableIncomeLine]
    non_taxable_lines: list[TaxableIncomeLine]
    review_lines: list[TaxableIncomeLine]


def _latest_taxability_subquery() -> Select[Any]:
    return (
        select(
            TaxabilityOutputORM.tx_id.label("tx_id"),
            TaxabilityOutputORM.id.label("output_id"),
        )
        .distinct(TaxabilityOutputORM.tx_id)
        .order_by(TaxabilityOutputORM.tx_id, TaxabilityOutputORM.created_at.desc())
    )


def _latest_label_subquery() -> Select[Any]:
    return (
        select(
            TransactionLabel.tx_id.label("tx_id"),
            TransactionLabel.semantic_category.label("semantic_category"),
            TransactionLabel.tax_rule_code.label("tax_rule_code"),
        )
        .distinct(TransactionLabel.tx_id)
        .order_by(TransactionLabel.tx_id, TransactionLabel.created_at.desc())
    )


def build_taxable_income_summary(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    bank_code: str | None = None,
) -> TaxableIncomeSummary:
    latest_tax = _latest_taxability_subquery().subquery()
    latest_label = _latest_label_subquery().subquery()

    stmt = (
        select(
            TransactionModel,
            TaxabilityOutputORM,
            latest_label.c.semantic_category,
            latest_label.c.tax_rule_code,
        )
        .join(latest_tax, latest_tax.c.tx_id == TransactionModel.id)
        .join(TaxabilityOutputORM, TaxabilityOutputORM.id == latest_tax.c.output_id)
        .outerjoin(latest_label, latest_label.c.tx_id == TransactionModel.id)
        .where(
            and_(
                TransactionModel.tx_date >= date_from,
                TransactionModel.tx_date <= date_to,
            ),
        )
    )
    if bank_code:
        stmt = stmt.where(TransactionModel.bank_code == bank_code)

    rows = db.execute(stmt).all()
    taxable_buckets: dict[tuple[str, str | None, str], dict[str, Any]] = {}
    non_taxable_buckets: dict[tuple[str, str | None, str], dict[str, Any]] = {}
    review_buckets: dict[tuple[str, str | None, str], dict[str, Any]] = {}

    total_taxable = Decimal("0.00")
    total_excluded = Decimal("0.00")
    review_count = 0

    for tx, output, class_key, rule_code in rows:
        class_key = class_key or "unknown"
        status = output.taxability_status.value
        gross = Decimal(tx.amount_lkr)
        taxable = Decimal(output.taxable_amount or 0)
        key = (class_key, rule_code, status)
        bucket_map = taxable_buckets
        if status in {TaxabilityStatus.EXEMPT.value}:
            bucket_map = non_taxable_buckets
            total_excluded += gross
        elif status == TaxabilityStatus.UNKNOWN.value or (
            output.confidence is not None and output.confidence < 0.35
        ):
            bucket_map = review_buckets
            review_count += 1
        else:
            total_taxable += taxable
        bucket = bucket_map.setdefault(
            key,
            {
                "transaction_count": 0,
                "gross_amount_lkr": Decimal("0.00"),
                "taxable_amount_lkr": Decimal("0.00"),
            },
        )
        bucket["transaction_count"] += 1
        bucket["gross_amount_lkr"] += gross
        bucket["taxable_amount_lkr"] += taxable

    def _to_lines(buckets: dict[tuple[str, str | None, str], dict[str, Any]]) -> list[TaxableIncomeLine]:
        lines = [
            TaxableIncomeLine(
                class_key=key[0],
                tax_rule_code=key[1],
                taxability_status=key[2],
                transaction_count=values["transaction_count"],
                gross_amount_lkr=values["gross_amount_lkr"],
                taxable_amount_lkr=values["taxable_amount_lkr"],
            )
            for key, values in buckets.items()
        ]
        return sorted(lines, key=lambda line: line.taxable_amount_lkr, reverse=True)

    return TaxableIncomeSummary(
        date_from=date_from,
        date_to=date_to,
        total_taxable_lkr=total_taxable,
        total_excluded_lkr=total_excluded,
        review_count=review_count,
        transaction_count=len(rows),
        taxable_lines=_to_lines(taxable_buckets),
        non_taxable_lines=_to_lines(non_taxable_buckets),
        review_lines=_to_lines(review_buckets),
    )
