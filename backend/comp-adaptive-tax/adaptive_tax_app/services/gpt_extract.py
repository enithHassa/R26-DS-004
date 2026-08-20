"""GPT / fixture structured extraction of amendment rules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule, ExtractedRulesPayload
from backend.shared.config.settings import PROJECT_ROOT

PROMPT_VERSION = "v1"
PROMPT_VERSION_SECTION = "v1-section"
FIXTURE_RELATIVE_PATH = Path("models/adaptive-tax/fixtures/section52_extract_sample.json")
SECTION_PROMPT_RELATIVE_PATH = Path("models/adaptive-tax/prompts/extract_section_rules.txt")

_SYSTEM_PROMPT = """You are a Sri Lankan Inland Revenue Act amendment analyst.
Extract structured tax rules from the provided amendment text ONLY.

Rules:
1. Use only the focused amendment text supplied by the user — do not invent sections.
2. Every rule MUST include source_quote: a verbatim contiguous substring copied from the provided text.
3. When the text says a section of the principal enactment is amended, set amends_section to that section id.
4. Prefer concrete numeric limits, rates, and conditions when present.
5. If nothing extractable, return an empty rules list.
"""


def load_section_system_prompt() -> str:
    """Load Phase 5 section-harvest system prompt from models/adaptive-tax/prompts."""
    path = PROJECT_ROOT / SECTION_PROMPT_RELATIVE_PATH
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return _SYSTEM_PROMPT


class ExtractionError(RuntimeError):
    """Raised when structured extraction fails."""


@dataclass
class ExtractionResult:
    rules: list[ExtractedRule]
    model_name: str
    prompt_version: str = PROMPT_VERSION
    mode: str = "fixture"
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    # Viva trail: prompts + focused window + raw completion + structured rules.
    audit: dict[str, Any] = field(default_factory=dict)


def fixture_path() -> Path:
    return PROJECT_ROOT / FIXTURE_RELATIVE_PATH


def load_fixture_rules(path: Path | None = None) -> list[ExtractedRule]:
    target = path or fixture_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    payload = ExtractedRulesPayload.model_validate(raw)
    return payload.rules


def build_user_prompt(
    focused_text: str,
    *,
    amends_section_candidates: list[str] | None = None,
    harvest_mode: str = "amendment",
    section_key: str | None = None,
) -> str:
    candidates = amends_section_candidates or []
    candidate_line = (
        ", ".join(candidates) if candidates else "(none detected — infer from text)"
    )
    if harvest_mode == "section":
        key_line = section_key or "(unspecified)"
        return (
            "Extract structured resident-individual APIT rules from this "
            "official Act SECTION focus window.\n\n"
            f"Target section_key: {key_line}\n"
            f"Detected section candidates: {candidate_line}\n\n"
            "--- BEGIN SECTION TEXT ---\n"
            f"{focused_text.strip()}\n"
            "--- END SECTION TEXT ---\n"
        )
    return (
        "Extract structured rules from this amendment focus window.\n\n"
        f"Detected amends_section candidates: {candidate_line}\n\n"
        "--- BEGIN AMENDMENT TEXT ---\n"
        f"{focused_text.strip()}\n"
        "--- END AMENDMENT TEXT ---\n"
    )


def _structured_rules_dict(rules: list[ExtractedRule]) -> dict[str, Any]:
    return {"rules": [rule.model_dump(mode="json") for rule in rules]}


def _completion_to_dict(completion: Any) -> dict[str, Any] | None:
    """Best-effort JSON-safe dump of an OpenAI completion object."""
    if completion is None:
        return None
    dump = getattr(completion, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            try:
                return dump()
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
    return {"repr": repr(completion)}


def build_audit_payload(
    *,
    mode: str,
    prompt_version: str,
    focused_text: str,
    amends_section_candidates: list[str],
    rules: list[ExtractedRule],
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    raw_completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the viva audit blob stored on amendment_extract_runs."""
    return {
        "mode": mode,
        "prompt_version": prompt_version,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "focused_text": focused_text,
        "amends_section_candidates": list(amends_section_candidates),
        "raw_completion": raw_completion,
        "structured_rules": _structured_rules_dict(rules),
    }


