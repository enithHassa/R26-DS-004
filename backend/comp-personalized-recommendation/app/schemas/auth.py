"""User View login/sign-up contracts — re-exported from shared auth."""

from backend.shared.auth.schemas import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)

__all__ = ["LoginRequest", "LoginResponse", "SignupRequest", "SignupResponse"]
