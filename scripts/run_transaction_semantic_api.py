#!/usr/bin/env python3
"""Run the Transaction Semantic FastAPI service with Uvicorn.

From repo root (with backend venv activated):

    python scripts/run_transaction_semantic_api.py

Equivalent CLI:

    uvicorn main:app --app-dir backend/comp-transaction-sementic/app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    component_dir = repo_root / "backend/comp-transaction-sementic"

    # Add both repo root (for backend.shared.*) and component dir (for app.* relative imports).
    for path_str in [str(repo_root), str(component_dir)]:
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
        py_path = os.environ.get("PYTHONPATH", "")
        if path_str not in py_path.split(os.pathsep):
            os.environ["PYTHONPATH"] = path_str + (os.pathsep + py_path if py_path else "")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=[str(component_dir / "app")],
    )


if __name__ == "__main__":
    main()
