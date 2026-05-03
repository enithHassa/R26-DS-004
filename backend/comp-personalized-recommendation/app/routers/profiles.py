"""Financial profile endpoints (FR1, FR2 — Phase 2 / WP4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import (
    DerivedFeatures,
    FinancialProfile,
    FinancialProfileCreate,
    FinancialProfileUpdate,
)
from app.services import profile_service
from backend.shared.schemas.common import PaginatedResponse

router = APIRouter()


def _profile_or_404(db: Session, profile_id: UUID) -> object:
    try:
        return profile_service.get_profile(db, profile_id)
    except profile_service.ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=FinancialProfile, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: FinancialProfileCreate,
    db: Session = DBSession,
) -> FinancialProfile:
    """Create a new financial profile (auto-creates a placeholder user)."""
    orm = profile_service.create_profile(db, payload)
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


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
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
