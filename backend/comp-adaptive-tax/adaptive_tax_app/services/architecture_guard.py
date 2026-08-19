"""Phase 10 — Architecture guard: Rule Engine remains the sole calculator.

CURRENT (locked)
----------------
```
RAG / Chroma  →  legal evidence + explain narrative
Rule Engine   →  tax calculate (sole calculator)
GPT           →  optional corpus metadata enrich (manual) OR explain narrative
                 (never calculates tax; never writes executable params)
```

FUTURE (not wired in this phase)
--------------------------------
```
RAG → LegalRuleEvidence (structured legal evidence, non-executable)
    → human / admin validation
    → approved rule candidate
    → (future) incorporation into Rule Engine / param packs
```

Invariants enforced by :mod:`tests.test_architecture_guard` and helpers below:

1. ``POST /calculate`` calls :func:`adaptive_tax_app.services.rule_engine.calculate` only.
2. Rule Engine must not import OpenAI, Chroma, GPT explain, or corpus enrich.
3. GPT corpus enrich must not be imported by calculate / rule engine / param packs.
4. Explain keeps global evidence gate + per-step evidence gate.
5. Do not remove or bypass the current Rule Engine.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from backend.shared.config.settings import PROJECT_ROOT

# Modules that may calculate tax amounts (sole calculator surface).
CALC_ENTRYPOINTS: frozenset[str] = frozenset(
    {
        "adaptive_tax_app.services.rule_engine",
        "adaptive_tax_app.routers.calculate",
    }
)

# Forbidden imports inside the calculate / rule-engine / param path.
FORBIDDEN_CALC_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "openai",
        "chromadb",
        "adaptive_tax_app.services.gpt_explain",
        "adaptive_tax_app.services.gpt_extract",
        "adaptive_tax_app.services.chroma_index",
        "adaptive_tax_app.services.evidence",
        "adaptive_tax_app.services.explain",
        "adaptive_tax_app.services.legal_rule_evidence_emit",
        "adaptive_tax_app.services.legal_rule_evidence_review",
    }
)

# Scripts / modules that must remain offline from the Rule Engine.
FORBIDDEN_ENGINE_TOUCH_NAMES: frozenset[str] = frozenset(
    {
        "adaptive_tax_enrich_corpus_metadata",
        "gpt_explain",
        "gpt_extract",
        "chroma_index",
        "legal_rule_evidence_emit",
        "legal_rule_evidence_review",
    }
)

_APP_ROOT = PROJECT_ROOT / "backend" / "comp-adaptive-tax" / "adaptive_tax_app"

# Source files that must not import GPT/RAG enrichment for calculation.
CALC_PATH_FILES: tuple[Path, ...] = (
    _APP_ROOT / "services" / "rule_engine.py",
    _APP_ROOT / "services" / "engine_handlers.py",
    _APP_ROOT / "services" / "param_store.py",
    _APP_ROOT / "services" / "provenance.py",
    _APP_ROOT / "routers" / "calculate.py",
)

ARCHITECTURE_SUMMARY = (
    "CURRENT: RAG → evidence + explain | Rule Engine → calculate. "
    "GPT may enrich metadata (manual) or narrate explain; GPT must not calculate tax. "
    "FUTURE: RAG → LegalRuleEvidence → human approval → Rule Engine. "
    "Do not remove or bypass the current Rule Engine."
)


def _import_roots_from_ast(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.name or "").strip()
                if name:
                    roots.add(name.split(".")[0])
                    roots.add(name)
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").strip()
            if mod:
                roots.add(mod.split(".")[0])
                roots.add(mod)
                # Also record full dotted prefixes used below.
                parts = mod.split(".")
                for i in range(1, len(parts) + 1):
                    roots.add(".".join(parts[:i]))
    return roots


def collect_import_roots(path: Path) -> set[str]:
    """Parse a Python file and return imported module roots / dotted names."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    return _import_roots_from_ast(tree)


def forbidden_imports_in_file(
    path: Path,
    *,
    forbidden: Iterable[str] = FORBIDDEN_CALC_IMPORT_ROOTS,
) -> list[str]:
    """Return forbidden import names found in ``path`` (empty if clean)."""
    roots = collect_import_roots(path)
    hits: list[str] = []
    for name in forbidden:
        if name in roots:
            hits.append(name)
            continue
        # Prefix match: ``adaptive_tax_app.services.gpt_explain.foo``
        for root in roots:
            if root == name or root.startswith(name + "."):
                hits.append(name)
                break
    return sorted(set(hits))


def assert_calc_path_has_no_gpt_rag(paths: Iterable[Path] | None = None) -> None:
    """Raise ``AssertionError`` if calculate/engine path imports GPT/RAG helpers."""
    targets = list(paths) if paths is not None else list(CALC_PATH_FILES)
    problems: list[str] = []
    for path in targets:
        if not path.is_file():
            problems.append(f"missing:{path}")
            continue
        hits = forbidden_imports_in_file(path)
        if hits:
            problems.append(f"{path.name}:{','.join(hits)}")
    if problems:
        raise AssertionError(
            "Architecture guard failed — calculate/Rule Engine path must not "
            f"import GPT/RAG modules: {problems}"
        )


def calculate_router_calls_rule_engine(path: Path | None = None) -> bool:
    """True when ``routers/calculate.py`` imports ``rule_engine.calculate``."""
    target = path or (_APP_ROOT / "routers" / "calculate.py")
    src = target.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(target))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.endswith("rule_engine") or mod == "adaptive_tax_app.services.rule_engine":
                for alias in node.names:
                    if alias.name == "calculate":
                        return True
    return False


def enrich_script_is_standalone() -> bool:
    """Corpus GPT enrich lives under scripts/ and is not an engine dependency."""
    script = PROJECT_ROOT / "scripts" / "adaptive_tax_enrich_corpus_metadata.py"
    if not script.is_file():
        return False
    # Rule engine must not mention the enrich script name.
    engine = _APP_ROOT / "services" / "rule_engine.py"
    text = engine.read_text(encoding="utf-8")
    return "adaptive_tax_enrich_corpus_metadata" not in text and "gpt_assisted" not in text


def evidence_gates_available() -> dict[str, bool]:
    """Confirm explain evidence gate helpers exist (global + step)."""
    from adaptive_tax_app.services import evidence as ev
    from adaptive_tax_app.services import explain as ex
    from adaptive_tax_app.services import gpt_explain as ge

    return {
        "has_insufficient_evidence": callable(getattr(ev, "has_insufficient_evidence", None)),
        "build_step_evidence_statuses": callable(
            getattr(ev, "build_step_evidence_statuses", None)
        ),
        "step_evidence_unavailable_message": bool(
            getattr(ev, "STEP_EVIDENCE_UNAVAILABLE", "")
        ),
        "explain_tax": callable(getattr(ex, "explain_tax", None)),
        "sanitize_narrative_payload": callable(
            getattr(ge, "sanitize_narrative_payload", None)
        ),
    }
