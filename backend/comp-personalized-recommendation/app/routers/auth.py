"""Common login for Component 3 — routes to the auditor admin tool or the
customer-facing User View dashboard depending on who's signing in."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from app.services import profile_service

router = APIRouter()

# Single hardcoded auditor account for the admin tool (profile management,
# recommendations, impact, compare). Prototype-grade auth only — see
# schemas/auth.py.
_AUDITOR_USERNAME = "Auditor"
_AUDITOR_PASSWORD = "auditor@123"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = DBSession) -> LoginResponse:
    if payload.username == _AUDITOR_USERNAME and payload.password == _AUDITOR_PASSWORD:
        return LoginResponse(role="auditor", full_name=_AUDITOR_USERNAME)

    try:
        user, profile = profile_service.authenticate_user(db, payload.username, payload.password)
    except profile_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(
        role="taxpayer",
        user_id=str(user.id),
        full_name=user.full_name or "",
        # None here means "account exists but hasn't completed the financial
        # intake yet" — the frontend routes to that flow instead of the portal.
        profile_id=str(profile.id) if profile is not None else None,
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = DBSession) -> SignupResponse:
    """Create a new taxpayer account (personal/contact details only).

    Does not log the user in — the frontend sends them to the login screen
    afterwards, per the sign-up flow's "create account, then sign in"
    requirement. The financial profile and behavioural questions are
    collected on that first login instead.
    """
    try:
        user = profile_service.create_account(
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
    except profile_service.EmailTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SignupResponse(user_id=str(user.id), email=user.email, full_name=user.full_name or "")
