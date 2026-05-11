"""Phase 3 Step 15 — corpus JSONL → KG join metadata map."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.corpus_chunk_kg_join import load_chunk_kg_join_by_id


def test_load_chunk_kg_join_section_uid_matches_etl(tmp_path: Path) -> None:
    corpus = tmp_path / "c.jsonl"
    row = {
        "chunk_id": "doc::p0001::c0001",
        "text": "Relief text.",
        "source_doc_id": "ird-act-99",
        "section_ref": ["Part II — Personal Relief"],
        "tier": "A",
        "instrument_type": "act",
        "content_kind": "text",
    }
    corpus.write_text(json.dumps(row) + "\n", encoding="utf-8")

    m = load_chunk_kg_join_by_id(corpus)
    assert "doc::p0001::c0001" in m
    hit = m["doc::p0001::c0001"]
    assert hit["source_doc_id"] == "ird-act-99"
    assert hit["tier"] == "A"
    assert hit["instrument_type"] == "act"
    assert hit["content_kind"] == "text"
    assert hit["section_label"] == "Part II — Personal Relief"
    assert hit["section_uid"] == "ird-act-99::sec::part_ii_personal_relief"


def test_load_chunk_kg_join_minimal_row_no_section(tmp_path: Path) -> None:
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        json.dumps({"chunk_id": "bare::1", "text": "x", "source_doc_id": "s1"}) + "\n",
        encoding="utf-8",
    )
    m = load_chunk_kg_join_by_id(corpus)
    assert m["bare::1"]["source_doc_id"] == "s1"
    assert m["bare::1"]["section_uid"] is None
    assert m["bare::1"]["section_label"] is None
