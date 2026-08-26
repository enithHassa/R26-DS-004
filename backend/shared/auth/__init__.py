"""Shared account auth (login / signup) for the API gateway and Comp 3.

Account rows live in the ``users`` table. Financial profiles and
recommendations stay in Component 3; login only resolves an optional
``profile_id`` by reading ``financial_profiles``.
"""

from backend.shared.auth.models import User
from backend.shared.auth.router import router as auth_router
from backend.shared.auth.schemas import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)

__all__ = [
    "User",
    "LoginRequest",
    "LoginResponse",
    "SignupRequest",
    "SignupResponse",
    "auth_router",
]
