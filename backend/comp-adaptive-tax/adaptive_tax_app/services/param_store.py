"""Load rate-band and relief-cap JSON for the Adaptive Tax rule engine.

Phase 4: when ``param_set=="current"`` and a runtime override file exists
(``COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH``), merge ``relief_updates`` into the
loaded pack so Sec 52 approve / pre-amend reset can change live tax without
editing ontology JSON.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Sequence

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings

AssessmentYear = Literal["2024_25"]
ParamSet = Literal["current", "pre_amend_2025"]

_RATE_BAND_FILES: dict[str, str] = {
    "2024_25": "rate_bands_2024_25.json",
}

_RELIEF_CAP_FILES: dict[str, str] = {
    "current": "relief_caps.json",
    "pre_amend_2025": "relief_caps_pre_amend_2025.json",
}

# Concepts / sections that trigger a Sec 52 cap override on approve.
_SEC52_CONCEPT_IDS = frozenset(
    {
        "qualifying_payment_cap",
        "qualifying_payment",
        "sec52_qualifying_payment_cap",
    }
)
_SEC52_SECTION_TOKENS = frozenset({"52", "section 52", "sec 52", "s.52", "s52"})


@dataclass(frozen=True)
class RateBand:
    rate_band_id: str
    band_index: int
    band_label: str
    lower: int
    upper: int | None
    rate: Decimal
    source_doc_id: str


@dataclass(frozen=True)
class ReliefCap:
    relief_id: str
    concept_id: str
    display_name: str
    section_uid: str | None
    source_doc_id: str
    cap_amount: Decimal | None
    cap_pct_of_assessable: Decimal | None


@dataclass(frozen=True)
class TaxParamPack:
    assessment_year: AssessmentYear
    param_set: ParamSet
    currency: str
    rate_bands: tuple[RateBand, ...]
    reliefs_by_concept: dict[str, ReliefCap]
    reliefs_by_id: dict[str, ReliefCap]

    def relief_for_concept(self, concept_id: str) -> ReliefCap | None:
        return self.reliefs_by_concept.get(concept_id)


@dataclass(frozen=True)
class ParamOverrideWriteResult:
    """Result of writing a runtime relief-cap override file."""

    path: Path
    source: str
    concept_id: str
    cap_amount: Decimal
    rule_source_id: str | None = None
    amendment_job_id: str | None = None


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object: {path}")
    return raw


def _parse_rate_bands(doc: dict[str, Any]) -> tuple[RateBand, ...]:
    bands_raw = doc.get("bands") or []
    out: list[RateBand] = []
    for row in bands_raw:
        if not isinstance(row, dict):
            continue
        upper_raw = row.get("upper")
        out.append(
            RateBand(
                rate_band_id=str(row["rate_band_id"]),
                band_index=int(row["band_index"]),
                band_label=str(row.get("band_label") or row["rate_band_id"]),
                lower=int(row.get("lower") or 0),
                upper=None if upper_raw is None else int(upper_raw),
                rate=Decimal(str(row["rate"])),
                source_doc_id=str(row.get("source_doc_id") or doc.get("source_doc_id") or ""),
            )
        )
    out.sort(key=lambda b: b.band_index)
    return tuple(out)


def _parse_reliefs(doc: dict[str, Any]) -> tuple[dict[str, ReliefCap], dict[str, ReliefCap]]:
    by_concept: dict[str, ReliefCap] = {}
    by_id: dict[str, ReliefCap] = {}
    for row in doc.get("reliefs") or []:
        if not isinstance(row, dict):
            continue
        cap_amount = row.get("cap_amount")
        cap_pct = row.get("cap_pct_of_assessable")
        relief = ReliefCap(
            relief_id=str(row["relief_id"]),
            concept_id=str(row.get("concept_id") or row["relief_id"]),
            display_name=str(row.get("display_name") or row["relief_id"]),
            section_uid=(str(row["section_uid"]) if row.get("section_uid") else None),
            source_doc_id=str(row.get("source_doc_id") or ""),
            cap_amount=None if cap_amount is None else Decimal(str(cap_amount)),
            cap_pct_of_assessable=None if cap_pct is None else Decimal(str(cap_pct)),
        )
        by_id[relief.relief_id] = relief
        by_concept[relief.concept_id] = relief
    return by_concept, by_id


@lru_cache
def _load_tax_param_pack_base(
    assessment_year: AssessmentYear = "2024_25",
    param_set: ParamSet = "current",
    ontology_dir: str | None = None,
) -> TaxParamPack:
    """Load ontology JSON only (no runtime override)."""
    root = Path(ontology_dir) if ontology_dir else get_adaptive_tax_settings().ontology_dir
    band_name = _RATE_BAND_FILES.get(assessment_year)
    relief_name = _RELIEF_CAP_FILES.get(param_set)
    if not band_name:
        raise ValueError(f"unsupported assessment_year: {assessment_year}")
    if not relief_name:
        raise ValueError(f"unsupported param_set: {param_set}")

    bands_path = root / band_name
    reliefs_path = root / relief_name
    if not bands_path.is_file():
        raise FileNotFoundError(f"rate bands not found: {bands_path}")
    if not reliefs_path.is_file():
        raise FileNotFoundError(f"relief caps not found: {reliefs_path}")

    bands_doc = _load_json(bands_path)
    reliefs_doc = _load_json(reliefs_path)
    by_concept, by_id = _parse_reliefs(reliefs_doc)
    return TaxParamPack(
        assessment_year=assessment_year,
        param_set=param_set,
        currency=str(bands_doc.get("currency") or "LKR"),
        rate_bands=_parse_rate_bands(bands_doc),
        reliefs_by_concept=by_concept,
        reliefs_by_id=by_id,
    )


def _normalize_section_token(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = text.replace("section", " ").replace("sec.", " ").replace("sec ", " ")
    text = text.replace("s.", " ").strip()
    return " ".join(text.split())


def is_sec52_cap_rule(
    *,
    concept_id: str | None,
    section: str | None,
    amends_section: str | None,
    maximum: float | None,
) -> bool:
    """True when an approved rule should rewrite the Sec 52 QP aggregate cap."""
    if maximum is None:
        return False
    concept = (concept_id or "").strip().lower()
    if concept in _SEC52_CONCEPT_IDS:
        return True
    for raw in (section, amends_section):
        token = _normalize_section_token(raw)
        if token in _SEC52_SECTION_TOKENS or token.endswith(" 52") or token == "52":
            return True
    return False


def _apply_runtime_override(
    pack: TaxParamPack,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> TaxParamPack:
    cfg = settings or get_adaptive_tax_settings()
    path = cfg.param_override_path
    if not path.is_file():
        return pack

    try:
        doc = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return pack

    updates = doc.get("relief_updates")
    if not isinstance(updates, list) or not updates:
        return pack

    by_concept = dict(pack.reliefs_by_concept)
    by_id = dict(pack.reliefs_by_id)

    for upd in updates:
        if not isinstance(upd, dict):
            continue
        concept_id = str(upd.get("concept_id") or "").strip()
        if not concept_id:
            continue
        existing = by_concept.get(concept_id) or by_id.get(
            str(upd.get("relief_id") or "").strip()
        )
        if existing is None:
            # Create a minimal relief row so the engine can still apply the cap.
            relief_id = str(upd.get("relief_id") or concept_id)
            cap_raw = upd.get("cap_amount")
            if cap_raw is None:
                continue
            relief = ReliefCap(
                relief_id=relief_id,
                concept_id=concept_id,
                display_name=str(upd.get("display_name") or relief_id),
                section_uid=(
                    str(upd["section_uid"]) if upd.get("section_uid") else None
                ),
                source_doc_id=str(upd.get("source_doc_id") or ""),
                cap_amount=Decimal(str(cap_raw)),
                cap_pct_of_assessable=None,
            )
        else:
            kwargs: dict[str, Any] = {}
            if upd.get("cap_amount") is not None:
                kwargs["cap_amount"] = Decimal(str(upd["cap_amount"]))
            if upd.get("source_doc_id"):
                kwargs["source_doc_id"] = str(upd["source_doc_id"])
            if upd.get("section_uid"):
                kwargs["section_uid"] = str(upd["section_uid"])
            if upd.get("display_name"):
                kwargs["display_name"] = str(upd["display_name"])
            if not kwargs:
                continue
            relief = replace(existing, **kwargs)

        by_concept[relief.concept_id] = relief
        by_id[relief.relief_id] = relief

    return TaxParamPack(
        assessment_year=pack.assessment_year,
        param_set=pack.param_set,
        currency=pack.currency,
        rate_bands=pack.rate_bands,
        reliefs_by_concept=by_concept,
        reliefs_by_id=by_id,
    )


def load_tax_param_pack(
    assessment_year: AssessmentYear = "2024_25",
    param_set: ParamSet = "current",
    ontology_dir: str | None = None,
    *,
    settings: AdaptiveTaxSettings | None = None,
    apply_override: bool = True,
) -> TaxParamPack:
    """Load rate bands + relief caps for ``assessment_year`` / ``param_set``.

    When ``param_set=="current"`` and ``apply_override`` is true, merges any
    runtime override file into the relief caps.
    """
    root = str(Path(ontology_dir)) if ontology_dir else None
    pack = _load_tax_param_pack_base(assessment_year, param_set, root)
    if apply_override and param_set == "current":
        return _apply_runtime_override(pack, settings=settings)
    return pack


def clear_param_store_cache() -> None:
    _load_tax_param_pack_base.cache_clear()


def read_param_override(
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> dict[str, Any] | None:
    """Return the override JSON object, or ``None`` if missing."""
    cfg = settings or get_adaptive_tax_settings()
    path = cfg.param_override_path
    if not path.is_file():
        return None
    return _load_json(path)


def reset_param_override(*, settings: AdaptiveTaxSettings | None = None) -> bool:
    """Delete the runtime override file (demo returns to ontology ``current``).

    Returns True if a file was removed.
    """
    cfg = settings or get_adaptive_tax_settings()
    path = cfg.param_override_path
    if not path.is_file():
        return False
    path.unlink()
    return True


def _write_override_doc(
    doc: dict[str, Any],
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> Path:
    cfg = settings or get_adaptive_tax_settings()
    path = cfg.param_override_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def seed_pre_amend_override(
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> ParamOverrideWriteResult:
    """Copy pre-amend Sec 52 cap (1.2M) into the override file for viva T1."""
    cfg = settings or get_adaptive_tax_settings()
    pre = load_tax_param_pack(
        assessment_year="2024_25",
        param_set="pre_amend_2025",
        apply_override=False,
        settings=cfg,
    )
    qp = pre.relief_for_concept("qualifying_payment_cap")
    if qp is None or qp.cap_amount is None:
        raise FileNotFoundError("pre-amend qualifying_payment_cap missing from ontology")

    doc = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "reset_to_pre_amend",
        "amendment_job_id": None,
        "rule_source_id": None,
        "relief_updates": [
            {
                "concept_id": qp.concept_id,
                "relief_id": qp.relief_id,
                "display_name": qp.display_name,
                "section_uid": qp.section_uid,
                "source_doc_id": qp.source_doc_id,
                "cap_amount": int(qp.cap_amount),
            }
        ],
    }
    path = _write_override_doc(doc, settings=cfg)
    return ParamOverrideWriteResult(
        path=path,
        source="reset_to_pre_amend",
        concept_id=qp.concept_id,
        cap_amount=qp.cap_amount,
    )


def write_sec52_override_from_rules(
    rules: Sequence[Any],
    *,
    amendment_job_id: uuid.UUID | str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> ParamOverrideWriteResult | None:
    """Write override from approved Sec 52 / qualifying-payment rules with a maximum.

    Returns ``None`` when no matching rule is present.
    """
    cfg = settings or get_adaptive_tax_settings()
    matched: list[Any] = []
    for rule in rules:
        maximum = getattr(rule, "maximum", None)
        if not is_sec52_cap_rule(
            concept_id=getattr(rule, "concept_id", None),
            section=getattr(rule, "section", None),
            amends_section=getattr(rule, "amends_section", None),
            maximum=maximum,
        ):
            continue
        matched.append(rule)

    if not matched:
        return None

    preferred = next(
        (
            r
            for r in matched
            if (getattr(r, "concept_id", None) or "").strip().lower()
            == "qualifying_payment_cap"
        ),
        matched[0],
    )
    maximum = getattr(preferred, "maximum", None)
    if maximum is None:
        return None

    cap_amount = Decimal(str(maximum))
    rule_id = getattr(preferred, "id", None)
    job_id = amendment_job_id or getattr(preferred, "amendment_job_id", None)

    # Prefer ontology relief_id when present.
    base = load_tax_param_pack(
        assessment_year="2024_25",
        param_set="current",
        apply_override=False,
        settings=cfg,
    )
    existing = base.relief_for_concept("qualifying_payment_cap")
    relief_id = existing.relief_id if existing else "sec52_qualifying_payment_cap"
    section_uid = (
        existing.section_uid if existing else "ird-ira-2017-base::sec::section_52"
    )

    doc = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "sec52_approve",
        "amendment_job_id": str(job_id) if job_id else None,
        "rule_source_id": str(rule_id) if rule_id else None,
        "relief_updates": [
            {
                "concept_id": "qualifying_payment_cap",
                "relief_id": relief_id,
                "display_name": (
                    existing.display_name
                    if existing
                    else "Section 52 qualifying payments aggregate cap"
                ),
                "section_uid": section_uid,
                "source_doc_id": "ird-amend-2025-02",
                "cap_amount": int(cap_amount) if cap_amount == cap_amount.to_integral_value() else float(cap_amount),
            }
        ],
    }
    path = _write_override_doc(doc, settings=cfg)
    return ParamOverrideWriteResult(
        path=path,
        source="sec52_approve",
        concept_id="qualifying_payment_cap",
        cap_amount=cap_amount,
        rule_source_id=str(rule_id) if rule_id else None,
        amendment_job_id=str(job_id) if job_id else None,
    )
