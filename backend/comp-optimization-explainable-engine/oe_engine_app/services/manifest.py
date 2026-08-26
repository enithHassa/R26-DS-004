"""Load the engine corpus manifest (git mirror of ingested files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oe_engine_app.config import get_oe_engine_settings


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or get_oe_engine_settings().OE_ENGINE_MANIFEST_PATH
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def manifest_documents(path: Path | None = None) -> list[dict[str, Any]]:
    payload = load_manifest(path)
    docs = payload.get("documents")
    if not isinstance(docs, list):
        raise ValueError("corpus_manifest.json is missing documents[]")
    return docs


def write_manifest_sha256(source_doc_id: str, sha256: str, path: Path | None = None) -> None:
    """Update the git-mirror hash after a successful ingest."""
    manifest_path = path or get_oe_engine_settings().OE_ENGINE_MANIFEST_PATH
    payload = load_manifest(manifest_path)
    updated = False
    for row in payload.get("documents", []):
        if row.get("source_doc_id") == source_doc_id:
            row["sha256"] = sha256
            updated = True
            break
    if not updated:
        raise KeyError(f"source_doc_id not in manifest: {source_doc_id}")
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
