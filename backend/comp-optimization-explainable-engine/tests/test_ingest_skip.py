"""Ingest skips an identical PDF by sha256 (no OpenAI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.shared.config.database import Base
from db.models import OeEngineDocument
from oe_engine_app.services.embedder import HashEmbedder
from oe_engine_app.services.ingest import ingest_pdf
from oe_engine_app.services.pdf_extract import DualExtract


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_ingest_skips_matching_sha256(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "act.pdf"
    pdf.write_bytes(b"%PDF-1.4\nidentical-bytes\n")
    extract = DualExtract(
        pages=[(1, "Relief for expenditure on solar panels.")],
        tables_by_page={},
        page_count=1,
        table_method=None,
    )
    monkeypatch.setattr(
        "oe_engine_app.services.ingest.extract_dual_text",
        lambda _path: extract,
    )
    monkeypatch.setattr(
        "oe_engine_app.services.ingest.build_chunks",
        lambda **_kwargs: [
            {
                "chunk_id": "oee-act-10-2021::p0001::c0000",
                "text": "Relief for expenditure on solar panels.",
                "page": 1,
                "chunk_index": 0,
                "channel": "text_stream",
                "section_ref": "Section 5",
            }
        ],
    )
    monkeypatch.setattr(
        "oe_engine_app.services.ingest.write_manifest_sha256",
        lambda *_args, **_kwargs: None,
    )
    row = {
        "source_doc_id": "oee-act-10-2021",
        "title": "Act 10 of 2021",
        "tier": "act",
        "instrument_type": "amendment_act",
    }
    embedder = HashEmbedder()
    first = ingest_pdf(
        db_session, pdf_path=pdf, row=row, embedder=embedder, update_manifest=False
    )
    assert first.status == "ingested"
    assert first.chunk_count == 1
    second = ingest_pdf(
        db_session, pdf_path=pdf, row=row, embedder=embedder, update_manifest=False
    )
    assert second.status == "skipped_sha256"
    assert db_session.query(OeEngineDocument).count() == 1
