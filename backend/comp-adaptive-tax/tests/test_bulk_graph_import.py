"""Phase 5.10 — bulk calc edge import + File KG full JSONL preference."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from adaptive_tax_app.services.kg_client import FileOntologyKgClient

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "scripts"
_ONTO = _REPO / "models" / "adaptive-tax" / "ontology"


def _load_import_mod():
    path = _SCRIPTS / "adaptive_tax_import_calc_edges.py"
    spec = importlib.util.spec_from_file_location("adaptive_tax_import_calc_edges", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_builds_at_least_300_edges_with_rule_source_ids(tmp_path: Path) -> None:
    mod = _load_import_mod()
    out = tmp_path / "calculation_edges_full.jsonl"
    code = mod.main(
        [
            "--out",
            str(out),
            "--min-edges",
            "300",
            "--with-mentions",
            "--no-ensure-bootstrap",
        ]
    )
    assert code == 0
    rows = [
        json.loads(line)
        for line in out.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 300
    assert all(r.get("rule_source_id") for r in rows)
    # Coverage must remain checklist-driven: bulk MENTIONS are non-executable.
    mentions = [r for r in rows if r.get("rel_type") == "MENTIONS"]
    assert mentions
    assert all(r.get("review_status") == "bulk_mentions" for r in mentions)
    assert "executable" not in rows[0]  # stripped for Neo4j ontology props


def test_file_kg_prefers_calculation_edges_full(tmp_path: Path) -> None:
    # Minimal ontology dir with concepts + full edges only.
    concepts = {
        "concepts": [
            {"concept_id": "employment_income", "display_name": "Employment"},
            {"concept_id": "assessable_income", "display_name": "Assessable"},
        ],
        "sections": [],
    }
    (tmp_path / "concepts_mvp.json").write_text(
        json.dumps(concepts), encoding="utf-8"
    )
    # Seed would be wrong on purpose if used.
    (tmp_path / "mvp_calc_edges_seed.jsonl").write_text(
        json.dumps(
            {
                "rel_type": "CONTRIBUTES_TO",
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": "employment_income",
                "to_label": "Concept",
                "to_key": "concept_id",
                "to_id": "assessable_income",
                "rule_source_id": "seed-only",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "calculation_edges_full.jsonl").write_text(
        json.dumps(
            {
                "rel_type": "CONTRIBUTES_TO",
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": "employment_income",
                "to_label": "Concept",
                "to_key": "concept_id",
                "to_id": "assessable_income",
                "rule_source_id": "full-file",
                "confidence": 0.99,
                "review_status": "act_verified",
            }
        )
        + "\n"
        + json.dumps(
            {
                "rel_type": "GOVERNED_BY",
                "from_label": "Concept",
                "from_key": "concept_id",
                "from_id": "employment_income",
                "to_label": "Section",
                "to_key": "section_uid",
                "to_id": "ird-ira-2017-base::sec::section_5",
                "rule_source_id": "full-file",
                "confidence": 0.99,
                "review_status": "act_verified",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    kg = FileOntologyKgClient(ontology_dir=tmp_path)
    assert any(e.get("rule_source_id") == "full-file" for e in kg._edges)  # noqa: SLF001
    hit = kg.resolve_applicable_concepts(
        income_types=["employment_income"],
        claimed_deductions=[],
    )
    assert "employment_income" in hit.income_concept_ids
    assert any("section_5" in u for u in hit.income_section_uids.get("employment_income", ()))
