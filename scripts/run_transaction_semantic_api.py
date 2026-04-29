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
    app_dir = repo_root / "backend/comp-transaction-sementic/app"

    # Future imports from ``backend.shared.*`` inside ``main.py`` need the repo root on sys.path.
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    py_path = os.environ.get("PYTHONPATH", "")
    if root_str not in py_path.split(os.pathsep):
        os.environ["PYTHONPATH"] = (
            root_str + (os.pathsep + py_path if py_path else "")
        )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir=str(app_dir),
        reload_dirs=[str(app_dir)],
    )


if __name__ == "__main__":
    main()
