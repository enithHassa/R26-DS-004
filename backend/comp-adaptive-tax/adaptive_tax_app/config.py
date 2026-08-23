"""Settings owned by Component 5 (Adaptive Tax).

Anything that is *only* meaningful to this component belongs here rather
than in :mod:`backend.shared.config.settings`. Every key is picked up from
the same ``.env`` at the repo root — prefix each with ``COMP_ADAPTIVE_TAX_``
so teammates' component settings do not collide.

``OPENAI_API_KEY`` is unprefixed (shared convention with the OpenAI SDK).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT

_DEFAULT_UPLOAD_ROOT = str(
    Path.home() / ".ai-tax-advisory" / "uploads" / "comp-adaptive-tax"
)


class AdaptiveTaxSettings(BaseSettings):
    """Component-5-only configuration (Phases 1–4: amend, KG/RAG, calc, explain)."""

    # Service port used by `uvicorn` when running this component directly.
    COMP_ADAPTIVE_TAX_PORT: int = 8005

    # Local filesystem root for amendment PDF storage (hash + path on job row).
    COMP_ADAPTIVE_TAX_UPLOAD_ROOT: str = Field(default=_DEFAULT_UPLOAD_ROOT)

    # Amendment job persistence: ``postgres`` (default) or ``file`` (JSON, no DB).
    COMP_ADAPTIVE_TAX_AMENDMENT_STORE: Literal["postgres", "file"] = "postgres"
    COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR: str = "data/dev/amendment-jobs"

    # OpenAI credentials / model for structured amendment extraction.
    OPENAI_API_KEY: str | None = None
    COMP_ADAPTIVE_TAX_OPENAI_MODEL: str = "gpt-4o-mini"

    # ``fixture`` = deterministic Section 52 sample (offline / viva dry-run).
    # ``openai`` = live GPT structured extraction (requires OPENAI_API_KEY).
    COMP_ADAPTIVE_TAX_EXTRACTION_MODE: Literal["openai", "fixture"] = "fixture"

    # Phase 2 — Neo4j (Neo4j Desktop default; Docker Compose also works).
    # Unprefixed so the same vars work for knowledge_graph loader scripts.
    NEO4J_URI: str = "neo4j://127.0.0.1:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # Phase 2 — embedded Chroma (no Docker server required).
    CHROMA_PERSIST_DIR: str = "data/processed/adaptive-tax/chroma"
    CHROMA_COLLECTION: str = "ird_legal_evidence_v1"

    # Phase 2 — adaptive-tax legal corpus (separate from Comp 4 ird corpus).
    COMP_ADAPTIVE_TAX_CORPUS_JSONL: str = "data/processed/adaptive-tax/corpus_v1.jsonl"

    # Phase 3 — calc ontology + param JSON (rate bands, relief caps, calc edges).
    COMP_ADAPTIVE_TAX_ONTOLOGY_DIR: str = "models/adaptive-tax/ontology"

    # Phase 3 — knowledge-graph backend for ``get_kg_client()`` default / tests / explain.
    # ``auto`` = Neo4j when NEO4J_PASSWORD is set, otherwise file ontology.
    # Exception: HTTP POST /calculate always forces neo4j (no file-ontology fallback).
    COMP_ADAPTIVE_TAX_KG_MODE: Literal["auto", "neo4j", "file"] = "auto"

    # Phase 4 — RAG-grounded explanation narrative.
    # ``fixture`` = deterministic template narrative (offline / viva dry-run).
    # ``openai`` = live GPT narrative (requires OPENAI_API_KEY); evidence-only.
    COMP_ADAPTIVE_TAX_EXPLAIN_MODE: Literal["openai", "fixture"] = "fixture"
    COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL: str = "gpt-4o-mini"

    # Retrieval similarity noise floor only — NOT legal confidence.
    # Initial experimental default; choose production value from P@K / R@K eval.
    RAG_MIN_SCORE: float = 0.55

    # Phase 4 — persisted CalculateTaxResponse JSON keyed by calc_id (UUID).
    COMP_ADAPTIVE_TAX_CALC_STORE_DIR: str = "data/processed/adaptive-tax/calculations"

    # Phase 4 — runtime relief-cap override written on Sec 52 approve (viva T1≠T2).
    COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH: str = (
        "data/processed/adaptive-tax/active_relief_caps.json"
    )

    # Phase 5.0 — provenance contract (enforcement lands in 5.0b).
    # ``legacy`` = MVP packs may lack approved rule_source_id (default during 5.0).
    # ``strict`` = refuse executable handlers without Act-backed approved rule_source.
    COMP_ADAPTIVE_TAX_PROVENANCE_MODE: Literal["legacy", "strict"] = "legacy"

    # Phase 5.0 — section harvest targets + coverage checklist.
    COMP_ADAPTIVE_TAX_HARVEST_DIR: str = "models/adaptive-tax/harvest"

    # Phase 6.0 — filing component catalog (UI + normalize + confidence metadata).
    COMP_ADAPTIVE_TAX_FILING_CATALOG_PATH: str = (
        "models/adaptive-tax/fixtures/filing_component_catalog_v1.json"
    )
    # Desktop IRD_Docs sync source (optional; scripts/adaptive_tax_sync_ird_docs.py).
    COMP_ADAPTIVE_TAX_IRD_DOCS_DIR: str = (
        r"c:\Users\H P\Desktop\Research_Project\IRD_Docs"
    )
    COMP_ADAPTIVE_TAX_RAW_PDF_DIR: str = "data/raw/adaptive-tax"

    # Catalog-admin upload/review (Add New Act). Empty → refuse to serve (503).
    COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN: str = ""
    # Optional isolate dir for jobs / hash index / proposed scan (tests). Empty = repo defaults.
    COMP_ADAPTIVE_TAX_CATALOG_ADMIN_WORK_DIR: str = ""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    def _resolve_under_project(self, value: str) -> Path:
        """Resolve a relative path against the repo root; leave absolute paths."""
        p = Path(value)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def upload_root(self) -> Path:
        """Expanded absolute path for amendment PDF storage."""
        return Path(self.COMP_ADAPTIVE_TAX_UPLOAD_ROOT).expanduser().resolve()

    @property
    def amendment_store_mode(self) -> Literal["postgres", "file"]:
        return self.COMP_ADAPTIVE_TAX_AMENDMENT_STORE

    @property
    def amendment_store_dir(self) -> Path:
        """Absolute directory for file-mode amendment job JSON records."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR)

    @property
    def chroma_persist_dir(self) -> Path:
        """Absolute path for embedded Chroma PersistentClient."""
        return self._resolve_under_project(self.CHROMA_PERSIST_DIR)

    @property
    def corpus_jsonl_path(self) -> Path:
        """Absolute path to adaptive-tax corpus_v1.jsonl."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_CORPUS_JSONL)

    @property
    def ontology_dir(self) -> Path:
        """Absolute path to Adaptive Tax ontology / param JSON directory."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_ONTOLOGY_DIR)

    @property
    def calc_store_dir(self) -> Path:
        """Absolute directory for Phase 4 calculation JSON store."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_CALC_STORE_DIR)

    @property
    def param_override_path(self) -> Path:
        """Absolute path to runtime relief-cap override JSON (may not exist yet)."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH)

    @property
    def harvest_dir(self) -> Path:
        """Absolute path to Phase 5 harvest targets / coverage checklist."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_HARVEST_DIR)

    @property
    def filing_catalog_path(self) -> Path:
        """Absolute path to Phase 6 filing component catalog JSON."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_FILING_CATALOG_PATH)

    @property
    def ird_docs_dir(self) -> Path:
        """Desktop (or configured) IRD_Docs folder used to sync official Act PDFs."""
        return Path(self.COMP_ADAPTIVE_TAX_IRD_DOCS_DIR).expanduser().resolve()

    @property
    def raw_pdf_dir(self) -> Path:
        """Project corpus PDF root (``data/raw/adaptive-tax``)."""
        return self._resolve_under_project(self.COMP_ADAPTIVE_TAX_RAW_PDF_DIR)

    @property
    def catalog_admin_work_dir(self) -> Path | None:
        """Override root for catalog-admin jobs/index (tests). None = repo paths."""
        raw = (self.COMP_ADAPTIVE_TAX_CATALOG_ADMIN_WORK_DIR or "").strip()
        if not raw:
            return None
        return self._resolve_under_project(raw)

    def resolve_kg_mode(self) -> Literal["neo4j", "file"]:
        """Effective KG backend for ``get_kg_client()`` after applying ``auto``.

        Does not apply to HTTP POST /calculate, which always forces neo4j.
        """
        mode = self.COMP_ADAPTIVE_TAX_KG_MODE
        if mode == "auto":
            return "neo4j" if (self.NEO4J_PASSWORD or "").strip() else "file"
        return mode


@lru_cache
def get_adaptive_tax_settings() -> AdaptiveTaxSettings:
    return AdaptiveTaxSettings()
