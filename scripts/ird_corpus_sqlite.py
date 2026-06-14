#!/usr/bin/env python3
"""SQLite store for corpus_v1 JSONL (Phase 1b JSON + DB deliverable).

Usage::

  python scripts/ird_corpus_sqlite.py ingest --corpus-jsonl data/processed/ird/corpus_v1.jsonl \\
    --db data/processed/ird/corpus_v1.sqlite

Re-running ingest upserts rows by chunk_id (replace).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS corpus_chunks (
          chunk_id TEXT PRIMARY KEY,
          source_doc_id TEXT NOT NULL,
          corpus_version TEXT,
          content_kind TEXT,
          page INTEGER,
          chunk_index INTEGER,
          tier TEXT,
          instrument_type TEXT,
          json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_corpus_source ON corpus_chunks(source_doc_id);
        CREATE INDEX IF NOT EXISTS idx_corpus_tier ON corpus_chunks(tier);
        CREATE INDEX IF NOT EXISTS idx_corpus_version ON corpus_chunks(corpus_version);
        """
    )
    conn.commit()


def ingest_jsonl(conn: sqlite3.Connection, corpus_jsonl: Path) -> int:
    ensure_schema(conn)
    n = 0
    with corpus_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            chunk_id = obj["chunk_id"]
            conn.execute(
                """
                INSERT INTO corpus_chunks (
                  chunk_id, source_doc_id, corpus_version, content_kind,
                  page, chunk_index, tier, instrument_type, json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                  source_doc_id=excluded.source_doc_id,
                  corpus_version=excluded.corpus_version,
                  content_kind=excluded.content_kind,
                  page=excluded.page,
                  chunk_index=excluded.chunk_index,
                  tier=excluded.tier,
                  instrument_type=excluded.instrument_type,
                  json=excluded.json
                """,
                (
                    chunk_id,
                    obj.get("source_doc_id") or "",
                    obj.get("corpus_version"),
                    obj.get("content_kind"),
                    obj.get("page"),
                    obj.get("chunk_index"),
                    obj.get("tier"),
                    obj.get("instrument_type"),
                    json.dumps(obj, ensure_ascii=False),
                ),
            )
            n += 1
    conn.commit()
    return n


def cmd_ingest(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    try:
        n = ingest_jsonl(conn, args.corpus_jsonl)
    finally:
        conn.close()
    print(f"ingested {n} chunks -> {args.db}")


def cmd_stats(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    try:
        ensure_schema(conn)
        cur = conn.execute("SELECT COUNT(*) FROM corpus_chunks")
        total = cur.fetchone()[0]
        cur = conn.execute(
            "SELECT source_doc_id, COUNT(*) FROM corpus_chunks GROUP BY source_doc_id ORDER BY 2 DESC"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    print(f"total chunks: {total}")
    for sid, c in rows:
        print(f"  {sid}: {c}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Corpus SQLite tools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Load JSONL into SQLite")
    p_ingest.add_argument("--corpus-jsonl", type=Path, required=True)
    p_ingest.add_argument("--db", type=Path, default=Path("data/processed/ird/corpus_v1.sqlite"))
    p_ingest.set_defaults(func=cmd_ingest)

    p_stats = sub.add_parser("stats", help="Row counts by source_doc_id")
    p_stats.add_argument("--db", type=Path, default=Path("data/processed/ird/corpus_v1.sqlite"))
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
