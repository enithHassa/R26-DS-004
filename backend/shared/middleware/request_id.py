"""Propagate ``X-Request-ID`` for traceability across services and logs."""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.shared.request_context import reset_request_id, set_request_id

REQUEST_ID_HEADER = "x-request-id"
CORRELATION_HEADER = "x-correlation-id"
_MAX_REQUEST_ID_LEN = 128


def _incoming_request_id(request: Request) -> str | None:
    return request.headers.get(REQUEST_ID_HEADER) or request.headers.get(
        CORRELATION_HEADER
    )


def _normalize_or_generate(raw: str | None) -> str:
    if raw is None:
        return str(uuid.uuid4())
    s = raw.strip()
    if not s:
        return str(uuid.uuid4())
    return s[:_MAX_REQUEST_ID_LEN]


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Set ``request.state.request_id``, bind ``contextvars``, echo header on response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        rid = _normalize_or_generate(_incoming_request_id(request))
        token = set_request_id(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = rid
            return response
        finally:
            reset_request_id(token)
