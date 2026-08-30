"""Unresolved claims: missing KG node vs missing DEDUCTED_FROM (stub concept)."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.kg_client import FileOntologyKgClient
from adaptive_tax_app.services.rule_engine import calculate
from backend.shared.config.settings import PROJECT_ROOT

_ONTO = PROJECT_ROOT / "models" / "adaptive-tax" / "ontology"
_EXAMPLES = PROJECT_ROOT / "models" / "adaptive-tax" / "examples"
_STUB = "stub_unresolved_relief"


def _copy_seed_kg(tmp_path: Path) -> Path:
    dest = tmp_path / "ontology"
    dest.mkdir()
    shutil.copy(_ONTO / "concepts_mvp.json", dest / "concepts_mvp.json")
    shutil.copy(_ONTO / "mvp_calc_edges_seed.jsonl", dest / "mvp_calc_edges_seed.jsonl")
    shutil.copy(_ONTO / "relief_caps.json", dest / "relief_caps.json")
    return dest


def _mutate_concepts(path: Path, *, add: dict | None = None, remove: str | None = None) -> None:
    doc = json.loads((path / "concepts_mvp.json").read_text(encoding="utf-8"))
    concepts = list(doc.get("concepts") or [])
    if remove:
        concepts = [c for c in concepts if c.get("concept_id") != remove]
    if add:
        concepts.append(add)
    doc["concepts"] = concepts
    (path / "concepts_mvp.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")


def _filter_edges(path: Path, *, drop_deducted_from: str | None = None) -> None:
    lines = (path / "mvp_calc_edges_seed.jsonl").read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            drop_deducted_from
            and row.get("rel_type") == "DEDUCTED_FROM"
            and row.get("from_id") == drop_deducted_from
        ):
            continue
        kept.append(json.dumps(row, separators=(",", ":")))
    (path / "mvp_calc_edges_seed.jsonl").write_text("\n".join(kept) + "\n", encoding="utf-8")


def _append_edge(path: Path, row: dict) -> None:
    with (path / "mvp_calc_edges_seed.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def test_stub_missing_node_is_concept_missing_in_kg(tmp_path: Path) -> None:
    dest = _copy_seed_kg(tmp_path)
    kg = FileOntologyKgClient(ontology_dir=dest)
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("1800000"),
            other_reliefs={_STUB: Decimal("100000")},
        ),
        kg=kg,
    )
    assert result.final_tax_lkr == "42000"
    assert result.unresolved_claims
    claim = result.unresolved_claims[0]
    assert claim.concept_id == _STUB
    assert claim.component_id == _STUB
    assert claim.claimed_lkr == "100000"
    assert claim.reason == "concept_missing_in_kg"
    assert "deduct_stub_unresolved_relief" not in result.rules_applied
    assert "unresolved_stub_unresolved_relief" in result.rules_applied
    step = next(
        s for s in result.calculation_trace if s.step_id == "unresolved_stub_unresolved_relief"
    )
    assert step.inputs["reason"] == "concept_missing_in_kg"
    assert step.output == "0"


def test_stub_node_without_deducted_from_edge(tmp_path: Path) -> None:
    dest = _copy_seed_kg(tmp_path)
    _mutate_concepts(dest, add={"concept_id": _STUB, "display_name": "Stub", "aliases": []})
    kg = FileOntologyKgClient(ontology_dir=dest)
    result = calculate(
        CalculateTaxRequestV1(
            assessment_year="2024_25",
            resident_status="resident",
            employment_income=Decimal("1800000"),
            other_reliefs={_STUB: Decimal("100000")},
        ),
        kg=kg,
    )
    assert result.final_tax_lkr == "42000"
    claim = next(c for c in result.unresolved_claims if c.concept_id == _STUB)
    assert claim.reason == "no_deducted_from_edge"
    assert claim.claimed_lkr == "100000"
    assert "unresolved_stub_unresolved_relief" in result.rules_applied


def _run_example(path: Path, kg: FileOntologyKgClient):
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = calculate(
        CalculateTaxRequestV1.model_validate(doc["inputs"]),
        kg=kg,
    )
    claim = next(
        c
        for c in result.unresolved_claims
        if c.concept_id == doc["expected_unresolved_concept_id"]
    )
    assert claim.reason == doc["expected_unresolved_reason"]
    assert claim.claimed_lkr == doc["expected_unresolved_claimed_lkr"]
    assert result.final_tax_lkr == doc["expected_final_tax_lkr"]
    assert "deduct_solar_panel_relief" not in result.rules_applied
    step_id = doc["expected_unresolved_step"]
    assert step_id in result.rules_applied
    step = next(s for s in result.calculation_trace if s.step_id == step_id)
    assert step.inputs["reason"] == doc["expected_unresolved_reason"]
    assert step.output == "0"
    return result


def test_ex28_solar_missing_node(tmp_path: Path) -> None:
    dest = _copy_seed_kg(tmp_path)
    _mutate_concepts(dest, remove="solar_panel_relief")
    _filter_edges(dest, drop_deducted_from="solar_panel_relief")
    _run_example(
        _EXAMPLES / "ex28_unresolved_claim_missing_node.json",
        FileOntologyKgClient(ontology_dir=dest),
    )


def test_ex29_solar_missing_deducted_from_edge(tmp_path: Path) -> None:
    dest = _copy_seed_kg(tmp_path)
    _filter_edges(dest, drop_deducted_from="solar_panel_relief")
    _run_example(
        _EXAMPLES / "ex29_unresolved_claim_missing_edge.json",
        FileOntologyKgClient(ontology_dir=dest),
    )


def test_file_kg_required_concepts_include_solar_and_rent() -> None:
    kg = FileOntologyKgClient()
    presence = kg.required_concept_presence()
    assert presence["qualifying_payment"] is True
    assert presence["solar_panel_relief"] is True
    assert presence["solar_panel_relief_cap"] is True
    assert presence["rent_relief"] is True
    assert presence["rent_relief_cap"] is True
