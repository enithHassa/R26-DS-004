"""Load Phase 3 Step 13 node embedding bundles (NPZ + meta) for dense retrieval."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np

from backend.shared.config.settings import PROJECT_ROOT


def load_bundle_arrays(bundle_dir: Path) -> tuple[dict[str, Any], list[str], np.ndarray]:
    """Validate and load ``node_embeddings_meta.json`` + NPZ; returns meta, chunk ids, float32 matrix."""
    lib_path = PROJECT_ROOT / "scripts" / "kg_node_embeddings_lib.py"
    if not lib_path.is_file():
        raise FileNotFoundError(f"kg_node_embeddings_lib not found at {lib_path}")

    spec = importlib.util.spec_from_file_location("kg_node_embeddings_lib", lib_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load kg_node_embeddings_lib from {lib_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    meta, ids_arr, emb = mod.load_bundle(bundle_dir)
    chunk_ids = [str(x) for x in np.asarray(ids_arr, dtype=object).ravel()]
    emb_f = np.asarray(emb, dtype=np.float32)
    return meta, chunk_ids, emb_f
