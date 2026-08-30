"""Settings for Component 4 (Intelligent Tax Advisory Language Model)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.config.settings import PROJECT_ROOT


class LanguageModelSettings(BaseSettings):
    """Language-model-only configuration (env vars from repo root `.env`)."""

    COMP_LLM_CORPUS_JSONL: Path | None = Field(
        default=None,
        description="Path to corpus_v1.jsonl for retrieval index (TF-IDF or dense per COMP_LLM_RETRIEVAL_BACKEND).",
    )
    COMP_LLM_RETRIEVAL_BACKEND: Literal["tfidf", "dense"] = Field(
        default="tfidf",
        description="Retrieval index for NLU parse: tfidf (default) or dense (sentence-transformers; optional deps).",
    )
    COMP_LLM_DENSE_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence-Transformers model id when COMP_LLM_RETRIEVAL_BACKEND=dense.",
    )
    COMP_LLM_DENSE_DEVICE: str | None = Field(
        default=None,
        description="Optional torch device for dense model (e.g. cuda, cuda:0, cpu); default is library auto.",
    )
    COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR: Path | None = Field(
        default=None,
        description=(
            "Phase 3 Step 14: directory containing node_embeddings_meta.json + .npz from "
            "compute_node_embeddings_bundle.py. When set with retrieval_backend=dense, "
            "skips re-encoding the corpus at startup (corpus JSONL still used for citation text)."
        ),
    )
    COMP_LLM_RETRIEVAL_TOP_K: int = Field(default=8, ge=1, le=50)
    COMP_LLM_QUERY_CITATION_MAX_CHARS: int = Field(
        default=2000,
        ge=200,
        le=50_000,
        description="Max characters per citation excerpt on POST /api/v1/query.",
    )
    COMP_LLM_INTENT_BENCHMARK_JSONL: Path | None = Field(
        default=None,
        description="Phase 2 benchmark JSONL to fit TF-IDF centroid intent baseline (optional).",
    )

    # ------------------------------------------------------------------
    # Phase 4 — Neo4j Knowledge Graph
    # ------------------------------------------------------------------
    NEO4J_URI: str = Field(
        default="neo4j://127.0.0.1:7687",
        description="Bolt URI for Neo4j instance.",
    )
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="")
    NEO4J_DATABASE: str = Field(default="neo4j")
    COMP_LLM_GRAPH_ENABLED: bool = Field(
        default=False,
        description=(
            "Phase 4: enable Neo4j GraphService enrichment on NLU and query responses. "
            "Set True once Neo4j is running and seeded."
        ),
    )

    COMP_LLM_ANSWER_SYNTHESIS_ENABLED: bool = Field(
        default=False,
        description="Enable optional plain-language answers on POST /api/v1/query.",
    )

    # ------------------------------------------------------------------
    # Taxpayer data grounding — chat answers about a specific taxpayer are
    # backed by the shared Azure DB (never guessed). Access is limited to
    # the caller's own financial profile.
    # ------------------------------------------------------------------
    COMP_LLM_TAXPAYER_DATA_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable taxpayer-specific grounding on POST /api/v1/chat. When on, a chat "
            "request carrying profile_id may ask about that taxpayer's own details and "
            "the answer is grounded on shared-DB rows + IRD citations + knowledge graph."
        ),
    )
    COMP_LLM_TAXPAYER_MONTHLY_LOOKBACK: int = Field(
        default=12,
        ge=1,
        le=36,
        description="How many recent monthly taxable-income rollup rows to include in the fact block.",
    )

    # ------------------------------------------------------------------
    # Persistent per-user chat history (FR9)
    # ------------------------------------------------------------------
    COMP_LLM_CHAT_HISTORY_ENABLED: bool = Field(
        default=True,
        description=(
            "Persist chat sessions + messages to the shared DB, scoped per user. "
            "When a chat request carries user_id, history is stored and can be "
            "listed / resumed. Falls back to in-memory sessions when off or when "
            "no user_id is supplied."
        ),
    )
    COMP_LLM_CHAT_HISTORY_MAX_SESSIONS: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Max sessions returned by GET /api/v1/chat/sessions.",
    )
    COMP_LLM_ANSWER_PROVIDER: Literal["gemini", "none"] = Field(default="gemini")
    COMP_LLM_GEMINI_API_KEY: str = Field(default="")
    COMP_LLM_GEMINI_MODEL: str = Field(default="gemini-2.0-flash")
    COMP_LLM_ANSWER_MAX_CITATIONS: int = Field(default=4, ge=1, le=8)
    COMP_LLM_ANSWER_MAX_CHARS_PER_CITATION: int = Field(default=1200, ge=200, le=8000)
    COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS: int = Field(default=1500, ge=128, le=16000)
    COMP_LLM_ANSWER_TIMEOUT_SECONDS: float = Field(default=25.0, ge=5.0, le=120.0)

    COMP_LLM_DOMAIN_GATE_ENABLED: bool = Field(
        default=True,
        description="Reject obvious non-tax questions and weak retrieval matches before answering.",
    )
    COMP_LLM_MIN_RETRIEVAL_SCORE: float = Field(
        default=0.04,
        ge=0.0,
        le=1.0,
        description="Minimum top retrieval score required when no tax hints are present in the question.",
    )
    COMP_LLM_DOMAIN_REQUIRE_TAX_HINTS: bool = Field(
        default=True,
        description="Require Sri Lankan income-tax wording before returning citations or summaries.",
    )
    COMP_LLM_DOMAIN_MIN_QUESTION_OVERLAP: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Minimum token overlap between the question and top excerpt before answering.",
    )

    COMP_LLM_LEX_SPECIALIS_RERANK: bool = Field(
        default=True,
        description="Boost Tier A / act / amendment chunks after vector or TF-IDF retrieval.",
    )
    COMP_LLM_THINK_TWICE_ENABLED: bool = Field(
        default=True,
        description="Run symbolic Think Twice validation on synthesized plain-language answers.",
    )
    COMP_LLM_PROOF_MAP_ENABLED: bool = Field(
        default=True,
        description="Attach structured Proof Map paper trail to query and chat responses.",
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_lm_settings() -> LanguageModelSettings:
    return LanguageModelSettings()
