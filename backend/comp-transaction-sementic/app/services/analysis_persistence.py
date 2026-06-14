"""Persist analyzed transactions, labels, and taxability outputs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.shared.db.enums import TxnDirection as DBTxnDirection
from backend.shared.db.transaction import Transaction as TransactionModel

from .component_db import (
    label_source_enum,
    taxability_output_model,
    taxability_status_enum,
    transaction_label_model,
)
from .transaction_analyzer import TransactionAnalysisResult


def persist_transaction_analysis(
    db: Session,
    *,
    raw_desc: str,
    amount_lkr: Decimal,
    tx_date: date,
    direction: str,
    bank_code: str | None,
    source_type: str,
    analysis: TransactionAnalysisResult,
    raw_payload: dict | None = None,
) -> TransactionModel:
    TaxabilityOutputORM = taxability_output_model()
    TransactionLabel = transaction_label_model()
    LabelSource = label_source_enum()
    DBTaxabilityStatus = taxability_status_enum()

    tx = TransactionModel(
        id=analysis.transaction_id,
        raw_desc=raw_desc,
        normalized_desc=analysis.text_primary,
        amount_lkr=amount_lkr,
        tx_date=tx_date,
        direction=DBTxnDirection(direction),
        bank_code=bank_code,
        source_type=source_type,
        raw_payload=raw_payload,
    )
    db.add(tx)
    db.add(
        TransactionLabel(
            tx_id=analysis.transaction_id,
            semantic_category=analysis.semantic_category,
            economic_event=analysis.economic_event,
            tax_rule_code=analysis.tax_rule_code,
            label_source=LabelSource.WEAK,
            confidence=analysis.confidence_report.top_probability,
        ),
    )
    db.add(
        TaxabilityOutputORM(
            tx_id=analysis.transaction_id,
            taxability_status=DBTaxabilityStatus(analysis.taxability_status.value),
            taxable_amount=analysis.taxable_amount_lkr,
            confidence=analysis.confidence_report.top_probability,
            evidence=analysis.evidence.model_dump(mode="json"),
            model_version=analysis.model_version,
            model_run_id=None,
        ),
    )
    db.commit()
    db.refresh(tx)
    return tx
