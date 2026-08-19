"""Phase 5.0b — resolve approved Act-backed rule_source rows for engine steps.

Provenance chain (must hold for every executable calc step)::

    CalculationTraceStep / rules_applied
        → rule_source_id(s)  [status = approved]
            → section (+ optional paragraph)
            → source_quote (verbatim from Act text)
            → source_doc_id (official IRD instrument)

Bootstrap seed: ``models/adaptive-tax/fixtures/provenance_bootstrap_v1.json``
(official Act quotes — not Tax Knowledge Base Master).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import RuleSourceRef
from backend.shared.config.settings import PROJECT_ROOT

ProvenanceMode = Literal["legacy", "strict"]

BOOTSTRAP_RELATIVE = Path("models/adaptive-tax/fixtures/provenance_bootstrap_v1.json")

# Official Acts / amendments only — Guide and Master are not executable SoT.
OFFICIAL_ACT_SOURCE_DOC_IDS: frozenset[str] = frozenset(
    {
        "ird-ira-2017-base",
        "ird-amend-2021-10",
        "ird-amend-2022-45",
        "ird-amend-2023-04",
        "ird-amend-2023-14",
        "ird-amend-2025-02",
        "ird-amend-2026-11",
        "ird-consolidated-2025",
    }
)

_SOURCE_QUOTE_MIN = 20


class ProvenanceError(RuntimeError):
    """Raised in strict mode when an executable step lacks Act-backed provenance."""


@dataclass(frozen=True)
class ProvenanceRecord:
    id: str
    section: str
    source_quote: str
    source_doc_id: str
    status: str
    section_uid: str | None = None
    concept_id: str | None = None
    kind: str = "source_doc"
    handler_ids: tuple[str, ...] = ()
    assessment_years: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def is_valid_act_backed(self) -> bool:
        if (self.status or "").lower() != "approved":
            return False
        if not (self.section or "").strip():
            return False
        quote = (self.source_quote or "").strip()
        if len(quote) < _SOURCE_QUOTE_MIN:
            return False
        if self.source_doc_id not in OFFICIAL_ACT_SOURCE_DOC_IDS:
            return False
        return True

    def to_ref(self) -> RuleSourceRef:
        return RuleSourceRef(
            id=self.id,
            kind=self.kind,
            section_uid=self.section_uid,
            concept_id=self.concept_id,
            section=self.section,
            source_quote=self.source_quote,
            source_doc_id=self.source_doc_id,
            status=self.status,
        )


@dataclass(frozen=True)
class ProvenanceResolution:
    """Result of resolving provenance for one engine handler."""

    handler_id: str
    records: tuple[ProvenanceRecord, ...]
    mode: ProvenanceMode
    used_legacy: bool = False

    @property
    def ok(self) -> bool:
        return any(r.is_valid_act_backed() for r in self.records)

    @property
    def rule_source_ids(self) -> list[str]:
        return [r.id for r in self.records]

    @property
    def refs(self) -> list[RuleSourceRef]:
        return [r.to_ref() for r in self.records]

    @property
    def section_uids(self) -> list[str]:
        return list(
            dict.fromkeys(r.section_uid for r in self.records if r.section_uid)
        )

    @property
    def provenance_tag(self) -> str:
        if self.ok and not self.used_legacy:
            return "approved"
        if self.used_legacy:
            return "legacy_seed"
        return "missing"


def get_provenance_mode(
    settings: AdaptiveTaxSettings | None = None,
) -> ProvenanceMode:
    cfg = settings or get_adaptive_tax_settings()
    mode = cfg.COMP_ADAPTIVE_TAX_PROVENANCE_MODE
    return "strict" if mode == "strict" else "legacy"


def bootstrap_path() -> Path:
    return PROJECT_ROOT / BOOTSTRAP_RELATIVE


@lru_cache
def _load_bootstrap_records(path_str: str | None = None) -> tuple[ProvenanceRecord, ...]:
    path = Path(path_str) if path_str else bootstrap_path()
    if not path.is_file():
        return ()
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: list[ProvenanceRecord] = []
    for row in doc.get("rules") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            ProvenanceRecord(
                id=str(row["id"]),
                section=str(row.get("section") or ""),
                source_quote=str(row.get("source_quote") or ""),
                source_doc_id=str(row.get("source_doc_id") or ""),
                status=str(row.get("status") or doc.get("status") or "approved"),
                section_uid=(str(row["section_uid"]) if row.get("section_uid") else None),
                concept_id=(str(row["concept_id"]) if row.get("concept_id") else None),
                kind=str(row.get("kind") or "source_doc"),
                handler_ids=tuple(str(h) for h in (row.get("handler_ids") or [])),
                assessment_years=tuple(
                    str(y) for y in (row.get("assessment_years") or [])
                ),
                aliases=tuple(str(a) for a in (row.get("aliases") or [])),
            )
        )
    return tuple(out)


def clear_provenance_cache() -> None:
    _load_bootstrap_records.cache_clear()


def _year_matches(record: ProvenanceRecord, assessment_year: str) -> bool:
    if not record.assessment_years:
        return True
    return assessment_year in record.assessment_years


def resolve_rule_sources(
    handler_id: str,
    assessment_year: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
    extra_keys: list[str] | None = None,
) -> ProvenanceResolution:
    """Resolve ≥1 approved Act-backed record for ``handler_id`` + YA.

    Also matches bootstrap ``aliases`` listed in ``extra_keys`` (ontology ids).
    """
    mode = get_provenance_mode(settings)
    keys = {handler_id, *(extra_keys or [])}
    matched: list[ProvenanceRecord] = []
    for record in _load_bootstrap_records():
        if not _year_matches(record, assessment_year):
            continue
        if handler_id in record.handler_ids:
            matched.append(record)
            continue
        if any(k in record.aliases or k == record.id for k in keys):
            matched.append(record)

    # Prefer valid Act-backed rows.
    valid = [r for r in matched if r.is_valid_act_backed()]
    if valid:
        return ProvenanceResolution(
            handler_id=handler_id,
            records=tuple(valid),
            mode=mode,
            used_legacy=False,
        )

    if mode == "legacy" and matched:
        # Incomplete bootstrap — still surface for legacy tagging.
        return ProvenanceResolution(
            handler_id=handler_id,
            records=tuple(matched),
            mode=mode,
            used_legacy=True,
        )

    return ProvenanceResolution(
        handler_id=handler_id,
        records=(),
        mode=mode,
        used_legacy=mode == "legacy",
    )


def require_provenance(
    handler_id: str,
    assessment_year: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
    extra_keys: list[str] | None = None,
    executable: bool = True,
) -> ProvenanceResolution:
    """Resolve provenance; raise in strict mode when missing for executable steps."""
    resolution = resolve_rule_sources(
        handler_id,
        assessment_year,
        settings=settings,
        extra_keys=extra_keys,
    )
    if not executable:
        return resolution
    if resolution.ok:
        return resolution
    if resolution.mode == "strict":
        raise ProvenanceError(
            f"Strict provenance: no approved Act-backed rule_source for "
            f"handler={handler_id!r} assessment_year={assessment_year!r}. "
            f"Harvest/approve an official Act quote or set "
            f"COMP_ADAPTIVE_TAX_PROVENANCE_MODE=legacy."
        )
    return resolution


def enrich_refs_from_ids(
    ids: list[str],
    assessment_year: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> list[RuleSourceRef]:
    """Attach section/quote/source_doc_id onto refs when bootstrap knows the id."""
    records = _load_bootstrap_records()
    by_key: dict[str, ProvenanceRecord] = {}
    for rec in records:
        if not _year_matches(rec, assessment_year):
            continue
        by_key[rec.id] = rec
        for alias in rec.aliases:
            by_key.setdefault(alias, rec)

    out: list[RuleSourceRef] = []
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            continue
        seen.add(sid)
        rec = by_key.get(sid)
        if rec is not None and rec.is_valid_act_backed():
            # Keep caller's id when it is an alias (golden compatibility).
            out.append(
                RuleSourceRef(
                    id=sid,
                    kind=rec.kind,
                    section_uid=rec.section_uid,
                    concept_id=rec.concept_id,
                    section=rec.section,
                    source_quote=rec.source_quote,
                    source_doc_id=rec.source_doc_id,
                    status=rec.status,
                )
            )
        else:
            out.append(RuleSourceRef(id=sid, kind="source_doc"))
    return out


def merge_rule_source_ids(
    *groups: list[str],
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for sid in group:
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(sid)
    return out


def provenance_complete_for_trace(
    steps: list[Any],
    *,
    tax_affecting_only: bool = True,
) -> bool:
    """True when every tax-affecting step has non-empty Act-backed provenance."""
    for step in steps:
        step_id = getattr(step, "step_id", "") or ""
        if tax_affecting_only and str(step_id).startswith("unresolved_"):
            continue
        if tax_affecting_only and step_id in {"final_tax"}:
            # final_tax is summary; still require ids
            pass
        tag = None
        inputs = getattr(step, "inputs", None) or {}
        if isinstance(inputs, dict):
            tag = inputs.get("provenance")
        explicit = getattr(step, "provenance", None)
        tag = explicit or tag
        ids = list(getattr(step, "rule_source_ids", None) or [])
        if not ids:
            return False
        if tag == "missing":
            return False
    return True
