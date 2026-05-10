"""Load and validate Component B rules YAML into immutable in-memory models.

File I/O and YAML parsing happen only in :func:`load_tax_opt_b_rules` /
:func:`parse_tax_opt_b_rules_dict`. The compliance engine receives a
:class:`TaxOptBRulePack` only — no disk reads during evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from typing import Any, Mapping

import yaml


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        raise TypeError("unexpected None for decimal conversion")
    return Decimal(str(value))


@dataclass(frozen=True)
class TaxOptBApitSlab:
    """One progressive APIT band (upper bound of slice; ``None`` = remainder)."""

    upper: int | None
    rate: Decimal


@dataclass(frozen=True)
class TaxOptBSourceRecord:
    act: str
    year: str
    section_note: str


@dataclass(frozen=True)
class TaxOptBThresholds:
    personal_relief_annual: Decimal
    apit_slabs: tuple[TaxOptBApitSlab, ...]
    deductions: dict[str, Decimal]


@dataclass(frozen=True)
class TaxOptBRuleSpec:
    """One declarative rule row from YAML (stable ``rule_id`` + ``rule_type``)."""

    rule_id: str
    rule_type: str
    description: str
    reference: str
    message: str
    relief_code: str | None = None
    cap_field: str | None = None
    cap_pct_field: str | None = None
    cap_annual_field: str | None = None


@dataclass(frozen=True)
class TaxOptBRulePack:
    """Validated ruleset for Function 1 (inject into :func:`evaluate_compliance`)."""

    path: Path | None
    schema_version: str
    assessment_year: str
    currency: str
    sources: tuple[TaxOptBSourceRecord, ...]
    thresholds: TaxOptBThresholds
    allowed_relief_codes: frozenset[str]
    rules: tuple[TaxOptBRuleSpec, ...]
    # Optional UI / Strategy Explorer: human labels and template strings (deterministic FR5).
    relief_display_names: tuple[tuple[str, str], ...] = ()
    search_explanation_templates: tuple[tuple[str, str], ...] = ()


def _require_str(data: Mapping[str, Any], key: str, *, ctx: str) -> str:
    v = data.get(key)
    if v is None or not isinstance(v, str) or not v.strip():
        msg = f"{ctx}: missing or invalid string field {key!r}"
        raise ValueError(msg)
    return v.strip()


def _parse_sources(raw: Mapping[str, Any], *, ctx: str) -> tuple[TaxOptBSourceRecord, ...]:
    src = raw.get("sources")
    if src is None:
        return ()
    if not isinstance(src, list):
        msg = f"{ctx}: sources must be a list when present"
        raise ValueError(msg)
    out: list[TaxOptBSourceRecord] = []
    for i, row in enumerate(src):
        if not isinstance(row, dict):
            msg = f"{ctx}: sources[{i}] must be a mapping"
            raise ValueError(msg)
        out.append(
            TaxOptBSourceRecord(
                act=str(row.get("act", "")),
                year=str(row.get("year", "")),
                section_note=str(row.get("section_note", row.get("note", ""))),
            )
        )
    return tuple(out)


def _parse_apit_slabs(rows: Any, *, ctx: str) -> tuple[TaxOptBApitSlab, ...]:
    if not isinstance(rows, list) or len(rows) == 0:
        msg = f"{ctx}: thresholds.apit_slabs must be a non-empty list"
        raise ValueError(msg)
    slabs: list[TaxOptBApitSlab] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            msg = f"{ctx}: apit_slabs[{i}] must be a mapping"
            raise ValueError(msg)
        up = row.get("upper")
        upper: int | None
        if up is None:
            upper = None
        else:
            upper = int(up)
        if row.get("rate") is None:
            msg = f"{ctx}: apit_slabs[{i}].rate is required"
            raise ValueError(msg)
        rate = _to_decimal(row["rate"])
        slabs.append(TaxOptBApitSlab(upper=upper, rate=rate))
    return tuple(slabs)


def _parse_thresholds(obj: Any, *, ctx: str) -> TaxOptBThresholds:
    if not isinstance(obj, dict):
        msg = f"{ctx}: thresholds must be a mapping"
        raise ValueError(msg)
    if obj.get("personal_relief_annual") is None:
        msg = f"{ctx}: thresholds.personal_relief_annual is required"
        raise ValueError(msg)
    pr = _to_decimal(obj["personal_relief_annual"])
    slabs = _parse_apit_slabs(obj.get("apit_slabs"), ctx=f"{ctx}.thresholds")
    ded = obj.get("deductions")
    if not isinstance(ded, dict) or not ded:
        msg = f"{ctx}: thresholds.deductions must be a non-empty mapping"
        raise ValueError(msg)
    deductions = {str(k): _to_decimal(v) for k, v in ded.items()}
    return TaxOptBThresholds(personal_relief_annual=pr, apit_slabs=slabs, deductions=deductions)


def _parse_rule_row(row: Any, *, ctx: str, index: int) -> TaxOptBRuleSpec:
    if not isinstance(row, dict):
        msg = f"{ctx}: rules[{index}] must be a mapping"
        raise ValueError(msg)
    rule_id = _require_str(row, "rule_id", ctx=f"{ctx}.rules[{index}]")
    rtype = row.get("type")
    if not isinstance(rtype, str) or not rtype.strip():
        msg = f"{ctx}.rules[{index}]: type is required"
        raise ValueError(msg)
    reference = str(row.get("reference", ""))
    description = str(row.get("description", ""))
    message = str(row.get("message", ""))
    rc = row.get("relief_code")
    cf = row.get("cap_field")
    cpf = row.get("cap_pct_field")
    caf = row.get("cap_annual_field")
    return TaxOptBRuleSpec(
        rule_id=rule_id,
        rule_type=rtype.strip(),
        description=description,
        reference=reference,
        message=message,
        relief_code=str(rc) if rc is not None else None,
        cap_field=str(cf) if cf is not None else None,
        cap_pct_field=str(cpf) if cpf is not None else None,
        cap_annual_field=str(caf) if caf is not None else None,
    )


def _parse_rules_list(rows: Any, *, ctx: str) -> tuple[TaxOptBRuleSpec, ...]:
    if not isinstance(rows, list) or len(rows) == 0:
        msg = f"{ctx}: rules must be a non-empty list"
        raise ValueError(msg)
    return tuple(_parse_rule_row(r, ctx=ctx, index=i) for i, r in enumerate(rows))


def _parse_str_str_mapping(
    raw: Any,
    *,
    ctx: str,
    field: str,
) -> tuple[tuple[str, str], ...]:
    """Optional mapping of string keys to string values; sorted by key for stable packs."""
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        msg = f"{ctx}: {field} must be a mapping when present"
        raise ValueError(msg)
    pairs: list[tuple[str, str]] = []
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            msg = f"{ctx}.{field}: keys and values must be strings"
            raise ValueError(msg)
        ks, vs = k.strip(), v.strip()
        if ks and vs:
            pairs.append((ks, vs))
    pairs.sort(key=lambda t: t[0])
    return tuple(pairs)


def parse_tax_opt_b_rules_dict(
    data: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> TaxOptBRulePack:
    """Parse an already-loaded YAML mapping into a :class:`TaxOptBRulePack` (no file I/O).

    Use in unit tests to inject rules without reading from disk.
    """
    ctx = "rules_pack"
    if not isinstance(data, Mapping):
        msg = "rules root must be a mapping"
        raise TypeError(msg)

    schema_version = _require_str(data, "schema_version", ctx=ctx)
    assessment_year = _require_str(data, "assessment_year", ctx=ctx)
    currency = _require_str(data, "currency", ctx=ctx)

    thresholds = _parse_thresholds(data.get("thresholds"), ctx=ctx)

    allowed = data.get("allowed_relief_codes")
    if not isinstance(allowed, list) or not allowed:
        msg = f"{ctx}: allowed_relief_codes must be a non-empty list"
        raise ValueError(msg)
    codes = frozenset(str(c) for c in allowed)

    rules = _parse_rules_list(data.get("rules"), ctx=ctx)
    sources = _parse_sources(data, ctx=ctx)
    relief_names = _parse_str_str_mapping(
        data.get("relief_display_names"),
        ctx=ctx,
        field="relief_display_names",
    )
    search_templates = _parse_str_str_mapping(
        data.get("search_explanation_templates"),
        ctx=ctx,
        field="search_explanation_templates",
    )

    return TaxOptBRulePack(
        path=path,
        schema_version=schema_version,
        assessment_year=assessment_year,
        currency=currency,
        sources=sources,
        thresholds=thresholds,
        allowed_relief_codes=codes,
        rules=rules,
        relief_display_names=relief_names,
        search_explanation_templates=search_templates,
    )


def load_tax_opt_b_rules(path: Path) -> TaxOptBRulePack:
    """Read YAML from ``path`` and return a validated :class:`TaxOptBRulePack`."""
    if not path.is_file():
        msg = f"Rules file not found: {path}"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = "Rules YAML root must be a mapping."
        raise ValueError(msg)
    return parse_tax_opt_b_rules_dict(data, path=path)


@lru_cache(maxsize=8)
def _load_tax_opt_b_rules_cached(path_resolved: str) -> TaxOptBRulePack:
    """Memoized load by resolved path string (optional hot-reload bypass in tests)."""
    return load_tax_opt_b_rules(Path(path_resolved))


def load_tax_opt_b_rules_cached(path: Path) -> TaxOptBRulePack:
    """Lazy cached load; same pack for the same resolved ``path`` until process restart."""
    return _load_tax_opt_b_rules_cached(str(path.resolve()))


__all__ = [
    "TaxOptBApitSlab",
    "TaxOptBRulePack",
    "TaxOptBRuleSpec",
    "TaxOptBSourceRecord",
    "TaxOptBThresholds",
    "load_tax_opt_b_rules",
    "load_tax_opt_b_rules_cached",
    "parse_tax_opt_b_rules_dict",
]
