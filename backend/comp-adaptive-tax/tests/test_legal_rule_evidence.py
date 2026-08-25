"""Phase 11a — LegalRuleEvidence schema (structured legal evidence, not calculation)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from adaptive_tax_app.schemas.extracted_rule import ExtractedRule
from adaptive_tax_app.schemas.legal_rule_evidence import (
    LegalRuleEvidence,
    legal_rule_evidence_from_extracted_rule,
    number_literally_in_quote,
)


_QUOTE = (
    "Where the deduction of any qualifying payment is not possible, "
    "such amount which cannot be deducted shall be carried forward "
    "subject to the aggregate limit of one million eight hundred thousand rupees "
    "(1,800,000)."
)


def test_defaults_candidate_and_non_executable() -> None:
    ev = LegalRuleEvidence(section="52")
    assert ev.status == "candidate"
    assert ev.executable is False
    assert ev.cap_value is None
    assert ev.threshold is None
    assert ev.maximum is None
    public = ev.model_dump_public()
    assert public["is_rag_calculation"] is False
    assert public["role"] == "structured_legal_evidence"
    assert public["executable"] is False


def test_executable_forced_false_even_if_true_passed() -> None:
    ev = LegalRuleEvidence(section="52", executable=True)  # type: ignore[arg-type]
    assert ev.executable is False


def test_structured_fields_require_verbatim_quote() -> None:
    with pytest.raises(ValidationError, match="source_quote"):
        LegalRuleEvidence(
            section="52",
            rule_type="carry_forward",
            formula="carry_forward(excess)",
        )


def test_invented_cap_rejected_when_not_in_quote() -> None:
    with pytest.raises(ValidationError, match="cap_value"):
        LegalRuleEvidence(
            section="52",
            rule_type="CAP",
            cap_value=999_999_999,
            source_quote=_QUOTE,
        )


def test_literal_cap_accepted_when_in_quote() -> None:
    ev = LegalRuleEvidence(
        section="52",
        paragraph_ref="52(4)",
        assessment_year="2025_26",
        rule_type="CAP",
        cap_value=1_800_000,
        maximum=1_800_000,
        source_quote=_QUOTE,
        source_doc_id="ird-amend-2026-11",
        source_chunk_ids=["ird-amend-2026-11::p0007::c0000"],
        parent_provision_id="sec52_4",
        status="candidate",
    )
    assert ev.cap_value == 1_800_000
    assert ev.executable is False
    assert ev.paragraph_ref == "52(4)"


def test_null_numerics_ok_without_inventing() -> None:
    ev = LegalRuleEvidence(
        section="52",
        rule_type="carry_forward",
        condition="excess qualifying payment cannot be deducted",
        formula=None,
        cap_value=None,
        threshold=None,
        maximum=None,
        source_quote=_QUOTE,
        applicability_note="YA 2025/26 pathway — evidence only",
    )
    assert ev.cap_value is None
    assert ev.status == "candidate"


def test_number_literally_in_quote_helper() -> None:
    assert number_literally_in_quote(1_800_000, _QUOTE)
    assert number_literally_in_quote(6.0, "taxed at 6% of the amount")
    assert not number_literally_in_quote(42, _QUOTE)
    assert number_literally_in_quote(None, None)


def test_from_extracted_rule_maps_overlap_and_nullifies_invented_numbers() -> None:
    rule = ExtractedRule(
        section="52",
        paragraph="(4)",
        rule_type="limit",
        condition="resident individual",
        formula=None,
        threshold=9_999_999,  # not in quote → must nullify on map
        maximum=1_800_000,
        effective_date=date(2025, 4, 1),
        source_quote=_QUOTE,
        assessment_years=["2025_26"],
        executable=True,  # ExtractedRule may be true; evidence must stay false
    )
    ev = legal_rule_evidence_from_extracted_rule(
        rule,
        source_doc_id="ird-amend-2026-11",
        source_chunk_ids=["c1"],
        paragraph_ref="52(4)",
    )
    assert ev.executable is False
    assert ev.status == "candidate"
    assert ev.threshold is None  # invented / unsupported by quote
    assert ev.maximum == 1_800_000
    assert ev.rule_type == "limit"
    assert ev.assessment_year == "2025_26"
    assert ev.source_doc_id == "ird-amend-2026-11"
