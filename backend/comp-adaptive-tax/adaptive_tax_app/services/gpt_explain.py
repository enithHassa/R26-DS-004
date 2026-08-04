"""Fixture / OpenAI narrators for Phase 4 tax explanations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import CalculateTaxResponseV1
from adaptive_tax_app.schemas.evidence import EvidenceBundle
from adaptive_tax_app.schemas.explain import (
    DISCLAIMER,
    ExplainNarrativePayload,
    ExplainStepV1,
)
from adaptive_tax_app.services.evidence import section_ref_matches, section_uid_to_label
from backend.shared.config.settings import PROJECT_ROOT

PROMPT_VERSION = "v1"
FIXTURE_RELATIVE_PATH = Path("models/adaptive-tax/fixtures/explain_ex04_sample.json")

_SYSTEM_PROMPT = """Do not introduce any section, threshold, or formula not present in the provided evidence. Use only the calculation trace, retrieved chunks, and source quotes supplied below.

You are explaining a Sri Lankan income-tax calculation for a research prototype.
Return structured JSON only.
Rules:
1. sections_cited must be a subset of the sections_retrieved list provided.
2. Every steps_explained entry must reference evidence_chunk_ids and/or rule_source_id from the evidence lists.
3. Do not invent legal sections, numeric caps, or formulas absent from the trace/evidence.
4. Keep the disclaimer exactly: Research prototype — not legal advice.
5. final_tax_lkr must match the calculation result supplied.
"""


class ExplainGenerationError(RuntimeError):
    """Raised when fixture/OpenAI narrative generation fails."""


@dataclass
class NarrativeResult:
    payload: ExplainNarrativePayload
    model_name: str
    mode: str
    prompt_version: str = PROMPT_VERSION
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def fixture_path() -> Path:
    return PROJECT_ROOT / FIXTURE_RELATIVE_PATH


def load_explain_fixture(path: Path | None = None) -> dict[str, Any]:
    """Load the shipped ex04 sample JSON (regression / documentation artifact)."""
    target = path or fixture_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ExplainGenerationError(f"explain fixture must be a JSON object: {target}")
    return raw


def filter_sections_cited(
    cited: list[str],
    sections_retrieved: list[str],
) -> tuple[list[str], list[str]]:
    """Keep only citations in ``sections_retrieved`` (faithfulness).

    Returns ``(filtered, dropped)``.
    """
    allowed = {s.strip() for s in sections_retrieved if s and str(s).strip()}
    kept: list[str] = []
    dropped: list[str] = []
    for label in cited:
        text = (label or "").strip()
        if not text:
            continue
        if text in allowed:
            if text not in kept:
                kept.append(text)
        else:
            dropped.append(text)
    return kept, dropped


def _allowed_chunk_ids(evidence: EvidenceBundle) -> set[str]:
    return {c.chunk_id for c in evidence.chunks if c.chunk_id}


def _allowed_rule_source_ids(evidence: EvidenceBundle) -> set[str]:
    return {q.rule_source_id for q in evidence.source_quotes if q.rule_source_id}


def sanitize_narrative_payload(
    payload: ExplainNarrativePayload,
    *,
    evidence: EvidenceBundle,
    final_tax_lkr: str,
) -> tuple[ExplainNarrativePayload, list[str]]:
    """Post-filter GPT/fixture output for citation faithfulness + evidence ids."""
    warnings: list[str] = []
    cited, dropped = filter_sections_cited(
        payload.sections_cited, evidence.sections_retrieved
    )
    if dropped:
        warnings.append(
            "dropped_hallucinated_sections:" + ",".join(dropped)
        )

    chunk_ok = _allowed_chunk_ids(evidence)
    quote_ok = _allowed_rule_source_ids(evidence)
    steps: list[ExplainStepV1] = []
    for step in payload.steps_explained:
        ids = [cid for cid in step.evidence_chunk_ids if cid in chunk_ok]
        bad_ids = [cid for cid in step.evidence_chunk_ids if cid not in chunk_ok]
        if bad_ids:
            warnings.append(
                f"step:{step.step_id}:dropped_chunk_ids:" + ",".join(bad_ids)
            )
        rule_id = step.rule_source_id
        if rule_id and rule_id not in quote_ok:
            warnings.append(f"step:{step.step_id}:dropped_rule_source_id:{rule_id}")
            rule_id = None
        steps.append(
            ExplainStepV1(
                step_id=step.step_id,
                narrative=step.narrative,
                evidence_chunk_ids=ids,
                rule_source_id=rule_id,
            )
        )

    cleaned = ExplainNarrativePayload(
        summary=payload.summary.strip() or payload.summary,
        sections_cited=cited,
        steps_explained=steps,
        final_tax_lkr=final_tax_lkr,
        disclaimer=DISCLAIMER,
    )
    return cleaned, warnings


def _chunks_for_step(
    step_section_uids: list[str],
    evidence: EvidenceBundle,
) -> list[str]:
    labels = [
        lab
        for uid in step_section_uids
        if (lab := section_uid_to_label(uid)) is not None
    ]
    if not labels:
        # Fall back to any retrieved chunks when the step has no section anchors.
        return [c.chunk_id for c in evidence.chunks[:1]]
    ids: list[str] = []
    for chunk in evidence.chunks:
        for lab in labels:
            if section_ref_matches(chunk.section_ref, lab) or section_ref_matches(
                chunk.text[:400], lab
            ):
                if chunk.chunk_id not in ids:
                    ids.append(chunk.chunk_id)
                break
    return ids


def _quote_for_step(
    step_section_uids: list[str],
    evidence: EvidenceBundle,
) -> str | None:
    labels = [
        lab
        for uid in step_section_uids
        if (lab := section_uid_to_label(uid)) is not None
    ]
    if not labels and evidence.source_quotes:
        return evidence.source_quotes[0].rule_source_id
    for quote in evidence.source_quotes:
        blob = f"{quote.section} {quote.amends_section or ''}".lower()
        for lab in labels:
            # Section 52 / "52"
            if "52" in lab and ("52" in blob or "section 52" in blob):
                return quote.rule_source_id
            if "5" in lab and lab == "Section 5" and (
                blob.strip() in {"5", "section 5"} or blob.startswith("5 ")
            ):
                return quote.rule_source_id
            token = lab.lower().replace("section ", "").strip()
            if token and token in blob:
                return quote.rule_source_id
    return None


def build_fixture_narrative(
    calculation: CalculateTaxResponseV1,
    evidence: EvidenceBundle,
) -> NarrativeResult:
    """Deterministic template narrative (no network)."""
    steps: list[ExplainStepV1] = []
    for step in calculation.calculation_trace:
        chunk_ids = _chunks_for_step(step.section_uids, evidence)
        rule_id = _quote_for_step(step.section_uids, evidence)
        labels = [
            lab
            for uid in step.section_uids
            if (lab := section_uid_to_label(uid)) is not None
        ]
        label_bit = f" (sections: {', '.join(labels)})" if labels else ""
        narrative = (
            f"{step.description}{label_bit}. "
            f"Applied formula `{step.formula}` yielding {step.output}."
        )
        steps.append(
            ExplainStepV1(
                step_id=step.step_id,
                narrative=narrative,
                evidence_chunk_ids=chunk_ids,
                rule_source_id=rule_id,
            )
        )

    retrieved = list(evidence.sections_retrieved)
    cited = list(retrieved)
    summary = (
        f"The rule engine computed a final income-tax liability of "
        f"{calculation.final_tax_lkr} LKR. "
        f"This narrative is grounded only in the calculation trace and "
        f"retrieved legal evidence"
        + (f" for {', '.join(cited)}." if cited else ".")
    )
    payload = ExplainNarrativePayload(
        summary=summary,
        sections_cited=cited,
        steps_explained=steps,
        final_tax_lkr=calculation.final_tax_lkr,
        disclaimer=DISCLAIMER,
    )
    cleaned, warnings = sanitize_narrative_payload(
        payload, evidence=evidence, final_tax_lkr=calculation.final_tax_lkr
    )
    return NarrativeResult(
        payload=cleaned,
        model_name="fixture:template_v1",
        mode="fixture",
        warnings=warnings,
        metrics={"step_count": len(cleaned.steps_explained)},
    )


def build_user_prompt(
    calculation: CalculateTaxResponseV1,
    evidence: EvidenceBundle,
) -> str:
    trace_rows = [
        {
            "step_id": s.step_id,
            "description": s.description,
            "formula": s.formula,
            "inputs": s.inputs,
            "output": s.output,
            "section_uids": s.section_uids,
        }
        for s in calculation.calculation_trace
    ]
    evidence_doc = {
        "sections_retrieved": evidence.sections_retrieved,
        "chunks": [c.model_dump(mode="json") for c in evidence.chunks],
        "source_quotes": [q.model_dump(mode="json") for q in evidence.source_quotes],
    }
    return (
        "Explain this tax calculation using ONLY the evidence below.\n\n"
        f"final_tax_lkr: {calculation.final_tax_lkr}\n\n"
        "--- CALCULATION TRACE ---\n"
        f"{json.dumps(trace_rows, indent=2)}\n"
        "--- END TRACE ---\n\n"
        "--- EVIDENCE ---\n"
        f"{json.dumps(evidence_doc, indent=2)}\n"
        "--- END EVIDENCE ---\n"
    )


def generate_narrative(
    calculation: CalculateTaxResponseV1,
    evidence: EvidenceBundle,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> NarrativeResult:
    """Run fixture template or OpenAI structured explanation."""
    cfg = settings or get_adaptive_tax_settings()
    mode = cfg.COMP_ADAPTIVE_TAX_EXPLAIN_MODE

    if mode == "fixture":
        return build_fixture_narrative(calculation, evidence)

    return _generate_with_openai(calculation, evidence, settings=cfg)


def _generate_with_openai(
    calculation: CalculateTaxResponseV1,
    evidence: EvidenceBundle,
    *,
    settings: AdaptiveTaxSettings,
) -> NarrativeResult:
    if not settings.OPENAI_API_KEY:
        raise ExplainGenerationError(
            "COMP_ADAPTIVE_TAX_EXPLAIN_MODE=openai but OPENAI_API_KEY is not set"
        )

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ExplainGenerationError("openai package is not installed") from exc

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_prompt = build_user_prompt(calculation, evidence)

    try:
        completion = client.beta.chat.completions.parse(
            model=settings.COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExplainNarrativePayload,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        raise ExplainGenerationError(
            f"OpenAI structured explanation failed: {exc}"
        ) from exc

    message = completion.choices[0].message
    if message.refusal:
        raise ExplainGenerationError(f"OpenAI refused explanation: {message.refusal}")
    parsed = message.parsed
    if parsed is None:
        raise ExplainGenerationError("OpenAI returned no parsed ExplainNarrativePayload")

    cleaned, warnings = sanitize_narrative_payload(
        parsed, evidence=evidence, final_tax_lkr=calculation.final_tax_lkr
    )
    usage = getattr(completion, "usage", None)
    metrics: dict[str, Any] = {"step_count": len(cleaned.steps_explained)}
    if usage is not None:
        metrics["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
        metrics["completion_tokens"] = getattr(usage, "completion_tokens", None)

    return NarrativeResult(
        payload=cleaned,
        model_name=settings.COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL,
        mode="openai",
        warnings=warnings,
        metrics=metrics,
    )
