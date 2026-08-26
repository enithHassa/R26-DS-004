"""Phase 1: engine must not import Adaptive Tax or read its catalog paths."""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "oe_engine_app"
FRONTEND_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "features"
    / "optimization-explainable-engine"
)

FORBIDDEN_SNIPPETS = (
    "adaptive_tax_app",
    "opt_explain_app",
    "models/adaptive-tax",
    "models\\adaptive-tax",
    "adaptive-tax/relief-interview",
)


def _scan(root: Path, globs: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return [f"missing tree: {root}"]
    files: list[Path] = []
    for pattern in globs:
        files.extend(root.rglob(pattern))
    for path in files:
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            if snippet in text:
                hits.append(f"{path.relative_to(root)} contains {snippet!r}")
    return hits


def test_oe_engine_app_does_not_depend_on_adaptive_tax() -> None:
    hits = _scan(BACKEND_ROOT, ("*.py",))
    assert hits == [], f"oe_engine_app must not depend on Adaptive Tax: {hits}"


def test_engine_frontend_does_not_import_adaptive_tax() -> None:
    hits: list[str] = []
    if not FRONTEND_ROOT.exists():
        hits.append(f"missing tree: {FRONTEND_ROOT}")
    else:
        for path in list(FRONTEND_ROOT.rglob("*.ts")) + list(FRONTEND_ROOT.rglob("*.tsx")):
            text = path.read_text(encoding="utf-8")
            if "adaptive-tax" in text or "adaptive_tax_app" in text:
                hits.append(str(path.relative_to(FRONTEND_ROOT)))
    assert hits == [], (
        "optimization-explainable-engine frontend must not import Adaptive Tax: "
        f"{hits}"
    )
