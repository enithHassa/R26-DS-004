"""Hybrid retrieve finds a known phrase without OpenAI."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.shared.config.database import Base
from db.models import OeEngineChunk, OeEngineDocument
from oe_engine_app.services.embedder import HashEmbedder
from oe_engine_app.services.retrieve import hybrid_retrieve


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


def test_retrieve_hits_solar_panels(db_session: Session) -> None:
    db_session.add(
        OeEngineDocument(
            source_doc_id="oee-act-10-2021",
            file_name="IR_Act_No._10_2021_E.pdf",
            title="Act 10 of 2021",
            tier="act",
            sha256="abc",
            byte_size=1,
            page_count=1,
            chunk_count=2,
        )
    )
    embedder = HashEmbedder()
    solar = "A resident individual may deduct expenditure incurred on solar panels."
    other = "Chargeable income of a company is computed under this Act."
    solar_vec, other_vec = embedder.embed_batch([solar, other])
    db_session.add_all(
        [
            OeEngineChunk(
                chunk_id="c-solar",
                source_doc_id="oee-act-10-2021",
                channel="text_stream",
                page=3,
                chunk_index=0,
                text=solar,
                embedding_json=json.dumps(solar_vec),
                embedding_model=embedder.model,
            ),
            OeEngineChunk(
                chunk_id="c-other",
                source_doc_id="oee-act-10-2021",
                channel="text_stream",
                page=1,
                chunk_index=1,
                text=other,
                embedding_json=json.dumps(other_vec),
                embedding_model=embedder.model,
            ),
        ]
    )
    db_session.commit()
    query_vec = embedder.embed_batch(["solar panels"])[0]
    hits = hybrid_retrieve(
        db_session,
        query="solar panels",
        query_embedding=query_vec,
        source_doc_id="oee-act-10-2021",
        top_k=2,
    )
    assert hits
    assert hits[0].chunk_id == "c-solar"
    assert "solar panels" in hits[0].text.lower()
