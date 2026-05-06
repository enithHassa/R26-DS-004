"""HTTP client for Component 1 income aggregate (Option B orchestration)."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from backend.shared.config.settings import settings
from backend.shared.schemas.income_snapshot import IncomeSnapshotV1


class IncomeSnapshotClientError(Exception):
    """Raised when the transaction service cannot return a valid snapshot."""


async def fetch_income_snapshot(
    *,
    user_id: str,
    assessment_year: str,
    transaction_base_url: str | None = None,
    timeout_s: float = 15.0,
) -> IncomeSnapshotV1:
    """GET ``/api/v1/users/{user_id}/income-snapshot`` on Component 1."""
    base = (transaction_base_url or settings.COMP_TRANSACTION_URL).rstrip("/")
    url = f"{base}/api/v1/users/{quote(user_id)}/income-snapshot"
    timeout = httpx.Timeout(timeout_s, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(url, params={"assessment_year": assessment_year})
        except httpx.RequestError as exc:
            msg = f"Transaction service unreachable: {exc}"
            raise IncomeSnapshotClientError(msg) from exc
    if resp.status_code != 200:
        snippet = (resp.text or "")[:500]
        msg = f"Transaction service returned HTTP {resp.status_code}: {snippet}"
        raise IncomeSnapshotClientError(msg)
    try:
        return IncomeSnapshotV1.model_validate(resp.json())
    except Exception as exc:
        raise IncomeSnapshotClientError(f"Invalid income snapshot payload: {exc}") from exc


__all__ = ["IncomeSnapshotClientError", "fetch_income_snapshot"]
