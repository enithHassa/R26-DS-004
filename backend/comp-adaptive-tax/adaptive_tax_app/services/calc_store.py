"""Phase 4 — persist CalculateTaxResponse under a UUID calc_id (JSON files)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    StoredCalculationV1,
)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class CalcStoreError(RuntimeError):
    """Raised when the calculation store cannot read or write."""


def _validate_calc_id(calc_id: str) -> uuid.UUID:
    text = (calc_id or "").strip()
    if not _UUID_RE.fullmatch(text):
        raise ValueError(f"invalid calc_id: {calc_id!r}")
    return uuid.UUID(text)


def _store_path(store_dir: Path, calc_id: uuid.UUID) -> Path:
    store_dir = store_dir.resolve()
    path = (store_dir / f"{calc_id}.json").resolve()
    if path.parent != store_dir:
        raise ValueError("calc_id resolves outside store directory")
    return path


def save(
    request: CalculateTaxRequestV1,
    response: CalculateTaxResponseV1,
    *,
    settings: AdaptiveTaxSettings | None = None,
    amendment_context: dict[str, Any] | None = None,
    calc_id: str | None = None,
) -> str:
    """Persist request/response JSON and return the assigned ``calc_id`` (UUID4)."""
    cfg = settings or get_adaptive_tax_settings()
    store_dir = cfg.calc_store_dir
    store_dir.mkdir(parents=True, exist_ok=True)

    uid = _validate_calc_id(calc_id) if calc_id else uuid.uuid4()

    enriched = response.model_copy(update={"calc_id": str(uid)})
    record = StoredCalculationV1(
        calc_id=str(uid),
        created_at=datetime.now(timezone.utc),
        request=request,
        response=enriched,
        param_set_effective=request.param_set,
        amendment_context=amendment_context,
    )

    path = _store_path(store_dir, uid)
    try:
        path.write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CalcStoreError(f"failed to write calculation {uid}: {exc}") from exc
    return str(uid)


def load(
    calc_id: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> StoredCalculationV1 | None:
    """Load a stored calculation, or ``None`` if missing."""
    cfg = settings or get_adaptive_tax_settings()
    try:
        uid = _validate_calc_id(calc_id)
    except ValueError:
        return None

    path = _store_path(cfg.calc_store_dir, uid)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalcStoreError(f"failed to read calculation {uid}: {exc}") from exc
    return StoredCalculationV1.model_validate(raw)
