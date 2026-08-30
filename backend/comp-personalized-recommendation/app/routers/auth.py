"""Auth routes for Comp 3 — shared service, local DB dependency.

Identity logic lives in ``backend.shared.auth``. The same routes are also
mounted on the API gateway at ``/api/v1/auth``. Comp 3 keeps these paths so
direct :8003 calls and existing tests continue to work. Financial profile
listing and recommendations stay in Comp 3 routers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from backend.shared.auth import service as auth_service
from backend.shared.auth.schemas import LoginRequest, LoginResponse, SignupRequest, SignupResponse

router = APIRouter()


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
