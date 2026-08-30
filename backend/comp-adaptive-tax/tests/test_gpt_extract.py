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
    _chat_parse_kwargs,
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


def test_extracted_rule_coerces_invalid_effective_dates() -> None:
    quote = (
        "Section 52 of the principal enactment is hereby amended by the "
        "substitution for the words one million eight hundred thousand"
    )
    for bad in ("0000-01-01", "1404-01-01", "not-a-date", ""):
        rule = ExtractedRule(
            section="52",
            rule_type="limit",
            effective_date=bad,  # type: ignore[arg-type]
            source_quote=quote,
        )
        assert rule.effective_date is None

    ok = ExtractedRule(
        section="52",
        rule_type="limit",
        effective_date="2023-04-01",  # type: ignore[arg-type]
        source_quote=quote,
    )
    assert ok.effective_date is not None
    assert ok.effective_date.isoformat() == "2023-04-01"


def test_extracted_rule_caps_short_string_fields() -> None:
    quote = (
        "Section 52 of the principal enactment is hereby amended by the "
        "substitution for the words one million eight hundred thousand"
    )
    long_section = "S" * 100
    long_amends = (
        "First Schedule to the Inland Revenue Act, No.24 of 2017, paragraph 8 "
        "with extra descriptive text that previously overflowed varchar(64)"
    )
    rule = ExtractedRule(
        section=long_section,
        rule_type="rate",
        amends_section=long_amends,
        paragraph="(1) " + ("x" * 80),
        source_quote=quote,
    )
    assert len(rule.section) == 64
    assert rule.amends_section == long_amends  # Text column; keep full label
    assert rule.paragraph is not None and len(rule.paragraph) == 64


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

    focused = "unused focused text for fixture mode"
    result = extract_rules(focused, amends_section_candidates=["52"])
    assert result.mode == "fixture"
    assert result.model_name.startswith("fixture:")
    assert len(result.rules) >= 1
    assert result.rules[0].section == "52"
    assert result.audit["mode"] == "fixture"
    assert result.audit["focused_text"] == focused
    assert result.audit["amends_section_candidates"] == ["52"]
    assert result.audit["raw_completion"] is None
    assert "rules" in result.audit["structured_rules"]
    assert "[fixture]" in (result.audit.get("user_prompt") or "")
    get_adaptive_tax_settings.cache_clear()


def test_extract_rules_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_adaptive_tax_settings.cache_clear()

    with pytest.raises(ExtractionError, match="OPENAI_API_KEY"):
        extract_rules("Section 52 of the principal enactment is hereby amended")
    get_adaptive_tax_settings.cache_clear()


def test_chat_parse_kwargs_omits_temperature_for_gpt5() -> None:
    assert _chat_parse_kwargs("gpt-5-mini") == {}
    assert _chat_parse_kwargs("gpt-5") == {}
    assert _chat_parse_kwargs("gpt-4o-mini") == {"temperature": 0}


def test_extract_rules_openai_populates_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock OpenAI structured parse and assert viva audit fields are filled."""
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_OPENAI_MODEL", "gpt-4o-mini")
    get_adaptive_tax_settings.cache_clear()

    focused = (
        "Section 52 of the principal enactment is hereby amended by the "
        "substitution for the words one million eight hundred thousand"
    )
    rule = ExtractedRule(
        section="52",
        rule_type="limit",
        amends_section="52",
        maximum=1_800_000,
        source_quote=focused,
    )
    payload = ExtractedRulesPayload(rules=[rule])

    message = MagicMock()
    message.refusal = None
    message.parsed = payload
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage = MagicMock(prompt_tokens=11, completion_tokens=22)
    completion.model_dump = MagicMock(
        return_value={"id": "chatcmpl-test", "choices": [{"message": {"content": "{}"}}]}
    )

    client = MagicMock()
    client.beta.chat.completions.parse.return_value = completion
    openai_mod = MagicMock()
    openai_mod.OpenAI.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "openai", openai_mod)

    result = extract_rules(focused, amends_section_candidates=["52"])

    assert result.mode == "openai"
    assert result.model_name == "gpt-4o-mini"
    assert len(result.rules) == 1
    assert result.audit["mode"] == "openai"
    assert result.audit["prompt_version"] == "v1"
    assert result.audit["focused_text"] == focused
    assert result.audit["amends_section_candidates"] == ["52"]
    assert "Inland Revenue" in (result.audit.get("system_prompt") or "")
    assert "BEGIN AMENDMENT TEXT" in (result.audit.get("user_prompt") or "")
    assert result.audit["raw_completion"]["id"] == "chatcmpl-test"
    assert result.audit["structured_rules"]["rules"][0]["section"] == "52"
    assert result.metrics.get("prompt_tokens") == 11
    client.beta.chat.completions.parse.assert_called_once()
    call_kwargs = client.beta.chat.completions.parse.call_args.kwargs
    assert call_kwargs.get("temperature") == 0  # gpt-4o-mini keeps temp=0
    get_adaptive_tax_settings.cache_clear()


def test_extract_rules_openai_gpt5_omits_temperature(monkeypatch: pytest.MonkeyPatch) -> None:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_OPENAI_MODEL", "gpt-5-mini")
    get_adaptive_tax_settings.cache_clear()

    focused = (
        "Section 52 of the principal enactment is hereby amended by the "
        "substitution for the words one million eight hundred thousand"
    )
    rule = ExtractedRule(
        section="52",
        rule_type="limit",
        amends_section="52",
        maximum=1_800_000,
        source_quote=focused,
    )
    payload = ExtractedRulesPayload(rules=[rule])
    message = MagicMock(refusal=None, parsed=payload)
    choice = MagicMock(message=message)
    completion = MagicMock(choices=[choice], usage=None)
    completion.model_dump = MagicMock(return_value={"id": "chatcmpl-g5"})
    client = MagicMock()
    client.beta.chat.completions.parse.return_value = completion
    openai_mod = MagicMock()
    openai_mod.OpenAI.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "openai", openai_mod)

    result = extract_rules(focused, amends_section_candidates=["52"])
    assert result.model_name == "gpt-5-mini"
    assert "temperature" not in client.beta.chat.completions.parse.call_args.kwargs
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
