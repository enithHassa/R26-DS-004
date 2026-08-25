"""Phase 7: Optimization and Explainable must not import Adaptive Tax."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "opt_explain_app"


def test_opt_explain_app_does_not_import_adaptive_tax_app() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "adaptive_tax_app" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"opt_explain_app must not import adaptive_tax_app: {hits}"
