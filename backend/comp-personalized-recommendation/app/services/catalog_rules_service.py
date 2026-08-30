"""Opt-in loader: Adaptive Tax catalog JSON → recommendation tax rules.

Does not replace the default ``sl_tax_*.yaml`` pack unless a caller explicitly
requests catalog rules (hybrid preview or admin sync). The default recommendation
pipeline continues to use ``COMP_RECOMMENDATION_RULES_PATH`` unchanged.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM


def _import_rules_engine() -> Any:
    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from rules.engine import TaxRules, apply_deductions, compute_annual_tax, load_tax_rules

    return TaxRules, apply_deductions, compute_annual_tax, load_tax_rules


@dataclass(frozen=True)
class RulesFieldDiff:
    field: str
    default_value: str
    catalog_value: str
    act_reference: str | None = None
    section_ref: str | None = None


@dataclass(frozen=True)
class CatalogActReference:
    label: str
    act_name: str
    section_ref: str | None
    source_doc_id: str | None
    effective_from: str | None
    quote_excerpt: str | None


@dataclass(frozen=True)
class CatalogPreviewMetadata:
    assessment_year: str
    assessment_period: str
    promoted_at: str | None
    promotion_source: str | None
    promotion_run: str | None
    carried_forward_from: str | None
    watcher_source_doc_id: str | None
    catalog_notes: str | None
    default_rules_version: str
    default_rules_label: str
    relief_entries_count: int
    rate_bands_count: int
    mapped_fields: list[str]
    fallback_fields: list[str]
    legal_references: list[CatalogActReference]


@dataclass
class CatalogRulesSnapshot:
    assessment_year: str
    rules: Any  # TaxRules
    promoted_at: str | None
    promotion_source: str | None
    personal_relief_act: str | None
    synced_at: str
    approved_path: str
    rates_path: str
    mapped_fields: list[str] = field(default_factory=list)
    fallback_fields: list[str] = field(default_factory=list)


# In-memory opt-in cache — cleared on process restart; default YAML unaffected.
_SYNCED_CATALOG: dict[str, CatalogRulesSnapshot] = {}


def catalog_approved_dir() -> Path:
    return component_settings.COMP_RECOMMENDATION_CATALOG_APPROVED_DIR


def catalog_rates_dir() -> Path:
    return component_settings.COMP_RECOMMENDATION_CATALOG_RATES_DIR


def list_catalog_assessment_years() -> list[str]:
    years: list[str] = []
    for path in sorted(catalog_approved_dir().glob("*.json")):
        stem = path.stem
        if stem and stem[0].isdigit():
            years.append(stem)
    return years


def _entry_cap(entries: list[dict[str, Any]], compare_group_id: str) -> float | None:
    for entry in entries:
        if entry.get("compare_group_id") != compare_group_id:
            continue
        raw = entry.get("cap_amount")
        if raw is None or raw == "":
            return None
        return float(str(raw).replace(",", ""))
    return None


def _rates_to_apit_slabs(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(bands, key=lambda b: int(b.get("band_index", 0)))
    slabs: list[dict[str, Any]] = []
    for band in ordered:
        lower = float(band["lower"])
        upper_raw = band.get("upper")
        rate = float(band["rate_percent"]) / 100.0
        if upper_raw is None:
            slabs.append({"upper": None, "rate": rate})
        else:
            width = float(upper_raw) - lower
            slabs.append({"upper": width, "rate": rate})
    return slabs


def _load_default_rules_dict() -> dict[str, Any]:
    TaxRules, _, _, load_tax_rules = _import_rules_engine()
    rules = load_tax_rules(component_settings.COMP_RECOMMENDATION_RULES_PATH)
    return {
        "version": rules.version,
        "currency": rules.currency,
        "personal_relief_annual": rules.personal_relief_annual,
        "apit_slabs": [
            {"upper": upper, "rate": rate} for upper, rate in rules.apit_slabs
        ],
        "deductions": dict(rules.deductions),
        "provident": dict(rules.provident),
    }


def build_rules_dict_from_catalog(assessment_year: str) -> dict[str, Any]:
    """Merge catalog JSON over the default YAML rule pack."""
    approved_path = catalog_approved_dir() / f"{assessment_year}.json"
    rates_path = catalog_rates_dir() / f"{assessment_year}.json"
    if not approved_path.is_file():
        raise FileNotFoundError(f"Catalog approved file not found: {approved_path}")
    if not rates_path.is_file():
        raise FileNotFoundError(f"Catalog rates file not found: {rates_path}")

    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    rates = json.loads(rates_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = approved.get("entries") or []
    bands: list[dict[str, Any]] = rates.get("bands") or []
    if not bands:
        raise ValueError(f"No rate bands in {rates_path}")

    merged = _load_default_rules_dict()
    mapped: list[str] = []
    fallback: list[str] = list(merged["deductions"].keys()) + ["provident"]

    merged["version"] = assessment_year

    personal_relief = _entry_cap(entries, "personal_relief")
    if personal_relief is not None:
        merged["personal_relief_annual"] = personal_relief
        mapped.append("personal_relief_annual")

    merged["apit_slabs"] = _rates_to_apit_slabs(bands)
    mapped.append("apit_slabs")

    return {
        "rules_dict": merged,
        "approved": approved,
        "rates": rates,
        "mapped_fields": mapped,
        "fallback_fields": fallback,
        "approved_path": str(approved_path),
        "rates_path": str(rates_path),
    }


def _ya_period_label(assessment_year: str) -> str:
    parts = assessment_year.split("_")
    if len(parts) != 2:
        return assessment_year
    start = int(parts[0])
    end = parts[1]
    return f"Year of assessment {start}/{end} (commencing 1 April {start})"


def _quote_excerpt(quote: str | None, *, max_len: int = 160) -> str | None:
    if not quote:
        return None
    cleaned = " ".join(str(quote).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _entry_by_group(entries: list[dict[str, Any]], compare_group_id: str) -> dict[str, Any] | None:
    return next((e for e in entries if e.get("compare_group_id") == compare_group_id), None)


def _unique_act_names(*sources: dict[str, Any] | None) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for src in sources:
        if not src:
            continue
        name = str(src.get("act_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def extract_catalog_preview_metadata(assessment_year: str) -> CatalogPreviewMetadata:
    """Human-facing catalog context for preview / demo UI."""
    built = build_rules_dict_from_catalog(assessment_year)
    approved: dict[str, Any] = built["approved"]
    rates: dict[str, Any] = built["rates"]
    entries: list[dict[str, Any]] = approved.get("entries") or []
    bands: list[dict[str, Any]] = rates.get("bands") or []

    personal = _entry_by_group(entries, "personal_relief")
    first_band = bands[0] if bands else None

    legal_refs: list[CatalogActReference] = []
    if personal:
        prov = personal.get("provenance") if isinstance(personal.get("provenance"), dict) else {}
        legal_refs.append(
            CatalogActReference(
                label="Personal relief (Fifth Schedule)",
                act_name=str(personal.get("act_name") or "—"),
                section_ref=personal.get("section_ref"),
                source_doc_id=personal.get("source_doc_id"),
                effective_from=prov.get("effective_from") or prov.get("effective_from_stated") or None,
                quote_excerpt=_quote_excerpt(personal.get("quote")),
            )
        )
    if first_band:
        legal_refs.append(
            CatalogActReference(
                label="APIT rate bands (First Schedule)",
                act_name=str(first_band.get("act_name") or first_band.get("act_name_extracted") or "—"),
                section_ref=first_band.get("section_ref"),
                source_doc_id=first_band.get("source_doc_id"),
                effective_from=None,
                quote_excerpt=_quote_excerpt(first_band.get("quote")),
            )
        )

    TaxRules, _, _, load_tax_rules = _import_rules_engine()
    default = load_tax_rules(component_settings.COMP_RECOMMENDATION_RULES_PATH)

    notes = approved.get("notes")
    if isinstance(notes, str) and len(notes) > 280:
        notes = notes[:279].rstrip() + "…"

    return CatalogPreviewMetadata(
        assessment_year=assessment_year,
        assessment_period=_ya_period_label(assessment_year),
        promoted_at=approved.get("promoted_at") or rates.get("promoted_at"),
        promotion_source=approved.get("promotion_source"),
        promotion_run=approved.get("promotion_run") or rates.get("promotion_run"),
        carried_forward_from=approved.get("carried_forward_from"),
        watcher_source_doc_id=approved.get("watcher_source_doc_id"),
        catalog_notes=notes if isinstance(notes, str) else None,
        default_rules_version=default.version,
        default_rules_label=f"Static YAML pack ({component_settings.COMP_RECOMMENDATION_RULES_PATH.name})",
        relief_entries_count=len(entries),
        rate_bands_count=len(bands),
        mapped_fields=built["mapped_fields"],
        fallback_fields=built["fallback_fields"],
        legal_references=legal_refs,
    )


def metadata_to_dict(meta: CatalogPreviewMetadata) -> dict[str, Any]:
    return {
        "assessment_year": meta.assessment_year,
        "assessment_period": meta.assessment_period,
        "promoted_at": meta.promoted_at,
        "promotion_source": meta.promotion_source,
        "promotion_run": meta.promotion_run,
        "carried_forward_from": meta.carried_forward_from,
        "watcher_source_doc_id": meta.watcher_source_doc_id,
        "catalog_notes": meta.catalog_notes,
        "default_rules_version": meta.default_rules_version,
        "default_rules_label": meta.default_rules_label,
        "relief_entries_count": meta.relief_entries_count,
        "rate_bands_count": meta.rate_bands_count,
        "mapped_fields": meta.mapped_fields,
        "fallback_fields": meta.fallback_fields,
        "legal_references": [
            {
                "label": ref.label,
                "act_name": ref.act_name,
                "section_ref": ref.section_ref,
                "source_doc_id": ref.source_doc_id,
                "effective_from": ref.effective_from,
                "quote_excerpt": ref.quote_excerpt,
            }
            for ref in meta.legal_references
        ],
    }


def diff_catalog_vs_default(assessment_year: str) -> list[RulesFieldDiff]:
    """Human-readable diff for demo UI."""
    built = build_rules_dict_from_catalog(assessment_year)
    catalog = built["rules_dict"]
    default = _load_default_rules_dict()
    approved: dict[str, Any] = built["approved"]
    rates: dict[str, Any] = built["rates"]
    entries: list[dict[str, Any]] = approved.get("entries") or []
    bands: list[dict[str, Any]] = rates.get("bands") or []
    personal = _entry_by_group(entries, "personal_relief")
    first_band = bands[0] if bands else None
    diffs: list[RulesFieldDiff] = []

    if catalog["personal_relief_annual"] != default["personal_relief_annual"]:
        diffs.append(
            RulesFieldDiff(
                field="personal_relief_annual",
                default_value=f"{default['personal_relief_annual']:,.0f}",
                catalog_value=f"{catalog['personal_relief_annual']:,.0f}",
                act_reference=(personal or {}).get("act_name"),
                section_ref=(personal or {}).get("section_ref"),
            )
        )

    default_slabs = default["apit_slabs"]
    catalog_slabs = catalog["apit_slabs"]
    if len(default_slabs) != len(catalog_slabs) or any(
        a != b for a, b in zip(default_slabs, catalog_slabs, strict=False)
    ):
        def _fmt_slabs(slabs: list[dict[str, Any]]) -> str:
            parts = []
            for slab in slabs:
                upper = slab["upper"]
                rate = float(slab["rate"]) * 100
                label = "∞" if upper is None else f"{float(upper):,.0f}"
                parts.append(f"{label} @ {rate:g}%")
            return " | ".join(parts)

        diffs.append(
            RulesFieldDiff(
                field="apit_slabs",
                default_value=_fmt_slabs(default_slabs),
                catalog_value=_fmt_slabs(catalog_slabs),
                act_reference=(first_band or {}).get("act_name") or (first_band or {}).get("act_name_extracted"),
                section_ref=(first_band or {}).get("section_ref"),
            )
        )

    return diffs


def sync_catalog_rules(assessment_year: str) -> CatalogRulesSnapshot:
    """Load catalog JSON into the in-memory opt-in cache."""
    TaxRules, _, _, _ = _import_rules_engine()
    built = build_rules_dict_from_catalog(assessment_year)
    approved: dict[str, Any] = built["approved"]

    personal_entry = next(
        (e for e in approved.get("entries", []) if e.get("compare_group_id") == "personal_relief"),
        None,
    )

    snapshot = CatalogRulesSnapshot(
        assessment_year=assessment_year,
        rules=TaxRules.from_dict(built["rules_dict"]),
        promoted_at=approved.get("promoted_at"),
        promotion_source=approved.get("promotion_source") or approved.get("notes"),
        personal_relief_act=(personal_entry or {}).get("act_name"),
        synced_at=datetime.now(UTC).isoformat(),
        approved_path=built["approved_path"],
        rates_path=built["rates_path"],
        mapped_fields=built["mapped_fields"],
        fallback_fields=built["fallback_fields"],
    )
    _SYNCED_CATALOG[assessment_year] = snapshot
    return snapshot


def get_synced_snapshot(assessment_year: str) -> CatalogRulesSnapshot | None:
    return _SYNCED_CATALOG.get(assessment_year)


def clear_synced_catalog() -> None:
    _SYNCED_CATALOG.clear()


def catalog_rules_status() -> dict[str, Any]:
    TaxRules, _, _, load_tax_rules = _import_rules_engine()
    default = load_tax_rules(component_settings.COMP_RECOMMENDATION_RULES_PATH)
    return {
        "default_rules_version": default.version,
        "default_rules_path": str(component_settings.COMP_RECOMMENDATION_RULES_PATH),
        "catalog_source": "adaptive-tax-relief-interview",
        "catalog_approved_dir": str(catalog_approved_dir()),
        "available_assessment_years": list_catalog_assessment_years(),
        "synced_years": [
            {
                "assessment_year": year,
                "synced_at": snap.synced_at,
                "promoted_at": snap.promoted_at,
                "personal_relief_act": snap.personal_relief_act,
                "mapped_fields": snap.mapped_fields,
            }
            for year, snap in sorted(_SYNCED_CATALOG.items())
        ],
    }


def baseline_tax_for_profile(profile: FinancialProfileORM, rules: Any) -> float:
    """Recompute baseline tax using an explicit rules pack (catalog or default)."""
    _, apply_deductions, compute_annual_tax, _ = _import_rules_engine()
    annual_income = float(profile.gross_annual_taxable_income or profile.gross_monthly_income * 12)
    taxable_after = apply_deductions(
        annual_income=annual_income,
        rules=rules,
        life_insurance_premium_annual=float(profile.life_insurance_premium_annual),
        health_insurance_premium_annual=15_000.0 if profile.health_insurance else 0.0,
        home_loan_interest_annual=float(profile.home_loan_interest_annual),
        donations_annual=float(profile.donations_annual),
    )
    return float(compute_annual_tax(taxable_after, rules))


__all__ = [
    "CatalogActReference",
    "CatalogPreviewMetadata",
    "CatalogRulesSnapshot",
    "RulesFieldDiff",
    "baseline_tax_for_profile",
    "build_rules_dict_from_catalog",
    "catalog_rules_status",
    "clear_synced_catalog",
    "diff_catalog_vs_default",
    "extract_catalog_preview_metadata",
    "get_synced_snapshot",
    "list_catalog_assessment_years",
    "metadata_to_dict",
    "sync_catalog_rules",
]
