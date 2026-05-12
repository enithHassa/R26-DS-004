"""SQLite corpus ingest smoke test."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ird_corpus_sqlite", _ROOT / "ird_corpus_sqlite.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


@pytest.fixture()
def sample_jsonl(tmp_path: Path) -> Path:
    p = tmp_path / "sample.jsonl"
    p.write_text(
        '{"chunk_id":"doc::p0001::c0000","source_doc_id":"doc","corpus_version":"corpus_v1",'
        '"content_kind":"text","page":1,"chunk_index":0,"tier":"A","instrument_type":"act",'
        '"text":"hello"}\n',
        encoding="utf-8",
    )
    return p


def test_ingest_jsonl_roundtrip(sample_jsonl: Path, tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    conn = _mod.connect(db)
    try:
        n = _mod.ingest_jsonl(conn, sample_jsonl)
        assert n == 1
        cur = conn.execute("SELECT chunk_id, tier FROM corpus_chunks")
        row = cur.fetchone()
        assert row == ("doc::p0001::c0000", "A")
    finally:
        conn.close()
