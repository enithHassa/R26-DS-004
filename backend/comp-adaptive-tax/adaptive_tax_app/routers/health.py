"""Liveness and readiness probes for Adaptive Tax component."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from adaptive_tax_app import __version__
from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.services.kg_client import (
    REQUIRED_CALC_CONCEPTS,
    FileOntologyKgClient,
    get_kg_client,
)

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, Any]:
    cfg = get_adaptive_tax_settings()
    payload: dict[str, Any] = {
        "status": "ok",
        "component": "adaptive-tax",
        "version": __version__,
        "extraction_mode": cfg.COMP_ADAPTIVE_TAX_EXTRACTION_MODE,
        "amendment_store": cfg.amendment_store_mode,
        "openai_key_configured": bool(cfg.OPENAI_API_KEY and cfg.OPENAI_API_KEY.strip()),
        "required_concepts": {cid: False for cid in REQUIRED_CALC_CONCEPTS},
        "required_concepts_missing": list(REQUIRED_CALC_CONCEPTS),
        "kg_reachable": False,
        "kg_source": None,
    }
    try:
        if cfg.COMP_ADAPTIVE_TAX_KG_MODE == "file" or not (cfg.NEO4J_PASSWORD or "").strip():
            kg = FileOntologyKgClient()
            payload["kg_source"] = "file"
        else:
            kg = get_kg_client(mode="neo4j")
            payload["kg_reachable"] = True
            payload["kg_source"] = "neo4j"
        presence = kg.required_concept_presence()
        payload["required_concepts"] = presence
        payload["required_concepts_missing"] = [
            cid for cid, ok in presence.items() if not ok
        ]
    except Exception:
        # Liveness stays 200. Calculate returns 503 when Neo4j is down.
        payload["kg_reachable"] = False
        payload["kg_source"] = None
    return payload


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    checks = {"api_bootstrap": True}
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
