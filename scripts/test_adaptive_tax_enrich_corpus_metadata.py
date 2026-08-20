"""Tests for optional GPT corpus metadata assist (no OpenAI calls)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _load():
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "adaptive_tax_enrich_corpus_metadata",
        _ROOT / "adaptive_tax_enrich_corpus_metadata.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load()


def test_validate_rejects_invented_section() -> None:
    patch, rejects = _mod.validate_enrichment(
        {"primary_section": "Section 999", "referenced_sections": []},
        candidates=["Section 5", "Section 52"],
        chunk_text="Subject to Section 5 of the Act.",
    )
    assert patch is None or patch.get("section_ref") != "Section 999"
    assert any("invented_primary_section" in r for r in rejects)


def test_validate_accepts_candidate_section() -> None:
    patch, rejects = _mod.validate_enrichment(
        {
            "primary_section": "Section 52",
            "referenced_sections": ["Section 5"],
            "uncertain": False,
        },
        candidates=["Section 5", "Section 52"],
        chunk_text="Section 52 qualifying payments refer to Section 5.",
    )
    assert patch is not None
    assert patch["section_ref"] == "Section 52"
    assert patch["metadata_source"] == "gpt_assisted"
    assert patch["needs_review"] is False
    assert "Section 5" in patch.get("section_refs", [])
    assert not any(r.startswith("invented_") for r in rejects)


def test_validate_rejects_invented_date() -> None:
    patch, rejects = _mod.validate_enrichment(
        {
            "primary_section": "Section 5",
            "effective_date": "2099-01-01",
        },
        candidates=["Section 5"],
        chunk_text="Section 5 employment income includes salary.",
    )
    assert patch is not None
    assert "effective_start_date" not in patch
    assert any("invented_effective_date" in r for r in rejects)


def test_validate_accepts_date_year_in_text() -> None:
    patch, rejects = _mod.validate_enrichment(
        {
            "primary_section": "Section 5",
            "effective_date": "2025-04-01",
        },
        candidates=["Section 5"],
        chunk_text="Section 5 as amended in 2025 applies to YA 2025/2026.",
    )
    assert patch is not None
    assert patch.get("effective_start_date") == "2025-04-01"
    assert not any("invented_effective_date" in r for r in rejects)


def test_chunk_needs_review_flag() -> None:
    assert _mod.chunk_needs_review({"needs_review": True, "section_ref": "Section 5"})
    assert not _mod.chunk_needs_review({"is_toc": True, "section_ref": None})
    assert _mod.chunk_needs_review(
        {"section_ref": None, "text": "x" * 200, "metadata_source": "deterministic"}
    )
    assert not _mod.chunk_needs_review(
        {"section_ref": "Section 5", "metadata_source": "gpt_assisted"}
    )


def test_dry_run_enrich_without_api_key(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    row = {
        "chunk_id": "doc::p0001::c0001",
        "source_doc_id": "ird-ira-2017-base",
        "page": 1,
        "text": "Qualifying payments under Section 52 of the Act. " * 10,
        "section_ref": None,
        "needs_review": True,
        "metadata_source": "deterministic",
    }
    corpus.write_text(json_line(row), encoding="utf-8")
    summary = _mod.enrich_corpus(
        corpus_jsonl=corpus,
        out_jsonl=None,
        dry_run=True,
        apply=False,
        limit=10,
        required_only=True,
        model="gpt-4o-mini",
        api_key=None,
    )
    assert summary["needs_review_selected"] >= 1
    assert summary["dry_run"] is True
    assert "wrote" not in summary


def json_line(row: dict) -> str:
    import json

    return json.dumps(row) + "\n"


def test_apply_without_api_key_does_not_write(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    row = {
        "chunk_id": "doc::p0001::c0001",
        "text": "Section 52 " * 30,
        "needs_review": True,
        "section_ref": None,
    }
    corpus.write_text(json_line(row), encoding="utf-8")
    out = tmp_path / "out.jsonl"
    summary = _mod.enrich_corpus(
        corpus_jsonl=corpus,
        out_jsonl=out,
        dry_run=False,
        apply=True,
        limit=5,
        required_only=False,
        model="gpt-4o-mini",
        api_key=None,
    )
    assert summary["skipped_no_api"] >= 1
    assert not out.exists()
