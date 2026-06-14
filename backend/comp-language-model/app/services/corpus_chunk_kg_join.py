"""Phase 3 Step 15 — chunk_id → KG join fields from corpus JSONL (matches ETL section_uid)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from backend.shared.utils.logging import logger


def _load_ird_corpus_lib():
    from backend.shared.config.settings import PROJECT_ROOT

    lib_path = PROJECT_ROOT / "scripts" / "ird_corpus_lib.py"
    if not lib_path.is_file():
        raise FileNotFoundError(f"ird_corpus_lib not found at {lib_path}")
    spec = importlib.util.spec_from_file_location("ird_corpus_lib", lib_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load ird_corpus_lib from {lib_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_kg_etl_lib():
    from backend.shared.config.settings import PROJECT_ROOT

    lib_path = PROJECT_ROOT / "scripts" / "kg_etl_lib.py"
    if not lib_path.is_file():
        raise FileNotFoundError(f"kg_etl_lib not found at {lib_path}")
    spec = importlib.util.spec_from_file_location("kg_etl_lib", lib_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load kg_etl_lib from {lib_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    s = str(v).strip()
    return s if s else None


def load_chunk_kg_join_by_id(path: Path | None) -> dict[str, dict[str, str | None]]:
    """Map chunk_id to KG-oriented join fields (same section_uid rule as ``kg_etl_lib``)."""
    if path is None:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}

    try:
        icl = _load_ird_corpus_lib()
        kg = _load_kg_etl_lib()
    except Exception as exc:
        logger.warning("KG join metadata disabled (could not load scripts helpers): {}", exc)
        return {}

    out: dict[str, dict[str, str | None]] = {}
    with p.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj: dict[str, Any] = json.loads(line)
            cid = obj.get("chunk_id")
            if not cid:
                continue
            cid_s = str(cid)
            try:
                norm = icl.normalize_chunk_for_kg(obj)
            except Exception:
                norm = obj
            source_doc_id = _str_or_none(norm.get("source_doc_id"))
            section_label = _str_or_none(norm.get("section_label"))
            section_uid: str | None = None
            if source_doc_id:
                try:
                    section_uid = kg.make_section_uid(source_doc_id, section_label)
                except Exception:
                    section_uid = None
            out[cid_s] = {
                "source_doc_id": source_doc_id,
                "section_uid": section_uid,
                "section_label": section_label,
                "tier": _str_or_none(norm.get("tier")),
                "instrument_type": _str_or_none(norm.get("instrument_type")),
                "content_kind": _str_or_none(norm.get("content_kind")),
            }
    return out
