"""Tests for ExtractedRule schema + fixture / GPT extract helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import (
    AmendmentExtractRun,
    AmendmentExtractRunStatus,
    AmendmentJob,
    AmendmentJobStatus,
    RuleSourceStatus,
)
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule, ExtractedRulesPayload
from adaptive_tax_app.services.extraction import persist_extracted_rules
from adaptive_tax_app.services.gpt_extract import (
    ExtractionError,
    build_user_prompt,
    extract_rules,
    fixture_path,
    load_fixture_rules,
)


def test_extracted_rule_requires_long_source_quote() -> None:
    with pytest.raises(ValidationError):
        ExtractedRule(
            section="52",
            rule_type="limit",
            source_quote="too short",
        )


def test_extracted_rule_accepts_valid_payload() -> None:
    rule = ExtractedRule(
        section="52",
        rule_type="limit",
        amends_section="52",
        maximum=1_800_000,
        source_quote=(
            "Section 52 of the principal enactment is hereby amended by the "
            "substitution for the words one million eight hundred thousand"
        ),
    )
    assert rule.amends_section == "52"
    assert rule.maximum == 1_800_000


def test_fixture_file_exists_and_loads() -> None:
    path = fixture_path()
    assert path.is_file(), f"missing fixture: {path}"
    rules = load_fixture_rules(path)
    assert len(rules) >= 1
    assert any(r.section == "52" for r in rules)
    assert all(len(r.source_quote) >= 20 for r in rules)
    assert any(r.amends_section == "52" for r in rules)


def test_extract_rules_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "fixture")
    get_adaptive_tax_settings.cache_clear()

    result = extract_rules("unused focused text for fixture mode")
    assert result.mode == "fixture"
    assert result.model_name.startswith("fixture:")
    assert len(result.rules) >= 1
    assert result.rules[0].section == "52"
    get_adaptive_tax_settings.cache_clear()


def test_extract_rules_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_adaptive_tax_settings.cache_clear()

    with pytest.raises(ExtractionError, match="OPENAI_API_KEY"):
        extract_rules("Section 52 of the principal enactment is hereby amended")
    get_adaptive_tax_settings.cache_clear()


def test_build_user_prompt_includes_focus_and_candidates() -> None:
    prompt = build_user_prompt(
        "Section 52 of the principal enactment is hereby amended",
        amends_section_candidates=["52", "5"],
    )
    assert "BEGIN AMENDMENT TEXT" in prompt
    assert "52, 5" in prompt
    assert "principal enactment is hereby amended" in prompt


def test_persist_extracted_rules_sets_jsonb_and_pending_rows() -> None:
    rules = load_fixture_rules()
    job = AmendmentJob(
        original_filename="act.pdf",
        content_type="application/pdf",
        size_bytes=10,
        file_hash="abc",
        storage_path="/tmp/act.pdf",
        status=AmendmentJobStatus.EXTRACTING,
    )
    # Give deterministic ids without DB defaults.
    import uuid

    job.id = uuid.uuid4()
    extract_run = AmendmentExtractRun(
        amendment_job_id=job.id,
        model_name="fixture:test",
        status=AmendmentExtractRunStatus.STARTED,
    )
    extract_run.id = uuid.uuid4()

    db = MagicMock()
    created = persist_extracted_rules(
        db=db,
        job=job,
        extract_run=extract_run,
        rules=rules,
    )

    assert isinstance(job.extracted_rules, dict)
    assert len(job.extracted_rules["rules"]) == len(rules)
    assert len(created) == len(rules)
    assert all(row.status == RuleSourceStatus.PENDING for row in created)
    assert created[0].source_quote == rules[0].source_quote
    db.execute.assert_called_once()
    assert db.add.call_count == len(rules)
    db.flush.assert_called_once()


def test_payload_roundtrip_from_fixture_json() -> None:
    raw = fixture_path().read_text(encoding="utf-8")
    payload = ExtractedRulesPayload.model_validate_json(raw)
    assert payload.rules[0].rule_type in {
        "deduction",
        "exemption",
        "rate",
        "definition",
        "limit",
        "condition",
    }
