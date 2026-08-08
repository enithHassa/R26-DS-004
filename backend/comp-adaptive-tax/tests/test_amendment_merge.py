"""Unit tests for Phase 2 amendment → Neo4j/Chroma merge."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from adaptive_tax_app.db_loader import RuleSource, RuleSourceStatus, RuleType, RuleVersion
from adaptive_tax_app.merge.amendment_merge import (
    make_section_uid,
    map_filename_to_source_doc_id,
    merge_approved_amendment,
)


def test_map_filename_act_02_2025() -> None:
    assert map_filename_to_source_doc_id("IR_Act_No_02-2025_E.pdf") == "ird-amend-2025-02"


def test_make_section_uid_normalizes() -> None:
    assert (
        make_section_uid("ird-ira-2017-base", "52")
        == "ird-ira-2017-base::sec::section_52"
    )


def test_merge_returns_neo4j_unavailable_without_password() -> None:
    db = MagicMock()
    job = MagicMock()
    job.original_filename = "IR_Act_No_02-2025_E.pdf"
    db.get.return_value = job

    rule = RuleSource(
        amendment_job_id=uuid.uuid4(),
        sort_order=0,
        section="52",
        rule_type=RuleType.LIMIT,
        concept_id="qualifying_payment_cap",
        maximum=1_800_000.0,
        effective_date=date(2025, 4, 1),
        amends_section="52",
        source_quote="Section 52 amended.",
        status=RuleSourceStatus.APPROVED,
    )
    rule.id = uuid.uuid4()

    with patch(
        "adaptive_tax_app.merge.amendment_merge.get_adaptive_tax_settings"
    ) as settings_fn:
        settings = MagicMock()
        settings.NEO4J_PASSWORD = ""
        settings.NEO4J_URI = "bolt://127.0.0.1:7687"
        settings.NEO4J_USER = "neo4j"
        settings_fn.return_value = settings
        result = merge_approved_amendment(
            db=db,
            amendment_job_id=uuid.uuid4(),
            rule_sources=[rule],
            rule_versions=[],
        )

    assert result.merged is False
    assert result.reason == "neo4j_unavailable"


def test_merge_success_with_mocked_driver() -> None:
    db = MagicMock()
    job = MagicMock()
    job.original_filename = "IR_Act_No_02-2025_E.pdf"
    db.get.return_value = job

    rule = RuleSource(
        amendment_job_id=uuid.uuid4(),
        sort_order=0,
        section="52",
        rule_type=RuleType.LIMIT,
        concept_id="qualifying_payment_cap",
        maximum=1_800_000.0,
        effective_date=date(2025, 4, 1),
        amends_section="52",
        source_quote="Section 52 of the principal enactment is hereby amended.",
        status=RuleSourceStatus.APPROVED,
    )
    rule.id = uuid.uuid4()
    version = RuleVersion(
        rule_source_id=rule.id,
        amendment_job_id=rule.amendment_job_id,
        version=1,
        params={"maximum": 1_800_000.0},
    )
    version.id = uuid.uuid4()

    session = MagicMock()
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False

    with (
        patch(
            "adaptive_tax_app.merge.amendment_merge._open_neo4j_driver",
            return_value=driver,
        ),
        patch(
            "adaptive_tax_app.merge.amendment_merge._chroma_reindex_quotes",
            return_value={"ok": True, "quote_chunks_upserted": 1},
        ),
    ):
        result = merge_approved_amendment(
            db=db,
            amendment_job_id=rule.amendment_job_id,
            rule_sources=[rule],
            rule_versions=[version],
        )

    assert result.merged is True
    assert result.reason == "ok"
    assert result.details is not None
    assert result.details["source_doc_id"] == "ird-amend-2025-02"
    assert "ird-ira-2017-base::sec::section_52" in result.details["modifies"]
    assert any(u["relief_id"] == "sec52_qualifying_payment_cap" for u in result.details["relief_updates"])
    assert session.execute_write.call_count >= 3
    driver.close.assert_called_once()


def test_mvp_calc_edges_validate_against_ontology() -> None:
    """Seed JSONL must satisfy edge_ingest / ontology contracts."""
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    scripts = repo / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    import kg_curated_edges_lib as kce
    import kg_ontology_lib as kol

    ontology = kol.load_ontology(repo / "knowledge_graph" / "ontology_v1.json")
    edges_path = repo / "models" / "adaptive-tax" / "ontology" / "mvp_calc_edges_seed.jsonl"
    rows = 0
    with edges_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = __import__("json").loads(line)
            errs = kce.validate_edge_row(row, ontology, line_no=line_no)
            assert not errs, errs
            rows += 1
    assert 30 <= rows <= 60
