"""Phase 3 Step 13 — node embedding bundle metadata, validation, save/load (NPZ + JSON sidecar)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

_SCHEMA_VERSION = "1"

_SAFE_RUN_ID = re.compile(r"^[a-zA-Z0-9._-]+$")


def validate_meta(
    meta: dict[str, Any],
    *,
    path: Path | None = None,
) -> list[str]:
    errs: list[str] = []
    prefix = f"{path}: " if path else ""

    if meta.get("schema_version") != _SCHEMA_VERSION:
        errs.append(f"{prefix}schema_version must be {_SCHEMA_VERSION!r}")

    for key in ("neo4j_label", "id_property", "embedding_model_id", "embedding_run_id"):
        v = meta.get(key)
        if not v or not isinstance(v, str) or not v.strip():
            errs.append(f"{prefix}missing or empty {key}")

    if meta.get("embedding_run_id") and isinstance(meta["embedding_run_id"], str):
        if not _SAFE_RUN_ID.match(meta["embedding_run_id"].strip()):
            errs.append(f"{prefix}embedding_run_id must match {_SAFE_RUN_ID.pattern}")

    vs = meta.get("vector_storage")
    if not isinstance(vs, dict):
        errs.append(f"{prefix}vector_storage must be an object")
    else:
        fmt = vs.get("format")
        if fmt not in ("npz_compressed", "pending"):
            errs.append(f"{prefix}vector_storage.format must be npz_compressed or pending")
        if fmt == "npz_compressed":
            for k in ("filename", "array_key", "ids_key", "dimensions", "dtype"):
                if vs.get(k) is None or (isinstance(vs.get(k), str) and not str(vs.get(k)).strip()):
                    errs.append(f"{prefix}vector_storage missing {k}")
            dim = vs.get("dimensions")
            if dim is not None and (not isinstance(dim, int) or dim < 1):
                errs.append(f"{prefix}vector_storage.dimensions must be a positive int")
        elif fmt == "pending":
            for k in ("filename", "array_key", "ids_key", "dtype"):
                v = vs.get(k)
                if v is None or (isinstance(v, str) and not v.strip()):
                    errs.append(f"{prefix}vector_storage missing {k} (required even when pending)")

    rc = meta.get("row_count")
    if rc is not None and (not isinstance(rc, int) or rc < 0):
        errs.append(f"{prefix}row_count must be a non-negative int or omitted")

    return errs


def validate_npz_against_meta(
    meta: dict[str, Any],
    *,
    embeddings: np.ndarray,
    ids: np.ndarray,
) -> list[str]:
    errs: list[str] = []
    vs = meta.get("vector_storage") or {}
    if vs.get("format") != "npz_compressed":
        return errs
    dim = vs.get("dimensions")
    if isinstance(dim, int) and embeddings.ndim == 2 and embeddings.shape[1] != dim:
        errs.append(f"embeddings second dim {embeddings.shape[1]} != meta dimensions {dim}")
    if embeddings.shape[0] != ids.shape[0]:
        errs.append(f"length mismatch embeddings {embeddings.shape[0]} vs ids {ids.shape[0]}")
    return errs


def write_bundle(
    out_dir: Path,
    *,
    meta: dict[str, Any],
    chunk_ids: list[str],
    embeddings: np.ndarray,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    merrs = validate_meta(meta)
    if merrs:
        raise ValueError("; ".join(merrs))

    vs = meta["vector_storage"]
    npz_name = str(vs["filename"])
    arr_key = str(vs["array_key"])
    ids_key = str(vs["ids_key"])

    emb = np.asarray(embeddings, dtype=np.float32)
    ids_arr = np.asarray(chunk_ids, dtype=object)
    verr = validate_npz_against_meta(meta, embeddings=emb, ids=ids_arr)
    if verr:
        raise ValueError("; ".join(verr))

    np.savez_compressed(out_dir / npz_name, **{arr_key: emb, ids_key: ids_arr})

    meta_out = dict(meta)
    meta_out["row_count"] = int(emb.shape[0])
    (out_dir / "node_embeddings_meta.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_bundle(out_dir: Path) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    meta_path = out_dir / "node_embeddings_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    errs = validate_meta(meta, path=meta_path)
    if errs:
        raise ValueError("; ".join(errs))
    vs = meta["vector_storage"]
    if vs.get("format") == "pending":
        raise ValueError("bundle is pending (no vectors written)")
    npz_path = out_dir / str(vs["filename"])
    data = np.load(npz_path, allow_pickle=True)
    arr_key = str(vs["array_key"])
    ids_key = str(vs["ids_key"])
    emb = np.asarray(data[arr_key], dtype=np.float32)
    ids = np.asarray(data[ids_key], dtype=object)
    verr = validate_npz_against_meta(meta, embeddings=emb, ids=ids)
    if verr:
        raise ValueError("; ".join(verr))
    return meta, ids, emb


def write_pending_meta(out_dir: Path, meta: dict[str, Any]) -> None:
    """Write manifest only (dry-run / planning)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    merrs = validate_meta(meta)
    if merrs:
        raise ValueError("; ".join(merrs))
    (out_dir / "node_embeddings_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
