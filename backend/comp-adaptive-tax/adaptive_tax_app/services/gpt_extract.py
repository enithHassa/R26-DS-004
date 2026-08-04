"""GPT / fixture structured extraction of amendment rules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.extracted_rule import ExtractedRule, ExtractedRulesPayload
from backend.shared.config.settings import PROJECT_ROOT

PROMPT_VERSION = "v1"
FIXTURE_RELATIVE_PATH = Path("models/adaptive-tax/fixtures/section52_extract_sample.json")

_SYSTEM_PROMPT = """You are a Sri Lankan Inland Revenue Act amendment analyst.
Extract structured tax rules from the provided amendment text ONLY.

Rules:
1. Use only the focused amendment text supplied by the user — do not invent sections.
2. Every rule MUST include source_quote: a verbatim contiguous substring copied from the provided text.
3. When the text says a section of the principal enactment is amended, set amends_section to that section id.
4. Prefer concrete numeric limits, rates, and conditions when present.
5. If nothing extractable, return an empty rules list.
"""


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
) -> str:
    candidates = amends_section_candidates or []
    candidate_line = (
        ", ".join(candidates) if candidates else "(none detected — infer from text)"
    )
    return (
        "Extract structured rules from this amendment focus window.\n\n"
        f"Detected amends_section candidates: {candidate_line}\n\n"
        "--- BEGIN AMENDMENT TEXT ---\n"
        f"{focused_text.strip()}\n"
        "--- END AMENDMENT TEXT ---\n"
    )


def extract_rules(
    focused_text: str,
    *,
    amends_section_candidates: list[str] | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> ExtractionResult:
    """Run fixture or OpenAI extraction against focused amendment text."""
    cfg = settings or get_adaptive_tax_settings()
    mode = cfg.COMP_ADAPTIVE_TAX_EXTRACTION_MODE

    if mode == "fixture":
        rules = load_fixture_rules()
        warnings = _quote_warnings(rules, focused_text)
        return ExtractionResult(
            rules=rules,
            model_name="fixture:section52_extract_sample",
            prompt_version=PROMPT_VERSION,
            mode="fixture",
            warnings=warnings,
            metrics={"rule_count": len(rules), "focused_chars": len(focused_text)},
        )

    return _extract_with_openai(
        focused_text,
        amends_section_candidates=amends_section_candidates or [],
        settings=cfg,
    )


def _extract_with_openai(
    focused_text: str,
    *,
    amends_section_candidates: list[str],
    settings: AdaptiveTaxSettings,
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
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=settings.COMP_ADAPTIVE_TAX_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExtractedRulesPayload,
            temperature=0,
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
    }
    if usage is not None:
        metrics["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
        metrics["completion_tokens"] = getattr(usage, "completion_tokens", None)

    return ExtractionResult(
        rules=rules,
        model_name=settings.COMP_ADAPTIVE_TAX_OPENAI_MODEL,
        prompt_version=PROMPT_VERSION,
        mode="openai",
        warnings=warnings,
        metrics=metrics,
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
