"""Reference catalog of income types and default taxability from taxonomy + rulebook."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY_PATH = ROOT / "taxonomy.yaml"
DEFAULT_RULEBOOK_PATH = ROOT / "rules" / "sl_tax_rules_ira_2017_v1.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a top-level mapping object.")
    return raw


@dataclass(frozen=True)
class IncomeTypeCatalogEntry:
    class_key: str
    group: str
    description: str
    tax_rule_code: str
    default_taxability_status: str
    default_taxable_fraction: float
    treatment: str | None
    rule_reference: str
    explanation: str
    is_conditional: bool


def build_income_type_catalog(
    *,
    taxonomy_path: Path = DEFAULT_TAXONOMY_PATH,
    rulebook_path: Path = DEFAULT_RULEBOOK_PATH,
) -> list[IncomeTypeCatalogEntry]:
    taxonomy = _load_yaml(taxonomy_path)
    rulebook = _load_yaml(rulebook_path)
    rules: dict[str, Any] = rulebook.get("rules", {})
    out: list[IncomeTypeCatalogEntry] = []
    for item in taxonomy.get("labels", []):
        if not isinstance(item, dict):
            continue
        class_key = item.get("key")
        code = item.get("tax_rule_code")
        if not isinstance(class_key, str) or not isinstance(code, str):
            continue
        rule = rules.get(code, {})
        if not isinstance(rule, dict):
            rule = {}
        out.append(
            IncomeTypeCatalogEntry(
                class_key=class_key,
                group=str(item.get("group", "")),
                description=str(item.get("description", "")),
                tax_rule_code=code,
                default_taxability_status=str(rule.get("taxability_status", "unknown")),
                default_taxable_fraction=float(rule.get("taxable_fraction", 0.0)),
                treatment=str(rule["treatment"]) if rule.get("treatment") is not None else None,
                rule_reference=str(rule.get("rule_reference", "")),
                explanation=str(rule.get("explanation", "")),
                is_conditional=isinstance(rule.get("conditions"), list) and bool(rule.get("conditions")),
            ),
        )
    return out


def group_catalog_by_taxability(
    entries: list[IncomeTypeCatalogEntry],
) -> dict[str, list[IncomeTypeCatalogEntry]]:
    grouped: dict[str, list[IncomeTypeCatalogEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.default_taxability_status, []).append(entry)
    return grouped
