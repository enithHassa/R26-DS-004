"""Embedded Chroma index for Adaptive Tax legal RAG (Phase 2).

Uses a local PersistentClient under ``CHROMA_PERSIST_DIR`` (no Docker server).
Shared by ``scripts/adaptive_tax_build_chroma.py``, approve re-index, and
``POST /knowledge/rag/search``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_COLLECTION = "ird_legal_evidence_v1"

# Phase 6.0 — never index Guide / Master into the tax evidence Chroma collection.
CHROMA_BLOCKED_SOURCE_DOC_IDS = frozenset(
    {
        "ird-calc-ontology-v5",
        "ird-guide-ira",
    }
)


@dataclass(frozen=True)
class RagHit:
    chunk_id: str
    text: str
    score: float | None
    source_doc_id: str | None
    section_ref: str | None
    page: int | None
    metadata: dict[str, Any]


def _stringify_section_ref(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [str(x).strip() for x in value if str(x).strip()]
        return " | ".join(parts)
    return str(value)


def _section_num_from_ref(section_ref: Any) -> str:
    """Primary section number / schedule key for retrieval filters (scalar)."""
    text = _stringify_section_ref(section_ref)
    if not text:
        return ""
    # Prefer first "Section N" token when multi-ref joined with " | "
    primary = text.split("|")[0].strip()
    if re.fullmatch(r"(?i)first\s+schedule", primary) or re.search(
        r"(?i)\bfirst\s+schedule\b", primary
    ):
        return "first_schedule"
    m = re.search(r"(?i)\bsection\s+(\d+[a-z]?)\b", primary)
    if m:
        return m.group(1)
    m2 = re.fullmatch(r"(\d+[a-z]?)", primary)
    if m2:
        return m2.group(1)
    return ""


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n", ""}:
        return False
    return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _applicable_yas_scalar(row: dict[str, Any]) -> str:
    """Chroma-safe comma-joined YA list (never invent)."""
    yas = row.get("applicable_yas")
    if yas is None:
        yas = row.get("applicable_assessment_years")
    parts: list[str] = []
    if isinstance(yas, list):
        for x in yas:
            s = str(x).strip()
            if not s:
                continue
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s.replace("'", '"'))
                    if isinstance(parsed, list):
                        parts.extend(str(p).strip() for p in parsed if str(p).strip())
                        continue
                except json.JSONDecodeError:
                    pass
            parts.append(s)
    elif isinstance(yas, str) and yas.strip():
        s = yas.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s.replace("'", '"'))
                if isinstance(parsed, list):
                    parts = [str(p).strip() for p in parsed if str(p).strip()]
                else:
                    parts = [s]
            except json.JSONDecodeError:
                parts = [p.strip() for p in re.split(r"[|,]", s) if p.strip()]
        else:
            parts = [p.strip() for p in re.split(r"[|,]", s) if p.strip()]
    return ",".join(dict.fromkeys(parts))


def chunk_metadata_for_chroma(row: dict[str, Any]) -> dict[str, Any]:
    """Build Chroma-safe scalar metadata from a corpus JSONL row.

    Chroma metadata values must be str | int | float | bool (no lists/dicts).
    Guide/Master rows are filtered by ``iter_corpus_rows`` before indexing.
    """
    page = _as_int(row.get("page"), default=0)
    section_ref = _stringify_section_ref(row.get("section_ref"))
    paragraph = row.get("paragraph_ref")
    paragraph_ref = "" if paragraph is None else str(paragraph).strip()

    chunk_id = str(row.get("chunk_id") or "")
    parent = row.get("parent_provision_id")
    return {
        "chunk_id": chunk_id,
        "source_doc_id": str(row.get("source_doc_id") or ""),
        "section_ref": section_ref,
        "section_num": _section_num_from_ref(row.get("section_ref"))
        or _section_num_from_ref(row.get("schedule_ref")),
        "paragraph_ref": paragraph_ref,
        "parent_provision_id": "" if parent is None else str(parent),
        "chunk_part": _as_int(row.get("chunk_part"), default=1),
        "chunk_parts": _as_int(row.get("chunk_parts"), default=1),
        "is_operative_provision": _as_bool(row.get("is_operative_provision")),
        "is_toc": _as_bool(row.get("is_toc")),
        "is_header_footer": _as_bool(row.get("is_header_footer")),
        "is_cross_reference": _as_bool(row.get("is_cross_reference")),
        "instrument_type": str(row.get("instrument_type") or ""),
        "page": page,
        "effective_start_date": str(row.get("effective_start_date") or ""),
        "applicable_yas": _applicable_yas_scalar(row),
        "metadata_source": str(row.get("metadata_source") or "deterministic"),
        "needs_review": _as_bool(row.get("needs_review")),
    }


def iter_corpus_rows(path: Path, *, limit: int | None = None) -> Iterable[dict[str, Any]]:
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            source_doc_id = str(row.get("source_doc_id") or "").strip()
            if source_doc_id in CHROMA_BLOCKED_SOURCE_DOC_IDS:
                continue
            text = row.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            chunk_id = row.get("chunk_id")
            if not chunk_id:
                continue
            yield row
            n += 1
            if limit is not None and n >= limit:
                break


class AdaptiveTaxChromaIndex:
    """Thin wrapper around chromadb PersistentClient + MiniLM embeddings."""

    def __init__(
        self,
        *,
        persist_dir: Path,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._client: Any | None = None
        self._collection: Any | None = None

    def _ensure_collection(self, *, reset: bool = False) -> Any:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))

        if reset:
            try:
                self._client.delete_collection(self.collection_name)
            except Exception:  # noqa: BLE001 — collection may not exist
                pass
            self._collection = None

        if self._collection is None:
            ef = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def count(self) -> int:
        return int(self._ensure_collection().count())

    def upsert_chunks(self, rows: Sequence[dict[str, Any]], *, batch_size: int = 64) -> int:
        """Upsert corpus-shaped rows. Returns number of documents written."""
        collection = self._ensure_collection()
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        written = 0

        def flush() -> None:
            nonlocal written, ids, documents, metadatas
            if not ids:
                return
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            written += len(ids)
            ids, documents, metadatas = [], [], []

        for row in rows:
            text = row.get("text")
            chunk_id = row.get("chunk_id")
            if not isinstance(text, str) or not text.strip() or not chunk_id:
                continue
            ids.append(str(chunk_id))
            documents.append(text)
            metadatas.append(chunk_metadata_for_chroma(row))
            if len(ids) >= batch_size:
                flush()
        flush()
        return written

    def upsert_from_corpus_jsonl(
        self,
        corpus_jsonl: Path,
        *,
        limit: int | None = None,
        batch_size: int = 64,
        reset: bool = False,
    ) -> int:
        self._ensure_collection(reset=reset)
        rows = list(iter_corpus_rows(corpus_jsonl, limit=limit))
        return self.upsert_chunks(rows, batch_size=batch_size)

    def search(
        self,
        query: str,
        *,
        section_ref: str | None = None,
        source_doc_id: str | None = None,
        top_k: int = 5,
    ) -> list[RagHit]:
        """Semantic search; optional metadata filters on section_ref / source_doc_id."""
        q = (query or "").strip()
        if not q:
            return []
        collection = self._ensure_collection()
        where: dict[str, Any] | None = None
        if source_doc_id and source_doc_id.strip():
            where = {"source_doc_id": source_doc_id.strip()}

        # Over-fetch when filtering by section_ref (substring match is client-side;
        # Chroma metadata where-clauses are equality / $in only).
        n_results = max(1, top_k)
        if section_ref and section_ref.strip():
            n_results = max(n_results * 8, 40)

        kwargs: dict[str, Any] = {"query_texts": [q], "n_results": n_results}
        if where is not None:
            kwargs["where"] = where

        result = collection.query(**kwargs)

        hits: list[RagHit] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, chunk_id in enumerate(ids):
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            dist = dists[i] if i < len(dists) else None
            score = None if dist is None else float(1.0 - float(dist))
            page_raw = meta.get("page")
            try:
                page = int(page_raw) if page_raw is not None and page_raw != "" else None
            except (TypeError, ValueError):
                page = None
            hits.append(
                RagHit(
                    chunk_id=str(chunk_id),
                    text=str(docs[i] if i < len(docs) else ""),
                    score=score,
                    source_doc_id=str(meta["source_doc_id"]) if meta.get("source_doc_id") else None,
                    section_ref=str(meta["section_ref"]) if meta.get("section_ref") else None,
                    page=page,
                    metadata=dict(meta),
                )
            )

        if section_ref and section_ref.strip():
            needle = section_ref.strip().lower()
            hits = [
                h
                for h in hits
                if h.section_ref and needle in h.section_ref.lower()
            ]
        return hits[:top_k]


@lru_cache
def get_chroma_index() -> AdaptiveTaxChromaIndex:
    from adaptive_tax_app.config import get_adaptive_tax_settings

    settings = get_adaptive_tax_settings()
    return AdaptiveTaxChromaIndex(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.CHROMA_COLLECTION,
    )
