"""Parametrized golden examples for the Adaptive Tax rule engine (file KG)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
from backend.shared.config.settings import PROJECT_ROOT

_EXAMPLES_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "examples"


def _example_files() -> list[Path]:
    return sorted(_EXAMPLES_DIR.glob("ex*.json"))


def _expand_cases(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a fixture (single case or ``variants[]``) into runnable cases."""
    if "variants" in doc:
        parent_id = str(doc.get("id") or "")
        cases: list[dict[str, Any]] = []
        for variant in doc["variants"]:
            case = {
                **variant,
                "parent_id": parent_id,
                "scenario": doc.get("scenario"),
                "assert_variants_differ": bool(doc.get("assert_variants_differ")),
            }
            cases.append(case)
        return cases
    return [doc]


def _all_cases() -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in _example_files():
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in _expand_cases(doc):
            case_id = str(case.get("id") or path.stem)
            out.append((case_id, case))
    return out


_CASES = _all_cases()


def test_examples_directory_has_eight_named_files() -> None:
    files = _example_files()
    assert len(files) == 8
    ids = []
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        ids.append(str(doc["id"]))
    assert ids == [f"ex0{i}" for i in range(1, 9)]


@pytest.mark.parametrize("case_id,case", _CASES, ids=[c[0] for c in _CASES])
def test_named_example(case_id: str, case: dict[str, Any]) -> None:
    kg = default_file_kg()
    result = calculate(
        CalculateTaxRequestV1.model_validate(case["inputs"]),
        kg=kg,
    )

    assert result.final_tax_lkr == case["expected_final_tax_lkr"], case_id
    assert result.rules_applied == case["expected_rules_applied"], case_id

    actual_sources = {ref.id for ref in result.rule_source_refs}
    for sid in case.get("expected_rule_source_ids") or []:
        assert sid in actual_sources, f"{case_id}: missing rule_source_id {sid}"

    steps = {s.step_id: s for s in result.calculation_trace}

    for step_id, allowed in (case.get("expected_deduction_allowed") or {}).items():
        assert step_id in steps, f"{case_id}: missing step {step_id}"
        assert steps[step_id].inputs.get("allowed") == allowed

    if "expected_personal_relief" in case:
        assert steps["apply_personal_relief"].inputs["personal_relief"] == case[
            "expected_personal_relief"
        ]
    if "expected_taxable_after_relief" in case:
        assert steps["apply_personal_relief"].output == case["expected_taxable_after_relief"]

    for concept in case.get("expected_assessable_concepts") or []:
        assert concept in steps["sum_assessable"].concept_ids

    order = case.get("expected_rule_order") or []
    if order:
        positions = [result.rules_applied.index(r) for r in order]
        assert positions == sorted(positions), f"{case_id}: rule order {order}"


def test_ex08_pre_and_current_taxes_differ() -> None:
    path = _EXAMPLES_DIR / "ex08_post_amendment_sec52.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc.get("assert_variants_differ") is True
    taxes: list[str] = []
    kg = default_file_kg()
    for variant in doc["variants"]:
        result = calculate(
            CalculateTaxRequestV1.model_validate(variant["inputs"]),
            kg=kg,
        )
        taxes.append(result.final_tax_lkr)
    assert taxes[0] != taxes[1]
    assert taxes == ["48000", "18000"]
