"""Load rate-band and relief-cap JSON for the Adaptive Tax rule engine.

Phase 5.0: dual assessment years ``2024_25`` / ``2025_26`` with year-native
relief packs. ``param_set=="current"`` resolves:

* YA 2024/25 → Sec 52 cap 1.2M (``relief_caps_2024_25.json``)
* YA 2025/26 → Sec 52 cap 1.8M (``relief_caps_2025_26.json``, Act 02/2025)

``param_set=="pre_amend_2025"`` always loads the 1.2M snapshot (ex08 / viva T1).

Phase 4: when ``param_set=="current"`` and a runtime override file exists
(``COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH``), merge ``relief_updates`` and
``rate_band_updates`` into the loaded pack so Sec 52 / First Schedule approve
can change live tax without editing ontology JSON.
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

AssessmentYear = Literal["2024_25", "2025_26"]
ParamSet = Literal["current", "pre_amend_2025"]

_RATE_BAND_FILES: dict[str, str] = {
    "2024_25": "rate_bands_2024_25.json",
    "2025_26": "rate_bands_2025_26.json",
}

# Year-native "current" packs (Phase 5.0).
_RELIEF_CAP_BY_YEAR: dict[str, str] = {
    "2024_25": "relief_caps_2024_25.json",
    "2025_26": "relief_caps_2025_26.json",
}

_RELIEF_CAP_PRE_AMEND = "relief_caps_pre_amend_2025.json"

# Deprecated: fictional aggregate Sec 52 cap removed (Path B). Kept for import compat.
_SEC52_CONCEPT_IDS = frozenset({"qualifying_payment_cap", "sec52_qualifying_payment_cap"})
_SEC52_SECTION_TOKENS = frozenset({"52", "section 52", "sec 52", "s.52", "s52"})

_RATE_CONCEPT_IDS = frozenset(
    {
        "first_schedule_rates",
        "first_schedule",
        "rate_band",
        "progressive_rates",
    }
)
_RATE_SECTION_TOKENS = frozenset(
    {
        "first schedule",
        "first_schedule",
        "schedule 1",
        "schedule i",
    }
)
_PERSONAL_RELIEF_CONCEPT_IDS = frozenset(
    {
        "personal_relief",
        "personal_reliefs",
    }
)
_PERSONAL_RELIEF_SECTION_TOKENS = frozenset(
    {
        "personal relief",
        "first schedule",
        "first_schedule",
    }
)
_DONATION_CAP_CONCEPT_IDS = frozenset(
    {
        "donation_cap",
        "donation",
        "charitable_donation_cap",
    }
)

@dataclass(frozen=True)
class RateBand:
    rate_band_id: str
    band_index: int
    band_label: str
    lower: int
    upper: int | None
    rate: Decimal
    source_doc_id: str
    rule_source_id: str | None = None


@dataclass(frozen=True)
class ReliefCap:
    relief_id: str
    concept_id: str
    display_name: str
    section_uid: str | None
    source_doc_id: str
    cap_amount: Decimal | None
    cap_pct_of_assessable: Decimal | None
    rule_source_id: str | None = None


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


@dataclass(frozen=True)
class RateBandOverrideWriteResult:
    """Result of writing First Schedule ``rate_band_updates`` into the override file."""

    path: Path
    source: str
    concept_id: str
    assessment_years: tuple[str, ...]
    band_update_count: int
    rule_source_id: str | None = None
    amendment_job_id: str | None = None


def relief_cap_filename(
    assessment_year: AssessmentYear,
    param_set: ParamSet,
) -> str:
    """Resolve ontology relief-cap filename for year + param_set."""
    if param_set == "pre_amend_2025":
        return _RELIEF_CAP_PRE_AMEND
    name = _RELIEF_CAP_BY_YEAR.get(assessment_year)
    if not name:
        raise ValueError(f"unsupported assessment_year: {assessment_year}")
    return name


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
        rs_id = row.get("rule_source_id")
        out.append(
            RateBand(
                rate_band_id=str(row["rate_band_id"]),
                band_index=int(row["band_index"]),
                band_label=str(row.get("band_label") or row["rate_band_id"]),
                lower=int(row.get("lower") or 0),
                upper=None if upper_raw is None else int(upper_raw),
                rate=Decimal(str(row["rate"])),
                source_doc_id=str(row.get("source_doc_id") or doc.get("source_doc_id") or ""),
                rule_source_id=str(rs_id) if rs_id else None,
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
        rs_id = row.get("rule_source_id")
        relief = ReliefCap(
            relief_id=str(row["relief_id"]),
            concept_id=str(row.get("concept_id") or row["relief_id"]),
            display_name=str(row.get("display_name") or row["relief_id"]),
            section_uid=(str(row["section_uid"]) if row.get("section_uid") else None),
            source_doc_id=str(row.get("source_doc_id") or ""),
            cap_amount=None if cap_amount is None else Decimal(str(cap_amount)),
            cap_pct_of_assessable=None if cap_pct is None else Decimal(str(cap_pct)),
            rule_source_id=str(rs_id) if rs_id else None,
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
    if not band_name:
        raise ValueError(f"unsupported assessment_year: {assessment_year}")
    relief_name = relief_cap_filename(assessment_year, param_set)

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
    """Deprecated: aggregate Sec 52 QP cap removed (Path B). Always False."""
    _ = (concept_id, section, amends_section)
    return False


def _is_sec52_cap_rule_legacy(
    *,
    concept_id: str | None,
    section: str | None,
    amends_section: str | None,
    maximum: float | None,
) -> bool:
    """Legacy matcher retained for reference tests only."""
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


def is_rate_band_rule(
    *,
    rule_type: str | None,
    concept_id: str | None,
    section: str | None,
    amends_section: str | None,
    engine_handler: str | None = None,
    schedule_ref: str | None = None,
) -> bool:
    """True when an approved rule should stamp First Schedule rate provenance."""
    rt = (rule_type or "").strip().lower()
    if rt == "rate":
        return True
    handler = (engine_handler or "").strip().lower()
    if handler in {"slab_band", "first_schedule_rates"}:
        return True
    concept = (concept_id or "").strip().lower()
    if concept in _RATE_CONCEPT_IDS:
        return True
    for raw in (section, amends_section, schedule_ref):
        token = _normalize_section_token(raw)
        if token in _RATE_SECTION_TOKENS or "first schedule" in token:
            return True
    return False


def is_personal_relief_rule(
    *,
    rule_type: str | None,
    concept_id: str | None,
    section: str | None,
    amends_section: str | None,
    engine_handler: str | None = None,
    schedule_ref: str | None = None,
    maximum: float | None = None,
) -> bool:
    """True when an approved rule should stamp personal relief limit provenance."""
    handler = (engine_handler or "").strip().lower()
    if handler in {"personal_relief_resident", "apply_personal_relief"}:
        return True
    concept = (concept_id or "").strip().lower()
    if concept in _PERSONAL_RELIEF_CONCEPT_IDS:
        return True
    for raw in (section, amends_section, schedule_ref):
        token = _normalize_section_token(raw)
        if "personal relief" in token:
            return True
    rt = (rule_type or "").strip().lower()
    if rt in {"limit", "deduction"} and concept in _PERSONAL_RELIEF_CONCEPT_IDS:
        return maximum is not None
    return False


def is_donation_cap_rule(
    *,
    rule_type: str | None,
    concept_id: str | None,
    section: str | None,
    amends_section: str | None,
    engine_handler: str | None = None,
    threshold: float | None = None,
    maximum: float | None = None,
) -> bool:
    """True when an approved rule should stamp donation cap percent provenance."""
    handler = (engine_handler or "").strip().lower()
    if handler in {"cap_percent_assessable", "cap_percent_assessable:donation_cap"}:
        return True
    concept = (concept_id or "").strip().lower()
    if concept in _DONATION_CAP_CONCEPT_IDS and threshold is not None:
        return True
    rt = (rule_type or "").strip().lower()
    if rt in {"limit", "deduction"} and concept == "donation_cap":
        return threshold is not None or maximum is not None
    for raw in (section, amends_section):
        token = _normalize_section_token(raw)
        if token in _SEC52_SECTION_TOKENS and concept in _DONATION_CAP_CONCEPT_IDS:
            return threshold is not None
    return False


def _upsert_relief_update(doc: dict[str, Any], update: dict[str, Any]) -> None:
    """Merge one relief update into ``doc['relief_updates']`` by concept_id."""
    concept_id = str(update.get("concept_id") or "").strip()
    if not concept_id:
        return
    rows = doc.setdefault("relief_updates", [])
    if not isinstance(rows, list):
        rows = []
        doc["relief_updates"] = rows
    for idx, row in enumerate(rows):
        if isinstance(row, dict) and str(row.get("concept_id") or "") == concept_id:
            rows[idx] = {**row, **update}
            return
    rows.append(update)


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

    by_concept = dict(pack.reliefs_by_concept)
    by_id = dict(pack.reliefs_by_id)
    rate_bands = list(pack.rate_bands)

    updates = doc.get("relief_updates")
    if isinstance(updates, list) and updates:
        for upd in updates:
            if not isinstance(upd, dict):
                continue
            concept_id = str(upd.get("concept_id") or "").strip()
            if not concept_id:
                continue
            year_filter = str(upd.get("assessment_year") or "").strip()
            if year_filter and year_filter != pack.assessment_year:
                continue
            existing = by_concept.get(concept_id) or by_id.get(
                str(upd.get("relief_id") or "").strip()
            )
            if existing is None:
                relief_id = str(upd.get("relief_id") or concept_id)
                cap_raw = upd.get("cap_amount")
                if cap_raw is None:
                    continue
                rs_id = upd.get("rule_source_id")
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
                    rule_source_id=str(rs_id) if rs_id else None,
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
                if upd.get("rule_source_id"):
                    kwargs["rule_source_id"] = str(upd["rule_source_id"])
                if upd.get("cap_pct_of_assessable") is not None:
                    kwargs["cap_pct_of_assessable"] = Decimal(
                        str(upd["cap_pct_of_assessable"])
                    )
                if not kwargs:
                    continue
                relief = replace(existing, **kwargs)

            by_concept[relief.concept_id] = relief
            by_id[relief.relief_id] = relief

    rate_updates = doc.get("rate_band_updates")
    if isinstance(rate_updates, list) and rate_updates:
        by_band_id = {b.rate_band_id: b for b in rate_bands}
        for upd in rate_updates:
            if not isinstance(upd, dict):
                continue
            year = str(upd.get("assessment_year") or "").strip()
            if year and year != pack.assessment_year:
                continue
            band_id = str(upd.get("rate_band_id") or "").strip()
            existing = by_band_id.get(band_id)
            if existing is None:
                # Optional full band insert when lower/rate provided.
                if upd.get("rate") is None or upd.get("band_index") is None:
                    continue
                upper_raw = upd.get("upper")
                new_band = RateBand(
                    rate_band_id=band_id or f"override_band_{upd['band_index']}",
                    band_index=int(upd["band_index"]),
                    band_label=str(upd.get("band_label") or band_id),
                    lower=int(upd.get("lower") or 0),
                    upper=None if upper_raw is None else int(upper_raw),
                    rate=Decimal(str(upd["rate"])),
                    source_doc_id=str(upd.get("source_doc_id") or ""),
                    rule_source_id=(
                        str(upd["rule_source_id"]) if upd.get("rule_source_id") else None
                    ),
                )
                by_band_id[new_band.rate_band_id] = new_band
            else:
                kwargs = {}
                if upd.get("rate") is not None:
                    kwargs["rate"] = Decimal(str(upd["rate"]))
                if "lower" in upd and upd.get("lower") is not None:
                    kwargs["lower"] = int(upd["lower"])
                if "upper" in upd:
                    upper_raw = upd.get("upper")
                    kwargs["upper"] = None if upper_raw is None else int(upper_raw)
                if upd.get("source_doc_id"):
                    kwargs["source_doc_id"] = str(upd["source_doc_id"])
                if upd.get("rule_source_id"):
                    kwargs["rule_source_id"] = str(upd["rule_source_id"])
                if upd.get("band_label"):
                    kwargs["band_label"] = str(upd["band_label"])
                if not kwargs:
                    continue
                by_band_id[band_id] = replace(existing, **kwargs)
        rate_bands = sorted(by_band_id.values(), key=lambda b: b.band_index)

    return TaxParamPack(
        assessment_year=pack.assessment_year,
        param_set=pack.param_set,
        currency=pack.currency,
        rate_bands=tuple(rate_bands),
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
    """Copy pre-amend personal relief (1.2M) into the override file for viva T1."""
    cfg = settings or get_adaptive_tax_settings()
    pre = load_tax_param_pack(
        assessment_year="2024_25",
        param_set="pre_amend_2025",
        apply_override=False,
        settings=cfg,
    )
    pr = pre.relief_for_concept("personal_relief")
    if pr is None or pr.cap_amount is None:
        raise FileNotFoundError("pre-amend personal_relief missing from ontology")

    doc: dict[str, Any] = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "reset_to_pre_amend",
        "amendment_job_id": None,
        "rule_source_id": pr.rule_source_id,
    }
    # YA 2025/26 pack carries 1.8M personal relief; pre-amend viva T1 keeps 1.2M.
    _upsert_relief_update(
        doc,
        {
            "assessment_year": "2025_26",
            "concept_id": pr.concept_id,
            "relief_id": pr.relief_id,
            "display_name": pr.display_name,
            "section_uid": pr.section_uid,
            "source_doc_id": pr.source_doc_id,
            "cap_amount": int(pr.cap_amount),
            "rule_source_id": pr.rule_source_id,
        },
    )
    path = _write_override_doc(doc, settings=cfg)
    return ParamOverrideWriteResult(
        path=path,
        source="reset_to_pre_amend",
        concept_id=pr.concept_id,
        cap_amount=pr.cap_amount,
        rule_source_id=pr.rule_source_id,
    )


def write_sec52_override_from_rules(
    rules: Sequence[Any],
    *,
    amendment_job_id: uuid.UUID | str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> ParamOverrideWriteResult | None:
    """Deprecated: no aggregate Sec 52 QP cap. Use ``write_personal_relief_override_from_rules``."""
    _ = (rules, amendment_job_id, settings)
    return None


def write_rate_band_override_from_rules(
    rules: Sequence[Any],
    *,
    amendment_job_id: uuid.UUID | str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> RateBandOverrideWriteResult | None:
    """Stamp approved ``rule_type=rate`` provenance onto First Schedule pack bands.

    Writes ``rate_band_updates`` into the runtime override file (preserving any
    existing ``relief_updates``). Returns ``None`` when no matching rate rule.
    """
    cfg = settings or get_adaptive_tax_settings()
    matched: list[Any] = []
    for rule in rules:
        rule_type = getattr(rule, "rule_type", None)
        rule_type_val = (
            rule_type.value if hasattr(rule_type, "value") else rule_type
        )
        if is_rate_band_rule(
            rule_type=str(rule_type_val) if rule_type_val else None,
            concept_id=getattr(rule, "concept_id", None),
            section=getattr(rule, "section", None),
            amends_section=getattr(rule, "amends_section", None),
            engine_handler=getattr(rule, "engine_handler", None),
            schedule_ref=getattr(rule, "schedule_ref", None),
        ):
            matched.append(rule)

    if not matched:
        return None

    preferred = matched[0]
    rule_id = getattr(preferred, "id", None)
    job_id = amendment_job_id or getattr(preferred, "amendment_job_id", None)

    years: list[str] = []
    raw_years = getattr(preferred, "assessment_years", None)
    if isinstance(raw_years, (list, tuple)) and raw_years:
        years = [str(y) for y in raw_years]
    else:
        # Default: stamp YA matching source doc / both packs when unspecified.
        years = ["2024_25", "2025_26"]

    updates: list[dict[str, Any]] = []
    for year in years:
        if year not in _RATE_BAND_FILES:
            continue
        pack = load_tax_param_pack(
            assessment_year=year,  # type: ignore[arg-type]
            param_set="current",
            apply_override=False,
            settings=cfg,
        )
        source_doc = (
            "ird-amend-2025-02" if year == "2025_26" else "ird-ira-2017-base"
        )
        for band in pack.rate_bands:
            row: dict[str, Any] = {
                "assessment_year": year,
                "rate_band_id": band.rate_band_id,
                "band_index": band.band_index,
                "band_label": band.band_label,
                "lower": band.lower,
                "upper": band.upper,
                "rate": float(band.rate),
                "source_doc_id": source_doc,
                "rule_source_id": str(rule_id) if rule_id else band.rule_source_id,
            }
            # Optional per-band numeric rewrite from extract fields.
            for cand in matched:
                para = (getattr(cand, "paragraph", None) or "").strip()
                if para and para not in {str(band.band_index), f"band_{band.band_index}"}:
                    continue
                if getattr(cand, "maximum", None) is not None and (
                    getattr(cand, "formula", None) or ""
                ).strip().startswith("0."):
                    try:
                        row["rate"] = float(str(getattr(cand, "formula")).strip())
                    except ValueError:
                        pass
                if getattr(cand, "threshold", None) is not None:
                    row["upper"] = int(getattr(cand, "threshold"))
                if getattr(cand, "id", None):
                    row["rule_source_id"] = str(cand.id)
            updates.append(row)

    if not updates:
        return None

    prior = read_param_override(settings=cfg) or {}
    doc: dict[str, Any] = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "rate_approve",
        "amendment_job_id": str(job_id) if job_id else None,
        "rule_source_id": str(rule_id) if rule_id else None,
        "rate_band_updates": updates,
    }
    if isinstance(prior.get("relief_updates"), list):
        doc["relief_updates"] = prior["relief_updates"]
        doc["source"] = "sec52_and_rate_approve"

    path = _write_override_doc(doc, settings=cfg)
    return RateBandOverrideWriteResult(
        path=path,
        source=str(doc["source"]),
        concept_id="first_schedule_rates",
        assessment_years=tuple(years),
        band_update_count=len(updates),
        rule_source_id=str(rule_id) if rule_id else None,
        amendment_job_id=str(job_id) if job_id else None,
    )


def write_personal_relief_override_from_rules(
    rules: Sequence[Any],
    *,
    amendment_job_id: uuid.UUID | str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> ParamOverrideWriteResult | None:
    """Stamp approved personal relief limit into runtime ``relief_updates``.

    Returns ``None`` when no matching personal-relief rule is present.
    """
    cfg = settings or get_adaptive_tax_settings()
    matched: list[Any] = []
    for rule in rules:
        rule_type = getattr(rule, "rule_type", None)
        rule_type_val = (
            rule_type.value if hasattr(rule_type, "value") else rule_type
        )
        if is_personal_relief_rule(
            rule_type=str(rule_type_val) if rule_type_val else None,
            concept_id=getattr(rule, "concept_id", None),
            section=getattr(rule, "section", None),
            amends_section=getattr(rule, "amends_section", None),
            engine_handler=getattr(rule, "engine_handler", None),
            schedule_ref=getattr(rule, "schedule_ref", None),
            maximum=getattr(rule, "maximum", None),
        ):
            matched.append(rule)

    if not matched:
        return None

    preferred = next(
        (
            r
            for r in matched
            if (getattr(r, "concept_id", None) or "").strip().lower() == "personal_relief"
        ),
        matched[0],
    )
    maximum = getattr(preferred, "maximum", None)
    if maximum is None:
        return None

    cap_amount = Decimal(str(maximum))
    rule_id = getattr(preferred, "id", None)
    job_id = amendment_job_id or getattr(preferred, "amendment_job_id", None)

    raw_years = getattr(preferred, "assessment_years", None)
    if isinstance(raw_years, (list, tuple)) and raw_years:
        assessment_year = str(raw_years[0])
    elif cap_amount >= Decimal("1800000"):
        assessment_year = "2025_26"
    else:
        assessment_year = "2024_25"

    pack = load_tax_param_pack(
        assessment_year=assessment_year,  # type: ignore[arg-type]
        param_set="current",
        apply_override=False,
        settings=cfg,
    )
    existing = pack.relief_for_concept("personal_relief")
    source_doc = (
        "ird-amend-2025-02" if assessment_year == "2025_26" else "ird-ira-2017-base"
    )

    prior = read_param_override(settings=cfg) or {}
    doc: dict[str, Any] = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "personal_relief_approve",
        "amendment_job_id": str(job_id) if job_id else None,
        "rule_source_id": str(rule_id) if rule_id else None,
    }
    _upsert_relief_update(
        doc,
        {
            "assessment_year": assessment_year,
            "concept_id": "personal_relief",
            "relief_id": existing.relief_id if existing else "personal_relief",
            "display_name": (
                existing.display_name if existing else "Personal relief (annual tax-free amount)"
            ),
            "section_uid": (
                existing.section_uid if existing else "ird-ira-2017-base::sec::first_schedule"
            ),
            "source_doc_id": source_doc,
            "cap_amount": int(cap_amount)
            if cap_amount == cap_amount.to_integral_value()
            else float(cap_amount),
            "rule_source_id": str(rule_id) if rule_id else None,
        },
    )
    if isinstance(prior.get("relief_updates"), list):
        for row in prior["relief_updates"]:
            if isinstance(row, dict) and row.get("concept_id") != "personal_relief":
                _upsert_relief_update(doc, row)
    if isinstance(prior.get("rate_band_updates"), list):
        doc["rate_band_updates"] = prior["rate_band_updates"]
        if doc["source"] == "personal_relief_approve" and prior.get("source"):
            doc["source"] = f"{prior['source']}_and_personal_relief"

    path = _write_override_doc(doc, settings=cfg)
    return ParamOverrideWriteResult(
        path=path,
        source=str(doc["source"]),
        concept_id="personal_relief",
        cap_amount=cap_amount,
        rule_source_id=str(rule_id) if rule_id else None,
        amendment_job_id=str(job_id) if job_id else None,
    )


def write_donation_cap_override_from_rules(
    rules: Sequence[Any],
    *,
    amendment_job_id: uuid.UUID | str | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> ParamOverrideWriteResult | None:
    """Stamp approved donation cap percent into runtime ``relief_updates``."""
    cfg = settings or get_adaptive_tax_settings()
    matched: list[Any] = []
    for rule in rules:
        if is_donation_cap_rule(
            rule_type=str(getattr(getattr(rule, "rule_type", None), "value", getattr(rule, "rule_type", None)) or ""),
            concept_id=getattr(rule, "concept_id", None),
            section=getattr(rule, "section", None),
            amends_section=getattr(rule, "amends_section", None),
            engine_handler=getattr(rule, "engine_handler", None),
            threshold=getattr(rule, "threshold", None),
            maximum=getattr(rule, "maximum", None),
        ):
            matched.append(rule)

    if not matched:
        return None

    preferred = next(
        (
            r
            for r in matched
            if (getattr(r, "concept_id", None) or "").strip().lower() == "donation_cap"
        ),
        matched[0],
    )
    threshold = getattr(preferred, "threshold", None)
    maximum = getattr(preferred, "maximum", None)
    if threshold is not None:
        cap_pct = Decimal(str(threshold))
    elif maximum is not None and float(maximum) <= 1:
        cap_pct = Decimal(str(maximum))
    else:
        return None

    rule_id = getattr(preferred, "id", None)
    job_id = amendment_job_id or getattr(preferred, "amendment_job_id", None)
    raw_years = getattr(preferred, "assessment_years", None)
    if isinstance(raw_years, (list, tuple)) and raw_years:
        years = [str(y) for y in raw_years]
    else:
        years = ["2024_25", "2025_26"]

    prior = read_param_override(settings=cfg) or {}
    doc: dict[str, Any] = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": "donation_cap_approve",
        "amendment_job_id": str(job_id) if job_id else None,
        "rule_source_id": str(rule_id) if rule_id else None,
    }

    for assessment_year in years:
        pack = load_tax_param_pack(
            assessment_year=assessment_year,  # type: ignore[arg-type]
            param_set="current",
            apply_override=False,
            settings=cfg,
        )
        existing = pack.relief_for_concept("donation_cap")
        if existing is None:
            continue
        _upsert_relief_update(
            doc,
            {
                "assessment_year": assessment_year,
                "concept_id": "donation_cap",
                "relief_id": existing.relief_id,
                "display_name": existing.display_name,
                "section_uid": existing.section_uid,
                "source_doc_id": existing.source_doc_id,
                "cap_pct_of_assessable": float(cap_pct),
                "rule_source_id": str(rule_id) if rule_id else None,
            },
        )

    if isinstance(prior.get("relief_updates"), list):
        for row in prior["relief_updates"]:
            if isinstance(row, dict) and row.get("concept_id") != "donation_cap":
                _upsert_relief_update(doc, row)
    if isinstance(prior.get("rate_band_updates"), list):
        doc["rate_band_updates"] = prior["rate_band_updates"]
        if prior.get("source"):
            doc["source"] = f"{prior['source']}_and_donation_cap"

    path = _write_override_doc(doc, settings=cfg)
    return ParamOverrideWriteResult(
        path=path,
        source=str(doc["source"]),
        concept_id="donation_cap",
        cap_amount=cap_pct,
        rule_source_id=str(rule_id) if rule_id else None,
        amendment_job_id=str(job_id) if job_id else None,
    )
