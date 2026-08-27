"""Load hand-built extract fixtures (no live GPT)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.shared.config.settings import PROJECT_ROOT
from db.models import OeEngineChunk, OeEngineDocument
from oe_engine_app.schemas.extract import ExtractRun
from sqlalchemy.orm import Session

FIXTURE_DIR = PROJECT_ROOT / "models" / "opt-explain-engine" / "fixtures"


def load_extract_fixture(name: str) -> ExtractRun:
    path = FIXTURE_DIR / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExtractRun.model_validate(payload)


def seed_act_document(
    session: Session,
    *,
    source_doc_id: str,
    title: str = "Fixture Act",
    with_chunk: bool = True,
) -> OeEngineDocument:
    existing = session.get(OeEngineDocument, source_doc_id)
    if existing is None:
        digest = f"{source_doc_id}-fixture-sha256".ljust(64, "0")[:64]
        existing = OeEngineDocument(
            source_doc_id=source_doc_id,
            file_name=f"{source_doc_id}.pdf",
            title=title,
            tier="act",
            instrument_type="fixture",
            sha256=digest,
            byte_size=1,
            page_count=1,
            chunk_count=1 if with_chunk else 0,
        )
        session.add(existing)
        session.flush()
    if with_chunk:
        chunk_id = f"{source_doc_id}::p0001::c0000"
        if session.get(OeEngineChunk, chunk_id) is None:
            session.add(
                OeEngineChunk(
                    chunk_id=chunk_id,
                    source_doc_id=source_doc_id,
                    channel="text_stream",
                    page=1,
                    chunk_index=0,
                    text="Personal relief solar panels First Schedule taxable income.",
                    section_ref="Fifth Schedule",
                )
            )
            existing.chunk_count = 1
    else:
        session.query(OeEngineChunk).filter(
            OeEngineChunk.source_doc_id == source_doc_id
        ).delete()
        existing.chunk_count = 0
    session.flush()
    return existing


def _extracted_run(source_doc_id: str, extraction_run_id: str | None) -> ExtractRun | None:
    try:
        from oe_engine_app.config import get_oe_engine_settings

        settings_out = get_oe_engine_settings().OE_ENGINE_EXTRACT_OUT
    except Exception:  # noqa: BLE001
        return None
    if not settings_out or not settings_out.is_dir():
        return None
    wanted = (extraction_run_id or "").strip() or None
    if wanted:
        named = settings_out / f"{source_doc_id}__{wanted}.json"
        if named.is_file():
            return ExtractRun.model_validate(json.loads(named.read_text(encoding="utf-8")))
    current = settings_out / f"{source_doc_id}__current.json"
    if current.is_file():
        payload = json.loads(current.read_text(encoding="utf-8"))
        if not wanted or payload.get("extraction_run_id") == wanted:
            return ExtractRun.model_validate(payload)
    return None


def load_promote_run(source_doc_id: str, extraction_run_id: str | None) -> ExtractRun:
    wanted = (extraction_run_id or "").strip() or None
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        if path.name.startswith("extract_schema_"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_doc_id") != source_doc_id:
            continue
        if payload.get("tier") not in (None, "act"):
            continue
        if wanted and payload.get("extraction_run_id") != wanted:
            continue
        return ExtractRun.model_validate(payload)
    extracted = _extracted_run(source_doc_id, wanted)
    if extracted is not None:
        return extracted
    raise FileNotFoundError(
        f"no extract run for {source_doc_id!r} extraction_run_id={extraction_run_id!r}"
    )


def fixture_path(name: str) -> Path:
    return FIXTURE_DIR / name


def list_extract_fixtures() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        if path.name.startswith("extract_schema_"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("source_doc_id"):
            continue
        if payload.get("tier") not in {"act", "guide", "consolidated"}:
            continue
        rows.append(
            {
                "file_name": path.name,
                "source_doc_id": payload.get("source_doc_id"),
                "tier": payload.get("tier"),
                "extraction_run_id": payload.get("extraction_run_id"),
                "terminus": payload.get("terminus"),
                "entity_count": len(payload.get("entities") or []),
            }
        )
    return rows
