"""Unit tests for IR corpus chunking helpers (no PDF I/O)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Ensure sibling imports resolve for ird_corpus_lib -> ird_section_aware
    import sys

    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec.loader.exec_module(mod)
    return mod


_mod = _load("ird_corpus_lib")
_sa = _load("ird_section_aware")


def test_make_chunk_id_format() -> None:
    assert _mod.make_chunk_id_text("ird-ira-2017-base", 12, 3) == "ird-ira-2017-base::p0012::c0003"
    assert _mod.make_chunk_id_table("ird-x", 2, 1) == "ird-x::p0002::t0001"


def test_chunk_page_text_splits_and_overlaps() -> None:
    text = ("word " * 200).strip()
    chunks = _mod.chunk_page_text(text, max_chars=200, overlap=40)
    assert len(chunks) >= 2
    for start, end, piece in chunks:
        assert piece == text[start:end].strip()
        assert len(piece) <= 200


def test_chunk_page_text_empty() -> None:
    assert _mod.chunk_page_text("   \n\t  ", max_chars=200, overlap=40) == []


def test_extract_section_refs() -> None:
    refs = _mod.extract_section_refs("Under Section 45 and Part IV of the Act.")
    assert refs is not None
    assert "Section 45" in refs
    assert "Part IV" in refs


def test_section_5_not_confused_with_52() -> None:
    page = (
        "5. Employment income.\n"
        "(1) Employment income means the gains.\n"
        "52. Qualifying payments.\n"
        "(4) Where a qualifying payment exceeds the limit it may be carried forward.\n"
    )
    segs, _ctx = _sa.split_page_into_provisions(page)
    by_sec = {s.context.section_num: s for s in segs if s.context.section_num}
    assert "5" in by_sec
    assert "52" in by_sec
    meta5 = _sa.detect_section_metadata(by_sec["5"].text, by_sec["5"].context)
    meta52 = _sa.detect_section_metadata(by_sec["52"].text, by_sec["52"].context)
    assert meta5["section_ref"] == "Section 5"
    assert meta52["section_ref"] == "Section 52"
    assert meta5["section_ref"] != meta52["section_ref"]


def test_subsection_alone_not_primary_section() -> None:
    text = "in subsection (5) of that section the words are substituted."
    ctx = _sa.ProvisionContext(section_num="52", paragraph_num="4")
    meta = _sa.detect_section_metadata(text, ctx)
    assert meta["section_ref"] == "Section 52"
    assert meta["paragraph_ref"] == "52(4)"
    refs = meta.get("section_refs") or []
    assert "Section 5" not in refs
    assert meta.get("subsection_only_refs") == ["5"]


def test_continuity_fields_on_oversized_provision() -> None:
    # One long subsection that must split
    body = "(4) " + ("carry forward qualifying payment limit applies. " * 80)
    page = "52. Qualifying payments.\n" + body
    segs, _ = _sa.split_page_into_provisions(page)
    qp = [s for s in segs if s.context.section_num == "52"]
    assert qp
    parts = _sa.split_provision_with_continuity(
        qp[-1].text,
        max_chars=200,
        overlap=40,
        chunk_page_text_fn=_mod.chunk_page_text,
    )
    assert len(parts) >= 2
    parent_ids = set()
    for piece, part_i, part_n in parts:
        meta = _sa.detect_section_metadata(piece, qp[-1].context)
        assert meta["paragraph_ref"] == "52(4)"
        assert meta["parent_provision_id"] == "sec52_4"
        assert part_n == len(parts)
        assert 1 <= part_i <= part_n
        parent_ids.add(meta["parent_provision_id"])
    assert parent_ids == {"sec52_4"}


def test_unsplit_provision_single_part() -> None:
    text = "5. Employment income.\n(1) Employment income means wages."
    segs, _ = _sa.split_page_into_provisions(text)
    assert segs
    parts = _sa.split_provision_with_continuity(
        segs[0].text,
        max_chars=2000,
        overlap=40,
        chunk_page_text_fn=_mod.chunk_page_text,
    )
    assert parts == [(segs[0].text.strip(), 1, 1)]


def test_toc_flag() -> None:
    toc = (
        "ARRANGEMENT OF SECTIONS\n"
        "Section Title Page\n"
        "1. Short title. 1\n"
        "2. Charging provision. 1\n"
        "5. Employment income. 3\n"
        "6. Business income. 5\n"
        "7. Investment income. 6\n"
        "8. Other income. 7\n"
    )
    flags = _sa.classify_chunk_flags(toc)
    assert flags["is_toc"] is True
    assert flags["is_operative_provision"] is False


def test_parent_provision_id_helpers() -> None:
    assert _sa.parent_provision_id_for("52", "52(4)") == "sec52_4"
    assert _sa.parent_provision_id_for("5", None) == "sec5"
    assert _sa.parent_provision_id_for(None, None, schedule_ref="First Schedule") == "first_schedule"


def test_emit_section_aware_writes_continuity(tmp_path: Path) -> None:
    import io

    page = (
        "52. Qualifying payments.\n"
        "(4) " + ("A taxpayer may carry forward the excess qualifying payment. " * 60)
    )
    buf = io.StringIO()
    n_text, n_tab = _mod.emit_pages_to_jsonl(
        pages=[(10, page)],
        source_doc_id="ird-ira-2017-base",
        doc_meta={"tier": "A", "instrument_type": "base_act", "doc_type": "pdf"},
        out_fp=buf,
        max_chars=220,
        overlap=40,
        section_aware=True,
    )
    assert n_text >= 2
    assert n_tab == 0
    rows = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    cont = [r for r in rows if r.get("parent_provision_id") == "sec52_4"]
    assert cont
    assert all(r.get("chunk_schema_version") == "section_aware_v1" for r in cont)
    assert all(r.get("paragraph_ref") == "52(4)" for r in cont)
    assert all(r.get("metadata_source") == "deterministic" for r in cont)
    parts = {r["chunk_part"] for r in cont}
    assert min(parts) == 1
    assert max(parts) == cont[0]["chunk_parts"]


# late import for test_emit
import json  # noqa: E402
