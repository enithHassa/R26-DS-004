"""Taxpayer portal transaction summary and curated transaction lists."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.profile import FinancialProfile as FinancialProfileORM
from app.models.user_transaction_flag import UserTransactionFlag
from app.schemas.taxable_income_monthly import ProfileTaxableIncomeMonthCoverage
from app.schemas.user_portal_transactions import (
    ProfileTransactionSummaryResponse,
    UserPortalActivityGroup,
    UserPortalActivityGroupsResponse,
    UserPortalNarrativeHit,
    UserPortalReasoningStep,
    UserPortalStatementItem,
    UserPortalTransactionDetailResponse,
    UserPortalTransactionItem,
    UserTransactionFlagResponse,
    UserPortalTransactionsResponse,
)
from app.services.profile_taxable_income_service import (
    _build_month_coverage,
    _resolve_tax_year,
)
from backend.shared.utils.assessment_year import (
    ya_bounds_from_orm_tax_year,
    ya_label_from_orm_tax_year,
)

_DB_ROOT = Path(__file__).resolve().parents[3] / "comp-transaction-sementic" / "db"
_DB_ALIAS = "comp_transaction_sementic_db_runtime"

_LARGE_NON_TAXABLE_THRESHOLD = Decimal("50000")

_STEP_TITLES: dict[str, str] = {
    "normalize": "Prepare transaction text",
    "layer1_bank_parse": "Bank narration parse",
    "narrative_context": "Narrative context",
    "semantic_classifier": "Semantic classification",
    "classification_guard": "Classification guard",
    "narrative_fusion": "Narrative fusion",
    "class_override": "Applied classification",
    "tax_rule_mapping": "Tax rule mapping",
}


class UserTransactionNotFoundError(LookupError):
    """Raised when a transaction is missing or not visible to the taxpayer portal."""


def _friendly_step_title(step_key: str) -> str:
    return _STEP_TITLES.get(step_key, step_key.replace("_", " ").title())


def _build_reasoning_steps(payload: dict) -> list[UserPortalReasoningStep]:
    steps: list[UserPortalReasoningStep] = []
    taxability = payload.get("taxability") or {}
    evidence = taxability.get("evidence") or {}
    for raw in evidence.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        step_key = str(raw.get("step") or "step")
        steps.append(
            UserPortalReasoningStep(
                step_key=step_key,
                title=_friendly_step_title(step_key),
                detail=str(raw.get("detail") or ""),
                is_decision=step_key == "tax_rule_mapping",
            ),
        )

    if not steps:
        confidence = (payload.get("confidence_report") or {}).get("top_probability")
        steps.extend(
            [
                UserPortalReasoningStep(
                    step_key="semantic_category",
                    title="Semantic classification",
                    detail=str(payload.get("semantic_category") or "unknown"),
                ),
                UserPortalReasoningStep(
                    step_key="economic_event",
                    title="Economic event",
                    detail=str(payload.get("economic_event") or "—"),
                ),
                UserPortalReasoningStep(
                    step_key="tax_rule",
                    title="Tax rule mapping",
                    detail=str(payload.get("rule_reference") or payload.get("tax_rule_code") or "—"),
                ),
                UserPortalReasoningStep(
                    step_key="decision",
                    title="Taxability decision",
                    detail=str((taxability.get("taxability_status") or payload.get("taxability_status") or "unknown")),
                    is_decision=True,
                ),
            ],
        )
        if confidence is not None:
            steps[0].detail = (
                f"{payload.get('semantic_category')} "
                f"(confidence {float(confidence) * 100:.0f}%)"
            )
    return steps


def _narrative_hits_from_payload(payload: dict) -> list[UserPortalNarrativeHit]:
    hits: list[UserPortalNarrativeHit] = []
    for raw in payload.get("narrative_hits") or []:
        if not isinstance(raw, dict):
            continue
        hits.append(
            UserPortalNarrativeHit(
                class_key=str(raw.get("class_key") or ""),
                score=float(raw.get("score") or 0),
                description=str(raw.get("description") or ""),
                default_taxability_status=str(raw.get("default_taxability_status") or ""),
            ),
        )
    hits.sort(key=lambda row: row.score, reverse=True)
    return hits[:5]


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


def _confidence_from_payload(payload: dict) -> float | None:
    report = payload.get("confidence_report") or {}
    raw = report.get("top_probability")
    if raw is None:
        taxability = payload.get("taxability") or {}
        raw = taxability.get("confidence")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _needs_review(
    *,
    taxability_status: str,
    certainty_tier: str | None,
    decision_mode: str | None,
) -> bool:
    if taxability_status == "unknown":
        return True
    if certainty_tier == "indeterminate":
        return True
    if decision_mode == "human_required":
        return True
    return False


def _is_curated_credit(
    *,
    direction: str,
    taxability_status: str,
    taxable_amount_lkr: Decimal,
    gross_amount_lkr: Decimal,
    certainty_tier: str | None,
    decision_mode: str | None,
) -> bool:
    if direction != "CR":
        return False
    if _needs_review(
        taxability_status=taxability_status,
        certainty_tier=certainty_tier,
        decision_mode=decision_mode,
    ):
        return True
    if taxable_amount_lkr > 0:
        return True
    if gross_amount_lkr >= _LARGE_NON_TAXABLE_THRESHOLD:
        return True
    return False


def _load_visible_rows(
    db: Session,
    *,
    profile_id: uuid.UUID,
    ya_start: date | None,
    ya_end: date | None,
) -> list[tuple[object, object, object]]:
    _load_db_package()
    ClassifiedExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.classified_extracted_transaction",
    ).ClassifiedExtractedTransaction
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document

    stmt = (
        select(ClassifiedExtractedTransaction, ExtractedTransaction, Document)
        .join(
            ExtractedTransaction,
            ExtractedTransaction.id == ClassifiedExtractedTransaction.extracted_transaction_id,
        )
        .join(Document, Document.id == ClassifiedExtractedTransaction.document_id)
        .where(
            ClassifiedExtractedTransaction.financial_profile_id == profile_id,
            ClassifiedExtractedTransaction.is_current.is_(True),
            Document.user_visible.is_(True),
        )
    )
    if ya_start is not None and ya_end is not None:
        stmt = stmt.where(
            ExtractedTransaction.tx_date >= ya_start,
            ExtractedTransaction.tx_date <= ya_end,
        )
    return list(db.execute(stmt).all())


def get_transaction_summary(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str | None = None,
) -> ProfileTransactionSummaryResponse:
    _load_db_package()
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction

    effective_tax_year = _resolve_tax_year(db, profile_id, tax_year)
    ya_start: date | None = None
    ya_end: date | None = None
    assessment_year_label: str | None = None
    month_coverage: list[ProfileTaxableIncomeMonthCoverage] = []
    covered_month_count = 0
    missing_month_count = 0

    if effective_tax_year and "_" in effective_tax_year:
        ya_start, ya_end = ya_bounds_from_orm_tax_year(effective_tax_year)
        assessment_year_label = ya_label_from_orm_tax_year(effective_tax_year)
        month_coverage, _, _ = _build_month_coverage(
            db,
            profile_id=profile_id,
            tax_year=effective_tax_year,
            rollup_lines=[],
            user_visible_only=True,
        )
        covered_month_count = sum(1 for row in month_coverage if row.status == "covered")
        missing_month_count = sum(1 for row in month_coverage if row.status == "missing")

    rows = _load_visible_rows(
        db,
        profile_id=profile_id,
        ya_start=ya_start,
        ya_end=ya_end,
    )

    total_extracted_credits = Decimal("0.00")
    total_taxable = Decimal("0.00")
    total_non_taxable = Decimal("0.00")
    review_count = 0
    visible_count = 0
    analyzed_count = 0

    for classified, extracted, _document in rows:
        direction = extracted.direction.value if hasattr(extracted.direction, "value") else str(
            extracted.direction,
        )
        gross = Decimal(classified.gross_amount_lkr or 0)
        taxable = Decimal(classified.taxable_amount_lkr or 0)
        if direction == "CR":
            total_extracted_credits += gross
            total_taxable += taxable
            non_taxable_part = max(gross - taxable, Decimal("0"))
            if non_taxable_part > 0:
                total_non_taxable += non_taxable_part
            analyzed_count += 1
        if _needs_review(
            taxability_status=classified.taxability_status,
            certainty_tier=classified.certainty_tier,
            decision_mode=classified.decision_mode,
        ):
            review_count += 1
        if _is_curated_credit(
            direction=direction,
            taxability_status=classified.taxability_status,
            taxable_amount_lkr=taxable,
            gross_amount_lkr=gross,
            certainty_tier=classified.certainty_tier,
            decision_mode=classified.decision_mode,
        ):
            visible_count += 1

    submitted_count = int(
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.financial_profile_id == profile_id,
                Document.submitted_by == "taxpayer",
            ),
        )
        or 0,
    )
    pending_count = int(
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.financial_profile_id == profile_id,
                Document.user_visible.is_(False),
                Document.status.in_(["submitted", "completed"]),
            ),
        )
        or 0,
    )

    compliance_score: int | None = None
    if analyzed_count > 0:
        resolved = max(analyzed_count - review_count, 0)
        compliance_score = int(round((resolved / analyzed_count) * 100))

    return ProfileTransactionSummaryResponse(
        financial_profile_id=str(profile_id),
        tax_year=effective_tax_year,
        assessment_year_label=assessment_year_label,
        total_extracted_credits_lkr=total_extracted_credits.quantize(Decimal("0.01")),
        total_taxable_lkr=total_taxable.quantize(Decimal("0.01")),
        total_non_taxable_lkr=total_non_taxable.quantize(Decimal("0.01")),
        review_count=review_count,
        visible_transaction_count=visible_count,
        analyzed_transaction_count=analyzed_count,
        compliance_score_pct=compliance_score,
        submitted_statement_count=submitted_count,
        pending_statement_count=pending_count,
        covered_month_count=covered_month_count,
        missing_month_count=missing_month_count,
        month_coverage=month_coverage,
    )


def list_user_statements(
    db: Session,
    *,
    profile_id: uuid.UUID,
) -> list[UserPortalStatementItem]:
    _load_db_package()
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction

    docs = list(
        db.scalars(
            select(Document)
            .where(Document.financial_profile_id == profile_id)
            .order_by(Document.uploaded_at.desc()),
        ).all(),
    )
    items: list[UserPortalStatementItem] = []
    for document in docs:
        row_count = int(
            db.scalar(
                select(func.count())
                .select_from(ExtractedTransaction)
                .where(ExtractedTransaction.document_id == document.id),
            )
            or 0,
        )
        status = document.status.value if hasattr(document.status, "value") else str(document.status)
        if document.user_visible:
            portal_status = "ready"
        elif status == "submitted":
            portal_status = "pending_review"
        elif status == "processing":
            portal_status = "processing"
        elif status == "failed":
            portal_status = "failed"
        else:
            portal_status = "under_review"
        items.append(
            UserPortalStatementItem(
                document_id=str(document.id),
                filename=document.filename,
                submitted_by=document.submitted_by,
                uploaded_at=document.uploaded_at,
                portal_status=portal_status,
                extracted_row_count=row_count,
                user_visible=document.user_visible,
            ),
        )
    return items


def list_user_transactions(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str | None = None,
    include_all: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> UserPortalTransactionsResponse:
    effective_tax_year = _resolve_tax_year(db, profile_id, tax_year)
    ya_start: date | None = None
    ya_end: date | None = None
    if effective_tax_year and "_" in effective_tax_year:
        ya_start, ya_end = ya_bounds_from_orm_tax_year(effective_tax_year)

    rows = _load_visible_rows(
        db,
        profile_id=profile_id,
        ya_start=ya_start,
        ya_end=ya_end,
    )

    curated: list[UserPortalTransactionItem] = []
    for classified, extracted, document in rows:
        direction = extracted.direction.value if hasattr(extracted.direction, "value") else str(
            extracted.direction,
        )
        gross = Decimal(classified.gross_amount_lkr or 0)
        taxable = Decimal(classified.taxable_amount_lkr or 0)
        if not include_all and not _is_curated_credit(
            direction=direction,
            taxability_status=classified.taxability_status,
            taxable_amount_lkr=taxable,
            gross_amount_lkr=gross,
            certainty_tier=classified.certainty_tier,
            decision_mode=classified.decision_mode,
        ):
            continue
        payload = classified.analysis_payload or {}
        curated.append(
            UserPortalTransactionItem(
                extracted_transaction_id=str(classified.extracted_transaction_id),
                document_id=str(document.id),
                tx_date=extracted.tx_date,
                description=extracted.description,
                amount_lkr=gross.quantize(Decimal("0.01")),
                direction=direction,
                semantic_category=classified.semantic_category,
                economic_event=classified.economic_event,
                taxability_status=classified.taxability_status,
                taxable_amount_lkr=taxable.quantize(Decimal("0.01")),
                confidence=_confidence_from_payload(payload),
                certainty_tier=classified.certainty_tier,
                needs_review=_needs_review(
                    taxability_status=classified.taxability_status,
                    certainty_tier=classified.certainty_tier,
                    decision_mode=classified.decision_mode,
                ),
            ),
        )

    curated.sort(key=lambda row: (row.tx_date, row.description), reverse=True)
    page = curated[offset : offset + limit]
    return UserPortalTransactionsResponse(
        financial_profile_id=str(profile_id),
        tax_year=effective_tax_year,
        items=page,
        total=len(curated),
        limit=limit,
        offset=offset,
        include_all=include_all,
    )


def get_user_transaction_detail(
    db: Session,
    *,
    profile_id: uuid.UUID,
    extracted_transaction_id: uuid.UUID,
) -> UserPortalTransactionDetailResponse:
    _load_db_package()
    ClassifiedExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.classified_extracted_transaction",
    ).ClassifiedExtractedTransaction
    ExtractedTransaction = importlib.import_module(
        f"{_DB_ALIAS}.extracted_transaction",
    ).ExtractedTransaction
    Document = importlib.import_module(f"{_DB_ALIAS}.document").Document

    row = db.execute(
        select(ClassifiedExtractedTransaction, ExtractedTransaction, Document)
        .join(
            ExtractedTransaction,
            ExtractedTransaction.id == ClassifiedExtractedTransaction.extracted_transaction_id,
        )
        .join(Document, Document.id == ClassifiedExtractedTransaction.document_id)
        .where(
            ClassifiedExtractedTransaction.financial_profile_id == profile_id,
            ClassifiedExtractedTransaction.extracted_transaction_id == extracted_transaction_id,
            ClassifiedExtractedTransaction.is_current.is_(True),
            Document.user_visible.is_(True),
        )
        .limit(1),
    ).first()
    if row is None:
        raise UserTransactionNotFoundError(
            f"Transaction {extracted_transaction_id} not found or not released to taxpayer portal.",
        )

    classified, extracted, document = row
    payload = classified.analysis_payload or {}
    taxability = payload.get("taxability") or {}
    direction = extracted.direction.value if hasattr(extracted.direction, "value") else str(
        extracted.direction,
    )
    gross = Decimal(classified.gross_amount_lkr or 0)
    taxable = Decimal(classified.taxable_amount_lkr or 0)
    flag = db.scalar(
        select(UserTransactionFlag).where(
            UserTransactionFlag.financial_profile_id == profile_id,
            UserTransactionFlag.extracted_transaction_id == extracted_transaction_id,
        ),
    )

    return UserPortalTransactionDetailResponse(
        extracted_transaction_id=str(classified.extracted_transaction_id),
        document_id=str(document.id),
        tx_date=extracted.tx_date,
        description=extracted.description,
        amount_lkr=gross.quantize(Decimal("0.01")),
        direction=direction,
        bank_detected=document.bank_detected,
        document_filename=document.filename,
        semantic_category=classified.semantic_category,
        economic_event=classified.economic_event,
        tax_rule_code=classified.tax_rule_code,
        rule_reference=payload.get("rule_reference"),
        explanation=payload.get("explanation"),
        taxability_status=classified.taxability_status,
        taxable_amount_lkr=taxable.quantize(Decimal("0.01")),
        certainty_tier=classified.certainty_tier,
        confidence=_confidence_from_payload(payload),
        class_source=classified.class_source,
        model_semantic_category=classified.model_semantic_category,
        review_reason=payload.get("review_reason"),
        evidence_needed=payload.get("evidence_needed"),
        decision_mode=classified.decision_mode or payload.get("decision_mode"),
        treatment=taxability.get("treatment"),
        narrative_hits=_narrative_hits_from_payload(payload),
        reasoning_steps=_build_reasoning_steps(payload),
        taxonomy_version=payload.get("taxonomy_version"),
        rulebook_version=payload.get("rulebook_version"),
        model_version=taxability.get("model_version"),
        flagged_for_adviser=flag is not None,
        flag_message=flag.message if flag else None,
    )


def _class_label(class_key: str) -> str:
    return class_key.replace("_", " ").title()


def list_activity_groups(
    db: Session,
    *,
    profile_id: uuid.UUID,
    tax_year: str | None = None,
) -> UserPortalActivityGroupsResponse:
    effective_tax_year = _resolve_tax_year(db, profile_id, tax_year)
    ya_start: date | None = None
    ya_end: date | None = None
    if effective_tax_year and "_" in effective_tax_year:
        ya_start, ya_end = ya_bounds_from_orm_tax_year(effective_tax_year)

    rows = _load_visible_rows(
        db,
        profile_id=profile_id,
        ya_start=ya_start,
        ya_end=ya_end,
    )

    buckets: dict[str, dict[str, Decimal | int]] = {}
    for classified, extracted, _document in rows:
        direction = extracted.direction.value if hasattr(extracted.direction, "value") else str(
            extracted.direction,
        )
        if direction != "CR":
            continue
        key = classified.semantic_category
        gross = Decimal(classified.gross_amount_lkr or 0)
        taxable = Decimal(classified.taxable_amount_lkr or 0)
        bucket = buckets.setdefault(
            key,
            {
                "transaction_count": 0,
                "total_amount_lkr": Decimal("0.00"),
                "taxable_amount_lkr": Decimal("0.00"),
                "review_count": 0,
            },
        )
        bucket["transaction_count"] = int(bucket["transaction_count"]) + 1
        bucket["total_amount_lkr"] = Decimal(bucket["total_amount_lkr"]) + gross
        bucket["taxable_amount_lkr"] = Decimal(bucket["taxable_amount_lkr"]) + taxable
        if _needs_review(
            taxability_status=classified.taxability_status,
            certainty_tier=classified.certainty_tier,
            decision_mode=classified.decision_mode,
        ):
            bucket["review_count"] = int(bucket["review_count"]) + 1

    groups = [
        UserPortalActivityGroup(
            class_key=key,
            label=_class_label(key),
            transaction_count=int(stats["transaction_count"]),
            total_amount_lkr=Decimal(stats["total_amount_lkr"]).quantize(Decimal("0.01")),
            taxable_amount_lkr=Decimal(stats["taxable_amount_lkr"]).quantize(Decimal("0.01")),
            review_count=int(stats["review_count"]),
        )
        for key, stats in buckets.items()
    ]
    groups.sort(key=lambda row: row.total_amount_lkr, reverse=True)

    return UserPortalActivityGroupsResponse(
        financial_profile_id=str(profile_id),
        tax_year=effective_tax_year,
        groups=groups,
    )


def flag_transaction_for_adviser(
    db: Session,
    *,
    profile_id: uuid.UUID,
    extracted_transaction_id: uuid.UUID,
    message: str | None,
) -> UserTransactionFlagResponse:
    # Ensure the transaction exists and is visible to the taxpayer.
    get_user_transaction_detail(
        db,
        profile_id=profile_id,
        extracted_transaction_id=extracted_transaction_id,
    )

    existing = db.scalar(
        select(UserTransactionFlag).where(
            UserTransactionFlag.financial_profile_id == profile_id,
            UserTransactionFlag.extracted_transaction_id == extracted_transaction_id,
        ),
    )
    if existing is None:
        existing = UserTransactionFlag(
            financial_profile_id=profile_id,
            extracted_transaction_id=extracted_transaction_id,
            message=message,
        )
        db.add(existing)
    else:
        existing.message = message
    db.commit()
    db.refresh(existing)

    return UserTransactionFlagResponse(
        extracted_transaction_id=str(extracted_transaction_id),
        flagged=True,
        message=existing.message,
        created_at=existing.created_at,
    )
