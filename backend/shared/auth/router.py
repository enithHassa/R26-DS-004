"""Shared auth HTTP routes — mounted on the gateway and re-used by Comp 3."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth import service as auth_service
from backend.shared.auth.schemas import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from backend.shared.config.database import get_db as _get_db

router = APIRouter()


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()


DBSession = Depends(get_db)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = DBSession) -> LoginResponse:
    if (
        payload.username == auth_service.AUDITOR_USERNAME
        and payload.password == auth_service.AUDITOR_PASSWORD
    ):
        return LoginResponse(role="auditor", full_name=auth_service.AUDITOR_USERNAME)

    try:
        user, profile_id = auth_service.authenticate_user(db, payload.username, payload.password)
    except auth_service.AmbiguousLoginError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(
        role="taxpayer",
        user_id=str(user.id),
        full_name=user.full_name or "",
        profile_id=str(profile_id) if profile_id is not None else None,
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = DBSession) -> SignupResponse:
    """Create a new taxpayer account (personal/contact details only)."""
    try:
        user = auth_service.create_account(
            db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            mobile_number=payload.mobile_number,
            country=payload.country,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            address=payload.address,
            city=payload.city,
            postal_code=payload.postal_code,
            profile_picture=payload.profile_picture,
        )
    except auth_service.EmailTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SignupResponse(user_id=str(user.id), email=user.email, full_name=user.full_name or "")
