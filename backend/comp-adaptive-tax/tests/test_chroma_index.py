"""Unit tests for AdaptiveTaxChromaIndex helpers (no embedding download)."""

from __future__ import annotations

from adaptive_tax_app.services.chroma_index import (
    CHROMA_BLOCKED_SOURCE_DOC_IDS,
    DEFAULT_COLLECTION,
    DEFAULT_EMBEDDING_MODEL,
    chunk_metadata_for_chroma,
    iter_corpus_rows,
)


def test_defaults_match_phase6_contract() -> None:
    assert DEFAULT_COLLECTION == "ird_legal_evidence_v1"
    assert "MiniLM" in DEFAULT_EMBEDDING_MODEL or "minilm" in DEFAULT_EMBEDDING_MODEL.lower()


def test_iter_corpus_rows_skips_guide_and_master(tmp_path) -> None:
    path = tmp_path / "c.jsonl"
    rows = [
        {
            "chunk_id": "g1",
            "source_doc_id": "ird-guide-ira",
            "text": "guide wording",
            "section_ref": "Section 52",
        },
        {
            "chunk_id": "m1",
            "source_doc_id": "ird-calc-ontology-v5",
            "text": "master ontology",
            "section_ref": "Section 52",
        },
        {
            "chunk_id": "ok",
            "source_doc_id": "ird-ira-2017-base",
            "text": "Section 52 qualifying payments",
            "section_ref": "Section 52",
        },
    ]
    path.write_text("\n".join(__import__("json").dumps(r) for r in rows) + "\n", encoding="utf-8")
    kept = list(iter_corpus_rows(path))
    assert [r["chunk_id"] for r in kept] == ["ok"]
    assert CHROMA_BLOCKED_SOURCE_DOC_IDS >= {"ird-guide-ira", "ird-calc-ontology-v5"}


def test_chunk_metadata_scalars_only() -> None:
    meta = chunk_metadata_for_chroma(
        {
            "chunk_id": "x",
            "source_doc_id": "ird-ira-2017-base",
            "section_ref": ["Section 5", "Section 6"],
            "paragraph_ref": "5(1)",
            "applicable_assessment_years": ["2024_25", "2025_26"],
            "is_operative_provision": True,
            "is_toc": False,
            "chunk_part": 1,
            "chunk_parts": 1,
            "parent_provision_id": "sec5_1",
            "instrument_type": "base_act",
            "page": 15,
            "effective_start_date": "2018-04-01",
        }
    )
    assert meta["section_num"] == "5"
    assert meta["applicable_yas"] == "2024_25,2025_26"
    assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())