def extract_rules(
    focused_text: str,
    *,
    amends_section_candidates: list[str] | None = None,
    settings: AdaptiveTaxSettings | None = None,
    harvest_mode: str = "amendment",
    section_key: str | None = None,
) -> ExtractionResult:
    """Run fixture or OpenAI extraction against focused amendment/section text."""
    cfg = settings or get_adaptive_tax_settings()
    mode = cfg.COMP_ADAPTIVE_TAX_EXTRACTION_MODE
    candidates = amends_section_candidates or []
    prompt_version = (
        PROMPT_VERSION_SECTION if harvest_mode == "section" else PROMPT_VERSION
    )

    if mode == "fixture":
        rules = load_fixture_rules()
        warnings = _quote_warnings(rules, focused_text)
        user_prompt = build_user_prompt(
            focused_text,
            amends_section_candidates=candidates,
            harvest_mode=harvest_mode,
            section_key=section_key,
        )
        audit = build_audit_payload(
            mode="fixture",
            prompt_version=prompt_version,
            focused_text=focused_text,
            amends_section_candidates=candidates,
            rules=rules,
            system_prompt=None,
            user_prompt=(
                f"[fixture] Loaded {FIXTURE_RELATIVE_PATH.as_posix()}; "
                f"PDF focus window was not sent to a model.\n\n{user_prompt}"
            ),
            raw_completion=None,
        )
        return ExtractionResult(
            rules=rules,
            model_name="fixture:section52_extract_sample",
            prompt_version=prompt_version,
            mode="fixture",
            warnings=warnings,
            metrics={
                "rule_count": len(rules),
                "focused_chars": len(focused_text),
                "harvest_mode": harvest_mode,
            },
            audit=audit,
        )

    return _extract_with_openai(
        focused_text,
        amends_section_candidates=candidates,
        settings=cfg,
        harvest_mode=harvest_mode,
        section_key=section_key,
    )


def _chat_parse_kwargs(model: str) -> dict[str, Any]:
    """Extra kwargs for structured chat parse.

    GPT-5 family rejects ``temperature=0`` (only default ``1`` is allowed).
    Older models keep ``temperature=0`` for deterministic extraction.
    """
    name = (model or "").strip().lower()
    if name.startswith("gpt-5"):
        return {}
    return {"temperature": 0}


def _extract_with_openai(
    focused_text: str,
    *,
    amends_section_candidates: list[str],
    settings: AdaptiveTaxSettings,
    harvest_mode: str = "amendment",
    section_key: str | None = None,
) -> ExtractionResult:
    if not settings.OPENAI_API_KEY:
        raise ExtractionError(
            "COMP_ADAPTIVE_TAX_EXTRACTION_MODE=openai but OPENAI_API_KEY is not set"
        )

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("openai package is not installed") from exc

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_prompt = build_user_prompt(
        focused_text,
        amends_section_candidates=amends_section_candidates,
        harvest_mode=harvest_mode,
        section_key=section_key,
    )
    model = settings.COMP_ADAPTIVE_TAX_OPENAI_MODEL
    system_prompt = (
        load_section_system_prompt() if harvest_mode == "section" else _SYSTEM_PROMPT
    )
    prompt_version = (
        PROMPT_VERSION_SECTION if harvest_mode == "section" else PROMPT_VERSION
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExtractedRulesPayload,
            **_chat_parse_kwargs(model),
        )
    except Exception as exc:  # noqa: BLE001 — surface as ExtractionError
        raise ExtractionError(f"OpenAI structured extraction failed: {exc}") from exc

    message = completion.choices[0].message
    if message.refusal:
        raise ExtractionError(f"OpenAI refused extraction: {message.refusal}")
    payload = message.parsed
    if payload is None:
        raise ExtractionError("OpenAI returned no parsed ExtractedRulesPayload")

    rules = list(payload.rules)
    warnings = _quote_warnings(rules, focused_text)
    usage = getattr(completion, "usage", None)
    metrics: dict = {
        "rule_count": len(rules),
        "focused_chars": len(focused_text),
        "harvest_mode": harvest_mode,
    }
    if usage is not None:
        metrics["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
        metrics["completion_tokens"] = getattr(usage, "completion_tokens", None)

    audit = build_audit_payload(
        mode="openai",
        prompt_version=prompt_version,
        focused_text=focused_text,
        amends_section_candidates=amends_section_candidates,
        rules=rules,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_completion=_completion_to_dict(completion),
    )

    return ExtractionResult(
        rules=rules,
        model_name=model,
        prompt_version=prompt_version,
        mode="openai",
        warnings=warnings,
        metrics=metrics,
        audit=audit,
    )


_WS_RE = re.compile(r"\s+")


def _normalize_ws(value: str) -> str:
    return _WS_RE.sub(" ", value).strip().lower()


def _quote_warnings(rules: list[ExtractedRule], focused_text: str) -> list[str]:
    """Warn when source_quote is not found in focused text (normalized whitespace)."""
    if not focused_text.strip():
        # Fixture mode often runs without PDF text in unit tests.
        return []
    haystack = _normalize_ws(focused_text)
    warnings: list[str] = []
    for idx, rule in enumerate(rules):
        needle = _normalize_ws(rule.source_quote)
        if needle and needle not in haystack:
            warnings.append(
                f"rule[{idx}] source_quote not found as substring of focused text "
                f"(section={rule.section})"
            )
    return warnings
