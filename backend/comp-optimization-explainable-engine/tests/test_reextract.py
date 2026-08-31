"""Re-extract archives previous run and diffs eligibility/evidence."""

from __future__ import annotations

from pathlib import Path

from oe_engine_app.services.archive import archive_previous_and_diff, side_by_side_diff


def test_side_by_side_diff_includes_eligibility_and_evidence() -> None:
    previous = {
        "extraction_run_id": "r1",
        "source_doc_id": "oee-fixture-act-2025",
        "entities": [
            {
                "entry_id": "e1",
                "cap_amount": "600000",
                "eligibility": {"text": "old", "review_status": "pending", "quote": "q1"},
                "required_evidence": ["invoice"],
            }
        ],
    }
    current = {
        "extraction_run_id": "r2",
        "source_doc_id": "oee-fixture-act-2025",
        "entities": [
            {
                "entry_id": "e1",
                "cap_amount": "600000",
                "eligibility": {"text": "new", "review_status": "pending", "quote": "q1"},
                "required_evidence": ["invoice", "photo"],
            }
        ],
    }
    diff = side_by_side_diff(previous, current)
    assert diff["previous_extraction_run_id"] == "r1"
    assert diff["current_extraction_run_id"] == "r2"
    updated = next(row for row in diff["changes"] if row["change"] == "updated")
    assert "eligibility" in updated["fields"]
    assert "required_evidence" in updated["fields"]


def test_archive_not_overwrite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.archive.get_oe_engine_settings",
        lambda: type("S", (), {"OE_ENGINE_EXTRACT_OUT": tmp_path})(),
    )
    first = {
        "extraction_run_id": "r1",
        "source_doc_id": "oee-doc",
        "entities": [{"entry_id": "e1", "cap_amount": "1"}],
    }
    second = {
        "extraction_run_id": "r2",
        "source_doc_id": "oee-doc",
        "entities": [{"entry_id": "e1", "cap_amount": "2"}],
    }
    assert archive_previous_and_diff(first) is None
    diff = archive_previous_and_diff(second)
    assert diff is not None
    archived = tmp_path / "archive" / "oee-doc" / "r1.json"
    assert archived.is_file()
    assert (tmp_path / "oee-doc__current.json").is_file()
    assert (tmp_path / "oee-doc__diff.json").is_file()
