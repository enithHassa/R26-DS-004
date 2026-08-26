"""User View login/sign-up contracts (customer-facing dashboard, not the
admin tool).

Login accepts either the account email or a profile's legacy ``full_name``
(e.g. ``Taxpayer_25265``, for pre-seeded demo data) as ``username``; password
is a plaintext value. This is prototype-grade auth only — see
``services.profile_service`` and migrations ``0004_add_user_password`` /
``0008_expand_user_account_fields``.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=64)


class LoginResponse(BaseModel):
    role: Literal["auditor", "taxpayer"]
    full_name: str
    user_id: str | None = None
    profile_id: str | None = None


class SignupRequest(BaseModel):
    """New taxpayer account — personal/contact details only.

    The financial profile and behavioural questions are collected on first
    login, not here (see ``routers.profiles``).
    """

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_RE)
    mobile_number: str = Field(min_length=5, max_length=32)
    country: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    gender: Literal["male", "female", "other"]
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    profile_picture: str | None = Field(default=None, max_length=2_000_000)
    password: str = Field(min_length=6, max_length=64)
    confirm_password: str = Field(min_length=6, max_length=64)

    @model_validator(mode="after")
    def _passwords_match(self) -> SignupRequest:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class SignupResponse(BaseModel):
    user_id: str
    email: str
    full_name: str


__all__ = ["LoginRequest", "LoginResponse", "SignupRequest", "SignupResponse"]
