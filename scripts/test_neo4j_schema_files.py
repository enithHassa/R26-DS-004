"""Sanity checks for Phase 3 Step 5 Neo4j schema files (no live DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCHEMA_DIR = _REPO / "knowledge_graph" / "neo4j"
_CONSTRAINTS = _SCHEMA_DIR / "00_constraints.cypher"
_INDEXES = _SCHEMA_DIR / "01_range_indexes.cypher"
_LEX_IDX = _SCHEMA_DIR / "02_lex_indexes.cypher"
_CONS_IDX = _SCHEMA_DIR / "03_consolidated_view_indexes.cypher"

_spec = importlib.util.spec_from_file_location("neo4j_cypher_split", Path(__file__).parent / "neo4j_cypher_split.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_constraints_parse_to_nine_statements() -> None:
    text = _CONSTRAINTS.read_text(encoding="utf-8")
    stmts = _mod.statements_from_cypher(text)
    assert len(stmts) == 9
    assert all("CREATE CONSTRAINT" in s for s in stmts)
    assert all("IS UNIQUE" in s for s in stmts)
    assert any("ConsolidatedViewPassage" in s for s in stmts)


def test_indexes_parse_and_reference_known_labels() -> None:
    text = _INDEXES.read_text(encoding="utf-8")
    stmts = _mod.statements_from_cypher(text)
    assert len(stmts) >= 10
    assert all("CREATE INDEX" in s for s in stmts)
    blob = "\n".join(stmts)
    for label in (
        "LawInstrument",
        "TextChunk",
        "Section",
        "Concept",
        "RateBand",
        "ProcedureMilestone",
        "IrdHubSummary",
    ):
        assert label in blob


def test_consolidated_view_indexes_parse() -> None:
    text = _CONS_IDX.read_text(encoding="utf-8")
    stmts = _mod.statements_from_cypher(text)
    assert len(stmts) == 3
    assert all("ConsolidatedViewPassage" in s for s in stmts)


def test_lex_indexes_parse() -> None:
    text = _LEX_IDX.read_text(encoding="utf-8")
    stmts = _mod.statements_from_cypher(text)
    assert len(stmts) >= 6
    assert all("CREATE INDEX" in s for s in stmts)
    assert "authority_class" in "\n".join(stmts)


def test_split_ignores_comment_only_lines() -> None:
    stmts = _mod.statements_from_cypher(
        "// hi\nCREATE (n:Foo) SET n.x=1;\n// bye\nCREATE (m:Bar) SET m.y=2;"
    )
    assert len(stmts) == 2
