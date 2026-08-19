"""Phase 10 — Architecture guard: Rule Engine sole calculator; GPT ≠ calc."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    CalculationTraceStep,
)
from adaptive_tax_app.schemas.evidence import EvidenceBundle, EvidenceChunk
from adaptive_tax_app.schemas.explain import ExplainTaxRequestV1
from adaptive_tax_app.services import architecture_guard as guard
from adaptive_tax_app.services.evidence import (
    STEP_EVIDENCE_UNAVAILABLE,
    build_step_evidence_statuses,
    has_insufficient_evidence,
)
from adaptive_tax_app.services.explain import explain_tax
from adaptive_tax_app.services.gpt_explain import build_fixture_narrative
from adaptive_tax_app.services.rule_engine import calculate as rule_engine_calculate


def test_architecture_summary_documents_current_vs_future() -> None:
    text = guard.ARCHITECTURE_SUMMARY.lower()
    assert "rule engine" in text
    assert "calculate" in text
    assert "rag" in text
    assert "future" in text
    assert "must not calculate" in text or "never" in text


def test_calc_path_files_exist() -> None:
    for path in guard.CALC_PATH_FILES:
        assert path.is_file(), f"missing calc-path file: {path}"


def test_calc_path_has_no_gpt_or_rag_imports() -> None:
    guard.assert_calc_path_has_no_gpt_rag()


def test_calculate_router_imports_rule_engine_calculate() -> None:
    assert guard.calculate_router_calls_rule_engine() is True


def test_enrich_script_not_wired_into_rule_engine() -> None:
    assert guard.enrich_script_is_standalone() is True
    from backend.shared.config.settings import PROJECT_ROOT

    script = PROJECT_ROOT / "scripts" / "adaptive_tax_enrich_corpus_metadata.py"
    assert script.is_file()
    engine_src = (
        PROJECT_ROOT
        / "backend"
        / "comp-adaptive-tax"
        / "adaptive_tax_app"
        / "services"
        / "rule_engine.py"
    ).read_text(encoding="utf-8")
    assert "adaptive_tax_enrich_corpus_metadata" not in engine_src
    assert "OPENAI_API_KEY" not in engine_src


def test_evidence_gates_preserved() -> None:
    flags = guard.evidence_gates_available()
    assert flags["has_insufficient_evidence"] is True
    assert flags["build_step_evidence_statuses"] is True
    assert flags["step_evidence_unavailable_message"] is True
    assert flags["explain_tax"] is True
    assert flags["sanitize_narrative_payload"] is True


def test_global_evidence_gate_blocks_gpt_without_chunks_or_quotes() -> None:
    calc = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="final_tax",
                description="total",
                formula="sum",
                output="0",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["final_tax"],
        rule_source_refs=[],
    )
    empty = EvidenceBundle(chunks=[], source_quotes=[], sections_retrieved=[])
    assert has_insufficient_evidence(empty) is True

    with patch(
        "adaptive_tax_app.services.explain.gather_evidence",
        return_value=empty,
    ), patch(
        "adaptive_tax_app.services.explain.generate_narrative"
    ) as gen:
        out = explain_tax(ExplainTaxRequestV1(calculation=calc), chroma_index=MagicMock())
    assert out.insufficient_evidence is True
    gen.assert_not_called()


def test_step_gate_preserved_when_global_evidence_exists() -> None:
    """Unrelated global chunk must not unlock a different step's narrative."""
    calc = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="deduct_qualifying_payment",
                description="Apply QP",
                formula="min",
                output="1",
                section_uids=["ird-ira-2017-base::sec::section_52"],
            )
        ],
        rules_applied=["deduct_qualifying_payment"],
        rule_source_refs=[],
    )
    bundle = EvidenceBundle(
        chunks=[
            EvidenceChunk(
                chunk_id="only-sec5",
                text="Section 5 employment income",
                section_ref="Section 5",
                source_doc_id="ird-ira-2017-base",
                score=0.9,
                is_operative_provision=True,
            )
        ],
        sections_retrieved=["Section 5"],
        sections_queried=["Section 52"],
    )
    bundle.step_evidence = build_step_evidence_statuses(calc.calculation_trace, bundle)
    narr = build_fixture_narrative(calc, bundle)
    step = narr.payload.steps_explained[0]
    assert step.evidence_unavailable is True
    assert step.narrative == STEP_EVIDENCE_UNAVAILABLE


def test_rule_engine_remains_callable_calculator() -> None:
    """Smoke: Rule Engine still computes without GPT (file KG)."""
    req = CalculateTaxRequestV1(
        assessment_year="2025_26",
        residency_status="resident",
        employment_income="3000000",
        qualifying_payments="0",
        donations="0",
    )
    # Use file ontology path via get_kg_client(mode="file")
    from adaptive_tax_app.services.kg_client import get_kg_client

    result = rule_engine_calculate(req, kg=get_kg_client(mode="file"))
    assert isinstance(result, CalculateTaxResponseV1)
    assert result.final_tax_lkr is not None
    assert result.calculation_trace
    assert "final_tax" in result.rules_applied or any(
        s.step_id == "final_tax" for s in result.calculation_trace
    )


def test_calculate_router_delegates_only_to_rule_engine() -> None:
    """POST /calculate must call services.rule_engine.calculate (not GPT)."""
    from adaptive_tax_app.routers import calculate as calc_router

    body = CalculateTaxRequestV1(
        assessment_year="2025_26",
        residency_status="resident",
        employment_income="1000000",
    )
    fake = CalculateTaxResponseV1(
        final_tax_lkr="0",
        calculation_trace=[
            CalculationTraceStep(
                step_id="final_tax",
                description="t",
                formula="x",
                output="0",
            )
        ],
        rules_applied=["final_tax"],
        rule_source_refs=[],
        calc_id="",
    )
    with patch(
        "adaptive_tax_app.routers.calculate.calculate",
        return_value=fake,
    ) as calc_fn, patch(
        "adaptive_tax_app.routers.calculate.get_kg_client",
        return_value=MagicMock(),
    ), patch(
        "adaptive_tax_app.routers.calculate.save_calculation",
        return_value="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    ):
        out = calc_router.calculate_tax(body)
    calc_fn.assert_called_once()
    assert out.calc_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    assert out.final_tax_lkr == "0"


def test_legal_rule_evidence_review_not_on_calc_path() -> None:
    """Phase 11b — approval stub must stay off Rule Engine / calculate imports."""
    assert (
        "adaptive_tax_app.services.legal_rule_evidence_review"
        in guard.FORBIDDEN_CALC_IMPORT_ROOTS
    )
    assert (
        "adaptive_tax_app.services.legal_rule_evidence_emit"
        in guard.FORBIDDEN_CALC_IMPORT_ROOTS
    )
    from adaptive_tax_app.services.legal_rule_evidence_review import (
        approval_path_documentation,
        incorporate_into_engine_stub,
        submit_candidate,
        approve_candidate,
        clear_review_store,
    )
    from adaptive_tax_app.schemas.legal_rule_evidence import LegalRuleEvidence

    clear_review_store()
    doc = approval_path_documentation()
    assert doc["is_rag_calculation"] is False
    assert doc["current"]["calculate_wiring"] is False
    ev = LegalRuleEvidence(
        section="52",
        source_quote="Qualifying payments shall be deducted in arriving at taxable income.",
        rule_type="deduction",
    )
    rec = submit_candidate(ev)
    approve_candidate(rec.review_id)
    assert incorporate_into_engine_stub(rec.review_id) == "blocked_future_only"
    guard.assert_calc_path_has_no_gpt_rag()
