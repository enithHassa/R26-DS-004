"""End-to-end transaction analysis: normalize -> classify -> rule map."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from backend.shared.schemas.confidence import ConfidenceReport
from backend.shared.schemas.enums import TaxabilityStatus, TxnDirection
from backend.shared.schemas.evidence import EvidenceChain, EvidenceStep

from .bank_feature_extractor import BankNarrationFeatures, extract_bank_features
from .narrative_context import (
    NarrativeContextHit,
    has_confirmed_internal_transfer_evidence,
    is_noisy_statement_description,
    resolve_narrative_context,
)
from .rule_engine_service import get_rule_executor
from .semantic_classifier import SemanticPrediction, get_semantic_classifier
from .taxpayer_profile import DEFAULT_TAXPAYER_ID, load_taxpayer_profile
from .text_normalize import build_text_primary


@dataclass(frozen=True)
class TransactionAnalyzeInput:
    raw_desc: str
    amount_lkr: Decimal
    tx_date: date
    direction: TxnDirection
    facts: dict[str, Any] | None = None
    row_id: str | None = None


@dataclass(frozen=True)
class TransactionAnalysisResult:
    transaction_id: UUID
    semantic_category: str
    economic_event: str | None
    tax_rule_code: str
    taxability_status: TaxabilityStatus
    taxable_amount_lkr: Decimal
    taxable_fraction: Decimal
    treatment: str | None
    rule_reference: str
    explanation: str
    review_reason: str | None
    condition_id_matched: str | None
    decision_mode: str
    confidence_report: ConfidenceReport
    evidence: EvidenceChain
    model_version: str
    taxonomy_version: str
    rulebook_version: str
    text_primary: str
    model_semantic_category: str | None
    class_source: str
    narrative_interpretation: str | None
    narrative_hits: tuple[NarrativeContextHit, ...]
    certainty_tier: str | None = None
    intent_tag: str | None = None
    channel: str | None = None
    evidence_needed: str | None = None
    layer1_note: str | None = None


def _status_enum(value: str) -> TaxabilityStatus:
    try:
        return TaxabilityStatus(value)
    except ValueError:
        return TaxabilityStatus.UNKNOWN


_MIN_CONFIDENCE_OOD = 0.35
_EXTERNAL_MOVEMENT_HINTS = re.compile(
    r"\b(atm|withdrawal|cefts?|salary|wage|wages|interest|bonus|invoice|merchant|"
    r"uber|eats|pos|purchase|payment|refund|dividend|rent|commission)\b",
    re.IGNORECASE,
)
_GENERIC_TRANSFER_HINTS = re.compile(
    r"\b(fund transfer|transfer from|transfer to|trf from|trf to|cefts?)\b",
    re.IGNORECASE,
)


def apply_classification_guards(
    prediction: SemanticPrediction,
    *,
    raw_desc: str,
) -> tuple[SemanticPrediction, list[str]]:
    """Do not auto-accept internal-transfer labels without explicit own-account evidence."""
    notes: list[str] = []
    if is_noisy_statement_description(raw_desc):
        notes.append("Noisy or numeric description; routed to review.")
        return (
            replace(
                prediction,
                label="unknown",
                probabilities={"unknown": prediction.confidence},
            ),
            notes,
        )

    if prediction.label != "inter_account_transfer":
        return prediction, []

    if has_confirmed_internal_transfer_evidence(raw_desc):
        return prediction, []

    if _EXTERNAL_MOVEMENT_HINTS.search(raw_desc) or _GENERIC_TRANSFER_HINTS.search(raw_desc):
        notes.append(
            "Transfer description lacks own-account evidence; not treated as internal movement.",
        )
    else:
        notes.append("Internal-transfer prediction requires explicit own-account evidence.")

    return (
        replace(
            prediction,
            label="unknown",
            probabilities={"unknown": prediction.confidence},
        ),
        notes,
    )


def _infer_economic_event(class_key: str) -> str | None:
    if class_key in {"employment_income", "bonus_performance"}:
        return "recurring_income"
    if class_key in {"freelance_service", "business_profit"}:
        return "business_receipt"
    if class_key == "inter_account_transfer":
        return "internal_movement"
    if class_key == "unknown":
        return "unresolved"
    if class_key in {"personal_spend", "bank_charge", "withholding_tax"}:
        return "non_income"
    return None


def _taxpayer_id_from_facts(facts: dict[str, Any] | None) -> str:
    if not facts:
        return DEFAULT_TAXPAYER_ID
    raw = facts.get("taxpayer_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return DEFAULT_TAXPAYER_ID


def _layer1_features(
    raw_desc: str,
    direction: TxnDirection,
    facts: dict[str, Any] | None,
) -> BankNarrationFeatures:
    profile = load_taxpayer_profile(_taxpayer_id_from_facts(facts))
    return extract_bank_features(raw_desc, direction=direction.value, profile=profile)


def _merge_facts(
    features: BankNarrationFeatures,
    facts: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {**features.as_facts(), **(facts or {})}
    merged.setdefault("taxpayer_id", _taxpayer_id_from_facts(facts))
    return merged


def _certainty_tier(
    *,
    taxability_status: str,
    decision_mode: str,
    class_source: str,
    hint: str | None,
    evidence_needed: str | None,
) -> str:
    if class_source == "manual":
        if taxability_status == "taxable":
            return "guaranteed_taxable"
        if taxability_status == "exempt":
            return "guaranteed_non_taxable"
        return "indeterminate"
    if hint in {"guaranteed_taxable", "guaranteed_non_taxable", "indeterminate"}:
        return hint
    if taxability_status == "unknown" or decision_mode == "human_required" or evidence_needed:
        return "indeterminate"
    if taxability_status == "taxable":
        return "guaranteed_taxable"
    if taxability_status == "exempt":
        return "guaranteed_non_taxable"
    return "indeterminate"


def _choose_applied_class(
    *,
    raw_desc: str,
    model_label: str,
    model_confidence: float,
    guard_notes: list[str],
    narrative_suggested: str | None,
    narrative_score: float | None,
) -> tuple[str, str]:
    if is_noisy_statement_description(raw_desc):
        return "unknown", "narrative"

    score = narrative_score or 0.0
    narrative_label = narrative_suggested or "unknown"

    if model_label == "inter_account_transfer" and not has_confirmed_internal_transfer_evidence(raw_desc):
        if narrative_label != "inter_account_transfer" and score >= 0.12:
            return narrative_label, "narrative"
        return "unknown", "narrative"

    if narrative_label and score >= 0.18 and (
        model_label == "unknown"
        or bool(guard_notes)
        or model_confidence < 0.80
        or (model_label != narrative_label and score >= 0.22)
    ):
        return narrative_label, "narrative"

    if model_label == "unknown" and narrative_label:
        return narrative_label, "narrative"

    return model_label, "model"


def _build_analysis_result(
    *,
    raw_desc: str,
    amount_lkr: Decimal,
    direction: TxnDirection,
    bank_code: str | None,
    document_type: str | None,
    facts: dict[str, Any] | None,
    prediction: SemanticPrediction | None = None,
    class_key_override: str | None = None,
    class_source_hint: str | None = None,
    model_semantic_category: str | None = None,
    transaction_id: UUID | None = None,
) -> TransactionAnalysisResult:
    tx_id = transaction_id or uuid4()
    text_primary = build_text_primary(
        description=raw_desc,
        bank_detected=bank_code,
        direction=direction.value,
        document_type=document_type,
    )
    features = _layer1_features(raw_desc, direction, facts)
    merged_facts = _merge_facts(features, facts)
    narrative = resolve_narrative_context(raw_desc, direction=direction.value)
    suppress_narrative = features.certainty_hint == "indeterminate"
    guard_notes: list[str] = []
    class_source = class_source_hint or "manual"
    applied_class_key = class_key_override
    resolved_model_label = model_semantic_category
    model_version = class_source_hint or "manual-class"
    model_confidence = 1.0

    if class_key_override is None:
        if prediction is None:
            raise ValueError("prediction is required when class_key_override is not set.")
        guarded_prediction, guard_notes = apply_classification_guards(
            prediction,
            raw_desc=raw_desc,
        )
        resolved_model_label = prediction.label
        model_version = prediction.model_version
        model_confidence = prediction.confidence
        applied_class_key, class_source = _choose_applied_class(
            raw_desc=raw_desc,
            model_label=guarded_prediction.label,
            model_confidence=guarded_prediction.confidence,
            guard_notes=guard_notes,
            narrative_suggested=narrative.suggested_class_key,
            narrative_score=narrative.suggestion_score,
        )

    assert applied_class_key is not None
    executor = get_rule_executor()
    decision = executor.evaluate(
        class_key=applied_class_key,
        amount_lkr=amount_lkr,
        facts=merged_facts,
    )
    evidence_steps = [
        EvidenceStep(
            step="normalize",
            detail=f"Built text_primary from description and context tags (len={len(text_primary)}).",
        ),
        EvidenceStep(
            step="layer1_bank_parse",
            detail=features.parse_note,
        ),
        EvidenceStep(
            step="narrative_context",
            detail=features.parse_note if suppress_narrative else narrative.interpretation,
        ),
    ]
    if prediction is not None:
        evidence_steps.append(
            EvidenceStep(
                step="semantic_classifier",
                detail=(
                    f"Predicted class={prediction.label} with confidence={prediction.confidence:.4f} "
                    f"using {prediction.model_version}."
                ),
            ),
        )
    if guard_notes:
        evidence_steps.append(
            EvidenceStep(
                step="classification_guard",
                detail=" ".join(guard_notes),
            ),
        )
    if class_key_override is not None:
        evidence_steps.append(
            EvidenceStep(
                step="class_override",
                detail=(
                    f"Applied class={class_key_override} "
                    f"(source={class_source_hint or 'manual'})."
                ),
            ),
        )
    elif class_source == "narrative":
        evidence_steps.append(
            EvidenceStep(
                step="narrative_fusion",
                detail=(
                    f"Narrative class {narrative.suggested_class_key} "
                    f"selected over model label {resolved_model_label}."
                ),
            ),
        )
    taxability_status = decision.taxability_status
    taxable_amount_lkr = decision.taxable_amount_lkr
    taxable_fraction = decision.taxable_fraction
    if applied_class_key == "unknown":
        if direction == TxnDirection.CR:
            taxability_status = "taxable"
            taxable_fraction = Decimal("1.00")
            taxable_amount_lkr = amount_lkr
        else:
            taxability_status = "unknown"
            taxable_fraction = Decimal("0.00")
            taxable_amount_lkr = Decimal("0.00")
    evidence_steps.append(
        EvidenceStep(
            step="tax_rule_mapping",
            detail=(
                f"Mapped rule={decision.tax_rule_code} status={taxability_status} "
                f"taxable_amount_lkr={taxable_amount_lkr}."
            ),
        ),
    )
    evidence = EvidenceChain(steps=evidence_steps)
    certainty = _certainty_tier(
        taxability_status=taxability_status,
        decision_mode=decision.decision_mode,
        class_source=class_source,
        hint=features.certainty_hint,
        evidence_needed=features.evidence_needed if applied_class_key == "unknown" else None,
    )
    is_ood = certainty == "indeterminate"
    confidence_report = ConfidenceReport(
        top_label=applied_class_key,
        top_probability=model_confidence if prediction is not None else None,
        calibrated_probability=model_confidence if prediction is not None else None,
        entropy=None,
        mc_dropout_variance=None,
        is_ood=is_ood,
    )
    result = TransactionAnalysisResult(
        transaction_id=tx_id,
        semantic_category=decision.class_key,
        economic_event=_infer_economic_event(decision.class_key),
        tax_rule_code=decision.tax_rule_code,
        taxability_status=_status_enum(taxability_status),
        taxable_amount_lkr=taxable_amount_lkr,
        taxable_fraction=taxable_fraction,
        treatment=decision.treatment,
        rule_reference=decision.rule_reference,
        explanation=decision.explanation,
        review_reason=decision.review_reason or features.evidence_needed,
        condition_id_matched=decision.condition_id_matched,
        decision_mode=decision.decision_mode,
        confidence_report=confidence_report,
        evidence=evidence,
        model_version=model_version,
        taxonomy_version=executor.taxonomy_version,
        rulebook_version=executor.rulebook_version,
        text_primary=text_primary,
        model_semantic_category=resolved_model_label,
        class_source=class_source,
        narrative_interpretation=(
            features.parse_note if suppress_narrative else narrative.interpretation
        ),
        narrative_hits=() if suppress_narrative else narrative.hits,
        certainty_tier=certainty,
        intent_tag=features.intent_tag,
        channel=features.channel,
        evidence_needed=features.evidence_needed if certainty == "indeterminate" else None,
        layer1_note=features.parse_note,
    )
    return result


def analyze_transaction_fields(
    *,
    raw_desc: str,
    amount_lkr: Decimal,
    direction: TxnDirection,
    bank_code: str | None = None,
    document_type: str | None = None,
    facts: dict[str, Any] | None = None,
    transaction_id: UUID | None = None,
) -> TransactionAnalysisResult:
    features = _layer1_features(raw_desc, direction, facts)
    if features.deterministic_class:
        return _build_analysis_result(
            raw_desc=raw_desc,
            amount_lkr=amount_lkr,
            direction=direction,
            bank_code=bank_code,
            document_type=document_type,
            facts=facts,
            class_key_override=features.deterministic_class,
            class_source_hint="deterministic",
            transaction_id=transaction_id,
        )
    if features.certainty_hint == "indeterminate":
        return _build_analysis_result(
            raw_desc=raw_desc,
            amount_lkr=amount_lkr,
            direction=direction,
            bank_code=bank_code,
            document_type=document_type,
            facts=facts,
            class_key_override="unknown",
            class_source_hint="deterministic",
            transaction_id=transaction_id,
        )
    classifier = get_semantic_classifier()
    text_primary = build_text_primary(
        description=raw_desc,
        bank_detected=bank_code,
        direction=direction.value,
        document_type=document_type,
    )
    prediction = classifier.predict(text_primary)
    return _build_analysis_result(
        raw_desc=raw_desc,
        amount_lkr=amount_lkr,
        direction=direction,
        bank_code=bank_code,
        document_type=document_type,
        facts=facts,
        prediction=prediction,
        transaction_id=transaction_id,
    )


def analyze_transactions_batch(
    items: list[TransactionAnalyzeInput],
    *,
    bank_code: str | None = None,
    document_type: str | None = None,
) -> list[TransactionAnalysisResult]:
    if not items:
        return []
    features_by_index = [
        _layer1_features(item.raw_desc, item.direction, item.facts) for item in items
    ]
    model_indexes = [
        idx
        for idx, feat in enumerate(features_by_index)
        if feat.deterministic_class is None and feat.certainty_hint != "indeterminate"
    ]
    predictions_by_index: dict[int, SemanticPrediction] = {}
    if model_indexes:
        classifier = get_semantic_classifier()
        texts = [
            build_text_primary(
                description=items[idx].raw_desc,
                bank_detected=bank_code,
                direction=items[idx].direction.value,
                document_type=document_type,
            )
            for idx in model_indexes
        ]
        if hasattr(classifier, "predict_many"):
            model_preds = classifier.predict_many(texts)
        else:
            model_preds = [classifier.predict(text) for text in texts]
        for idx, pred in zip(model_indexes, model_preds, strict=True):
            predictions_by_index[idx] = pred

    results: list[TransactionAnalysisResult] = []
    for idx, item in enumerate(items):
        feat = features_by_index[idx]
        if feat.deterministic_class:
            results.append(
                _build_analysis_result(
                    raw_desc=item.raw_desc,
                    amount_lkr=item.amount_lkr,
                    direction=item.direction,
                    bank_code=bank_code,
                    document_type=document_type,
                    facts=item.facts,
                    class_key_override=feat.deterministic_class,
                    class_source_hint="deterministic",
                ),
            )
            continue
        if feat.certainty_hint == "indeterminate":
            results.append(
                _build_analysis_result(
                    raw_desc=item.raw_desc,
                    amount_lkr=item.amount_lkr,
                    direction=item.direction,
                    bank_code=bank_code,
                    document_type=document_type,
                    facts=item.facts,
                    class_key_override="unknown",
                    class_source_hint="deterministic",
                ),
            )
            continue
        results.append(
            _build_analysis_result(
                raw_desc=item.raw_desc,
                amount_lkr=item.amount_lkr,
                direction=item.direction,
                bank_code=bank_code,
                document_type=document_type,
                facts=item.facts,
                prediction=predictions_by_index[idx],
            ),
        )
    return results


def apply_transactions_class_batch(
    items: list[TransactionAnalyzeInput],
    *,
    class_keys: list[str],
    bank_code: str | None = None,
    document_type: str | None = None,
    model_semantic_categories: list[str | None] | None = None,
) -> list[TransactionAnalysisResult]:
    if not items:
        return []
    model_labels = model_semantic_categories or [None] * len(items)
    return [
        _build_analysis_result(
            raw_desc=item.raw_desc,
            amount_lkr=item.amount_lkr,
            direction=item.direction,
            bank_code=bank_code,
            document_type=document_type,
            facts=item.facts,
            class_key_override=class_key,
            class_source_hint="manual",
            model_semantic_category=model_label,
        )
        for item, class_key, model_label in zip(items, class_keys, model_labels, strict=True)
    ]
