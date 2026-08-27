"""Act-admin job JSON + path roots. Never writes corpus_manifest.json."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from backend.shared.config.settings import PROJECT_ROOT
from oe_engine_app.config import get_oe_engine_settings

JobStatus = Literal[
    "uploaded",
    "ingesting",
    "extracting",
    "extracted",
    "failed",
    "discarded",
    "activated",
]

IN_FLIGHT_STATUSES = frozenset({"uploaded", "ingesting", "extracting"})
PENDING_REVIEW_STATUSES = frozenset({"extracted"})

DEFAULT_ROOT = PROJECT_ROOT / "models" / "opt-explain-engine" / "act-admin"


@dataclass(frozen=True)
class ActAdminPaths:
    root: Path
    hash_index: Path
    jobs_dir: Path
    uploads_dir: Path
    drafts_dir: Path
    decisions_path: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def act_admin_paths() -> ActAdminPaths:
    override = get_oe_engine_settings().OE_ENGINE_ACT_ADMIN_WORK_DIR
    root = override if override is not None else DEFAULT_ROOT
    return ActAdminPaths(
        root=root,
        hash_index=root / "corpus_text_hashes.json",
        jobs_dir=root / "jobs",
        uploads_dir=root / "uploads",
        drafts_dir=root / "drafts",
        decisions_path=root / "decisions.json",
    )


def new_job_id() -> str:
    return str(uuid.uuid4())


def job_path(job_id: str, paths: ActAdminPaths | None = None) -> Path:
    root = paths or act_admin_paths()
    return root.jobs_dir / f"{job_id}.json"


def load_job(job_id: str, paths: ActAdminPaths | None = None) -> dict[str, Any] | None:
    path = job_path(job_id, paths)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def save_job(payload: dict[str, Any], paths: ActAdminPaths | None = None) -> Path:
    root = paths or act_admin_paths()
    root.jobs_dir.mkdir(parents=True, exist_ok=True)
    path = job_path(str(payload["id"]), root)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def list_jobs(paths: ActAdminPaths | None = None) -> list[dict[str, Any]]:
    root = paths or act_admin_paths()
    if not root.jobs_dir.is_dir():
        return []
    jobs: list[dict[str, Any]] = []
    for path in sorted(root.jobs_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            jobs.append(payload)
    return jobs


def draft_path(source_doc_id: str, paths: ActAdminPaths | None = None) -> Path:
    root = paths or act_admin_paths()
    return root.drafts_dir / f"{source_doc_id}.json"


def load_draft(source_doc_id: str, paths: ActAdminPaths | None = None) -> dict[str, Any] | None:
    path = draft_path(source_doc_id, paths)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def save_draft(payload: dict[str, Any], paths: ActAdminPaths | None = None) -> Path:
    root = paths or act_admin_paths()
    root.drafts_dir.mkdir(parents=True, exist_ok=True)
    sid = str(payload.get("source_doc_id") or "").strip()
    if not sid:
        raise ValueError("draft requires source_doc_id")
    path = draft_path(sid, root)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_decisions(paths: ActAdminPaths | None = None) -> dict[str, Any]:
    root = paths or act_admin_paths()
    if not root.decisions_path.is_file():
        return {"spec_version": "1.0.0", "rows": {}}
    payload = json.loads(root.decisions_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"spec_version": "1.0.0", "rows": {}}
    payload.setdefault("rows", {})
    return payload


def save_decisions(payload: dict[str, Any], paths: ActAdminPaths | None = None) -> Path:
    root = paths or act_admin_paths()
    root.root.mkdir(parents=True, exist_ok=True)
    root.decisions_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return root.decisions_path
