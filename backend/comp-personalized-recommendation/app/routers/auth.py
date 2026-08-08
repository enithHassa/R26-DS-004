"""Common login for Component 3 — routes to the auditor admin tool or the
customer-facing User View dashboard depending on who's signing in."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import DBSession
from app.schemas import LoginRequest, LoginResponse
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
        profile_id=str(profile.id),
    )
