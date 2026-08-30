"""Catalog-admin job JSON + path roots (Add New Act). Never writes corpus_manifest.json."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from adaptive_tax_app.config import get_adaptive_tax_settings
from backend.shared.config.settings import PROJECT_ROOT

JobStatus = Literal[
    "uploaded",
    "extracting",
    "extracted",
    "failed",
    "discarded",
    "paused_rescan",
]

IN_FLIGHT_STATUSES = frozenset({"uploaded", "extracting", "paused_rescan"})
PENDING_REVIEW_STATUSES = frozenset({"extracted"})

OUT_ROOT = PROJECT_ROOT / "models" / "adaptive-tax" / "relief-interview"
REVIEW_DIR = OUT_ROOT / "review"
DEFAULT_PROPOSED_DIR = OUT_ROOT / "proposed"
DEFAULT_EXTRACTED_DIR = OUT_ROOT / "extracted"
DEFAULT_HASH_INDEX = REVIEW_DIR / "corpus_text_hashes.json"
DEFAULT_HARVEST_SIDECAR_DIR = OUT_ROOT / "harvest" / "watcher_commencements"
DEFAULT_LEDGER_PATH = REVIEW_DIR / "decisions.json"
APPROVED_DIR = OUT_ROOT / "approved"
RATES_DIR = OUT_ROOT / "rates"
HARVEST_CORPUS_JSON = OUT_ROOT / "harvest" / "commencement_records.json"
MANIFEST_PATH = PROJECT_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"


@dataclass(frozen=True)
class CatalogAdminPaths:
    """Filesystem roots. Work-dir override isolates tests from live proposed/."""

    hash_index: Path
    jobs_dir: Path
    uploads_dir: Path
    proposed_dir: Path
    extracted_dir: Path
    harvest_sidecar_dir: Path
    ledger_path: Path
    manifest_path: Path
    approved_dir: Path
    rates_dir: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def catalog_admin_paths() -> CatalogAdminPaths:
    override = get_adaptive_tax_settings().catalog_admin_work_dir
    if override is not None:
        return CatalogAdminPaths(
            hash_index=override / "corpus_text_hashes.json",
            jobs_dir=override / "jobs",
            uploads_dir=override / "uploads",
            proposed_dir=override / "proposed",
            extracted_dir=override / "extracted",
            harvest_sidecar_dir=override / "watcher_commencements",
            ledger_path=override / "decisions.json",
            manifest_path=MANIFEST_PATH,
            approved_dir=override / "approved",
            rates_dir=override / "rates",
        )
    return CatalogAdminPaths(
        hash_index=DEFAULT_HASH_INDEX,
        jobs_dir=REVIEW_DIR / "catalog-admin-jobs",
        uploads_dir=REVIEW_DIR / "catalog-admin-uploads",
        proposed_dir=DEFAULT_PROPOSED_DIR,
        extracted_dir=DEFAULT_EXTRACTED_DIR,
        harvest_sidecar_dir=DEFAULT_HARVEST_SIDECAR_DIR,
        ledger_path=DEFAULT_LEDGER_PATH,
        manifest_path=MANIFEST_PATH,
        approved_dir=APPROVED_DIR,
        rates_dir=RATES_DIR,
    )


def job_path(job_id: str, paths: CatalogAdminPaths | None = None) -> Path:
    root = paths or catalog_admin_paths()
    return root.jobs_dir / f"{job_id}.json"


def load_job(job_id: str, paths: CatalogAdminPaths | None = None) -> dict[str, Any] | None:
    path = job_path(job_id, paths)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_job(payload: dict[str, Any], paths: CatalogAdminPaths | None = None) -> Path:
    root = paths or catalog_admin_paths()
    root.jobs_dir.mkdir(parents=True, exist_ok=True)
    path = job_path(str(payload["id"]), root)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def list_jobs(paths: CatalogAdminPaths | None = None) -> list[dict[str, Any]]:
    root = paths or catalog_admin_paths()
    if not root.jobs_dir.is_dir():
        return []
    jobs: list[dict[str, Any]] = []
    for path in sorted(root.jobs_dir.glob("*.json")):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return jobs


def new_job_id() -> str:
    return str(uuid.uuid4())
