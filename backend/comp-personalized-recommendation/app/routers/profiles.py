"""Financial profile endpoints (FR1, FR2 — Phase 2 / WP4)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import (
    BehaviouralAnswer,
    BehaviouralAnswerBatchCreate,
    DerivedFeatures,
    EligibilityOverrideUpdate,
    FinancialProfile,
    FinancialProfileCreate,
    FinancialProfileUpdate,
    ProfileHistorySnapshot,
)
from app.services import behavioural_answer_service, history_service, profile_service
from app.services import profile_taxable_income_service, profile_user_portal_service, tax_computation_service
from backend.shared.schemas.common import PaginatedResponse
from app.schemas.taxable_income_monthly import (
    ProfileTaxableIncomeMonthDetailResponse,
    ProfileTaxableIncomeMonthlyResponse,
)
from app.schemas.user_portal_transactions import (
    ProfileTransactionSummaryResponse,
    UserPortalActivityGroupsResponse,
    UserPortalStatementItem,
    UserPortalTransactionDetailResponse,
    UserPortalTransactionsResponse,
    UserTransactionFlagRequest,
    UserTransactionFlagResponse,
)
from app.schemas.tax_computation_snapshot import (
    TaxComputationSnapshotDetail,
    TaxComputationSnapshotStatusUpdate,
    TaxComputationSnapshotSummary,
    TaxComputationSnapshotUpsert,
)

router = APIRouter()


def _profile_or_404(db: Session, profile_id: UUID) -> object:
    try:
        return profile_service.get_profile(db, profile_id)
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=FinancialProfile, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: FinancialProfileCreate,
    user_id: UUID | None = Query(
        None, description="Attach to an existing account instead of creating a placeholder user."
    ),
    db: Session = DBSession,
) -> FinancialProfile:
    """Create a new financial profile.

    If ``user_id`` is omitted, a placeholder user is auto-created (admin
    tooling / synthetic data); if given, the profile is attached to that
    already-registered account (first-login financial intake).
    """
    try:
        orm = profile_service.create_profile(db, payload, user_id=user_id)
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FinancialProfile.model_validate(orm)


@router.get(
    "",
    response_model=PaginatedResponse[FinancialProfile],
)
def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    occupation: str | None = Query(None, description="Filter by occupation enum value."),
    district: str | None = Query(None, description="Filter by Sri Lankan district."),
    db: Session = DBSession,
) -> PaginatedResponse[FinancialProfile]:
    page_result = profile_service.list_profiles(
        db, page=page, page_size=page_size, occupation=occupation, district=district
    )
    return PaginatedResponse[FinancialProfile](
        items=[FinancialProfile.model_validate(p) for p in page_result.items],
        total=page_result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/{profile_id}", response_model=FinancialProfile)
def get_profile(profile_id: UUID, db: Session = DBSession) -> FinancialProfile:
    orm = _profile_or_404(db, profile_id)
    return FinancialProfile.model_validate(orm)


@router.patch("/{profile_id}", response_model=FinancialProfile)
def update_profile(
    profile_id: UUID,
    payload: FinancialProfileUpdate,
    db: Session = DBSession,
) -> FinancialProfile:
    try:
        orm = profile_service.update_profile(db, profile_id, payload)
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FinancialProfile.model_validate(orm)


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_profile(profile_id: UUID, db: Session = DBSession) -> None:
    try:
        profile_service.delete_profile(db, profile_id)
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{profile_id}/features", response_model=DerivedFeatures)
def get_profile_features(profile_id: UUID, db: Session = DBSession) -> DerivedFeatures:
    """Derived features (disposable income, savings rate, eligibility flags, baseline tax)."""
    orm = _profile_or_404(db, profile_id)
    return profile_service.compute_derived_features(orm)


@router.get("/{profile_id}/history", response_model=list[ProfileHistorySnapshot])
def get_profile_history(
    profile_id: UUID,
    months: int = Query(36, ge=1, le=60),
    db: Session = DBSession,
) -> list[ProfileHistorySnapshot]:
    """Synthetic monthly financial history (income, expenses, balances) used
    to evidence whether a profile's trajectory supports adopting a
    recommended strategy. Generated deterministically on first request."""
    orm = _profile_or_404(db, profile_id)
    rows = history_service.get_or_create_history(db, orm, months=months)
    return [ProfileHistorySnapshot.model_validate(r) for r in rows]


@router.post("/{profile_id}/behavioural-answers", response_model=list[BehaviouralAnswer])
def submit_behavioural_answers(
    profile_id: UUID,
    payload: BehaviouralAnswerBatchCreate,
    db: Session = DBSession,
) -> list[BehaviouralAnswer]:
    """Record (or update) a taxpayer's answers to behavioural questions.

    Answers to a known question key (see `PROFILE_MAPPED_QUESTIONS`) are also
    written onto the profile itself, so the next recommendation call reflects
    them immediately.
    """
    try:
        rows = behavioural_answer_service.upsert_answers(db, profile_id, payload.answers)
    except behavioural_answer_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [BehaviouralAnswer.model_validate(r) for r in rows]


@router.get("/{profile_id}/behavioural-answers", response_model=list[BehaviouralAnswer])
def get_behavioural_answers(profile_id: UUID, db: Session = DBSession) -> list[BehaviouralAnswer]:
    try:
        rows = behavioural_answer_service.list_answers(db, profile_id)
    except behavioural_answer_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [BehaviouralAnswer.model_validate(r) for r in rows]


@router.patch("/{profile_id}/eligibility-overrides", response_model=DerivedFeatures)
def set_eligibility_override(
    profile_id: UUID,
    payload: EligibilityOverrideUpdate,
    db: Session = DBSession,
) -> DerivedFeatures:
    """Manually pin (or, with ``value: null``, clear) a single eligibility flag."""
    try:
        orm = profile_service.set_eligibility_override(
            db, profile_id, flag=payload.flag, value=payload.value
        )
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return profile_service.compute_derived_features(orm)


@router.get(
    "/{profile_id}/taxable-income/monthly",
    response_model=ProfileTaxableIncomeMonthlyResponse,
)
def get_profile_monthly_taxable_income(
    profile_id: UUID,
    tax_year: str | None = Query(None, description="Filter by assessment year label, e.g. 2024_25."),
    db: Session = DBSession,
) -> ProfileTaxableIncomeMonthlyResponse:
    _profile_or_404(db, profile_id)
    return profile_taxable_income_service.list_monthly_taxable_income(
        db,
        profile_id=profile_id,
        tax_year=tax_year,
    )


@router.get(
    "/{profile_id}/taxable-income/monthly/{calendar_month}",
    response_model=ProfileTaxableIncomeMonthDetailResponse,
)
def get_profile_monthly_taxable_income_detail(
    profile_id: UUID,
    calendar_month: date,
    tax_year: str | None = Query(None, description="Optional assessment year filter."),
    db: Session = DBSession,
) -> ProfileTaxableIncomeMonthDetailResponse:
    _profile_or_404(db, profile_id)
    return profile_taxable_income_service.get_monthly_taxable_income_detail(
        db,
        profile_id=profile_id,
        calendar_month=calendar_month,
        tax_year=tax_year,
    )


@router.post(
    "/{profile_id}/tax-computations",
    response_model=TaxComputationSnapshotDetail,
    status_code=status.HTTP_201_CREATED,
)
def save_profile_tax_computation(
    profile_id: UUID,
    payload: TaxComputationSnapshotUpsert,
    db: Session = DBSession,
) -> TaxComputationSnapshotDetail:
    _profile_or_404(db, profile_id)
    return tax_computation_service.save_snapshot(db, profile_id=profile_id, payload=payload)


@router.get(
    "/{profile_id}/tax-computations",
    response_model=list[TaxComputationSnapshotSummary],
)
def list_profile_tax_computations(
    profile_id: UUID,
    assessment_year: str | None = Query(None, description="Filter by assessment year, e.g. 2025_26."),
    limit: int = Query(20, ge=1, le=100),
    db: Session = DBSession,
) -> list[TaxComputationSnapshotSummary]:
    _profile_or_404(db, profile_id)
    return tax_computation_service.list_snapshots(
        db,
        profile_id=profile_id,
        assessment_year=assessment_year,
        limit=limit,
    )


@router.get(
    "/{profile_id}/tax-computations/latest",
    response_model=TaxComputationSnapshotDetail,
)
def get_latest_profile_tax_computation(
    profile_id: UUID,
    assessment_year: str | None = Query(None, description="Filter by assessment year, e.g. 2025_26."),
    prefer_status: str | None = Query(
        None,
        description="Prefer this status first: finalized | calculated | draft.",
    ),
    db: Session = DBSession,
) -> TaxComputationSnapshotDetail:
    _profile_or_404(db, profile_id)
    snapshot = tax_computation_service.get_latest_snapshot(
        db,
        profile_id=profile_id,
        assessment_year=assessment_year,
        prefer_status=prefer_status,
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshot found.")
    return snapshot


@router.get(
    "/{profile_id}/tax-computations/{snapshot_id}",
    response_model=TaxComputationSnapshotDetail,
)
def get_profile_tax_computation(
    profile_id: UUID,
    snapshot_id: UUID,
    db: Session = DBSession,
) -> TaxComputationSnapshotDetail:
    _profile_or_404(db, profile_id)
    try:
        return tax_computation_service.get_snapshot(
            db,
            profile_id=profile_id,
            snapshot_id=snapshot_id,
        )
    except tax_computation_service.SnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/{profile_id}/tax-computations/{snapshot_id}",
    response_model=TaxComputationSnapshotDetail,
)
def update_profile_tax_computation_status(
    profile_id: UUID,
    snapshot_id: UUID,
    payload: TaxComputationSnapshotStatusUpdate,
    db: Session = DBSession,
) -> TaxComputationSnapshotDetail:
    _profile_or_404(db, profile_id)
    try:
        return tax_computation_service.update_snapshot_status(
            db,
            profile_id=profile_id,
            snapshot_id=snapshot_id,
            status=payload.status,
        )
    except tax_computation_service.SnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{profile_id}/transaction-summary",
    response_model=ProfileTransactionSummaryResponse,
)
def get_profile_transaction_summary(
    profile_id: UUID,
    tax_year: str | None = Query(None, description="Assessment year label, e.g. 2025_26."),
    db: Session = DBSession,
) -> ProfileTransactionSummaryResponse:
    _profile_or_404(db, profile_id)
    return profile_user_portal_service.get_transaction_summary(
        db,
        profile_id=profile_id,
        tax_year=tax_year,
    )


@router.get(
    "/{profile_id}/user-transactions",
    response_model=UserPortalTransactionsResponse,
)
def list_profile_user_transactions(
    profile_id: UUID,
    tax_year: str | None = Query(None, description="Assessment year label, e.g. 2025_26."),
    include_all: bool = Query(False, description="Include all credit rows, not just curated view."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = DBSession,
) -> UserPortalTransactionsResponse:
    _profile_or_404(db, profile_id)
    return profile_user_portal_service.list_user_transactions(
        db,
        profile_id=profile_id,
        tax_year=tax_year,
        include_all=include_all,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{profile_id}/user-statements",
    response_model=list[UserPortalStatementItem],
)
def list_profile_user_statements(
    profile_id: UUID,
    db: Session = DBSession,
) -> list[UserPortalStatementItem]:
    _profile_or_404(db, profile_id)
    return profile_user_portal_service.list_user_statements(db, profile_id=profile_id)


@router.get(
    "/{profile_id}/user-transactions/{extracted_transaction_id}",
    response_model=UserPortalTransactionDetailResponse,
)
def get_profile_user_transaction_detail(
    profile_id: UUID,
    extracted_transaction_id: UUID,
    db: Session = DBSession,
) -> UserPortalTransactionDetailResponse:
    _profile_or_404(db, profile_id)
    try:
        return profile_user_portal_service.get_user_transaction_detail(
            db,
            profile_id=profile_id,
            extracted_transaction_id=extracted_transaction_id,
        )
    except profile_user_portal_service.UserTransactionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{profile_id}/transaction-activity-groups",
    response_model=UserPortalActivityGroupsResponse,
)
def list_profile_transaction_activity_groups(
    profile_id: UUID,
    tax_year: str | None = Query(None, description="Assessment year label, e.g. 2025_26."),
    db: Session = DBSession,
) -> UserPortalActivityGroupsResponse:
    _profile_or_404(db, profile_id)
    return profile_user_portal_service.list_activity_groups(
        db,
        profile_id=profile_id,
        tax_year=tax_year,
    )


@router.post(
    "/{profile_id}/user-transactions/{extracted_transaction_id}/flag",
    response_model=UserTransactionFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
def flag_profile_user_transaction(
    profile_id: UUID,
    extracted_transaction_id: UUID,
    payload: UserTransactionFlagRequest,
    db: Session = DBSession,
) -> UserTransactionFlagResponse:
    _profile_or_404(db, profile_id)
    try:
        return profile_user_portal_service.flag_transaction_for_adviser(
            db,
            profile_id=profile_id,
            extracted_transaction_id=extracted_transaction_id,
            message=payload.message,
        )
    except profile_user_portal_service.UserTransactionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
