"""Async-safe request correlation via ``contextvars`` (Starlette/FastAPI)."""

from __future__ import annotations

import contextvars

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the active ``X-Request-ID``, or ``"-"`` outside a request scope."""
    rid = _request_id.get("")
    return rid if rid else "-"


def set_request_id(value: str) -> contextvars.Token[str]:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token[str]) -> None:
    _request_id.reset(token)
