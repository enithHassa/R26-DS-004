"""User View login contracts (customer-facing dashboard, not the admin tool).

Username is the profile's ``full_name`` (e.g. ``Taxpayer_25265``); password
is a plaintext value derived from that name (see ``services.profile_service``
and migration ``0004_add_user_password``). This is prototype-grade auth only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=64)


class LoginResponse(BaseModel):
    role: Literal["auditor", "taxpayer"]
    full_name: str
    user_id: str | None = None
    profile_id: str | None = None


__all__ = ["LoginRequest", "LoginResponse"]
