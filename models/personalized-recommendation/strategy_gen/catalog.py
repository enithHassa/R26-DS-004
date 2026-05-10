"""Strategy catalog models + loader for declarative YAML catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EstimationMethod:
    type: str
    formula_ref: str
    required_inputs: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EstimationMethod":
        return cls(
            type=str(raw.get("type", "")),
            formula_ref=str(raw.get("formula_ref", "")),
            required_inputs=tuple(str(x) for x in raw.get("required_inputs", [])),
        )


@dataclass(frozen=True)
class StrategyConstraints:
    min_liquidity_lkr: float | None
    min_liquidity_lkr_expr: str | None
    max_debt_to_income: float | None
    required_docs: tuple[str, ...]
    profile_fields_required: tuple[str, ...]
    conflicts_with: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StrategyConstraints":
        return cls(
            min_liquidity_lkr=(
                None if raw.get("min_liquidity_lkr") is None else float(raw["min_liquidity_lkr"])
            ),
            min_liquidity_lkr_expr=(
                None if raw.get("min_liquidity_lkr_expr") is None else str(raw["min_liquidity_lkr_expr"])
            ),
            max_debt_to_income=(
                None if raw.get("max_debt_to_income") is None else float(raw["max_debt_to_income"])
            ),
            required_docs=tuple(str(x) for x in raw.get("required_docs", [])),
            profile_fields_required=tuple(str(x) for x in raw.get("profile_fields_required", [])),
            conflicts_with=tuple(str(x) for x in raw.get("conflicts_with", [])),
        )


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    description: str
    category: str
    priority_hint: int
    eligibility_rules: dict[str, Any]
    constraints: StrategyConstraints
    estimation_method: EstimationMethod

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StrategyDefinition":
        return cls(
            strategy_id=str(raw["strategy_id"]),
            name=str(raw["name"]),
            description=str(raw["description"]),
            category=str(raw.get("category", "other")),
            priority_hint=int(raw.get("priority_hint", 999)),
            eligibility_rules=dict(raw.get("eligibility_rules", {})),
            constraints=StrategyConstraints.from_dict(dict(raw.get("constraints", {}))),
            estimation_method=EstimationMethod.from_dict(dict(raw.get("estimation_method", {}))),
        )


@dataclass(frozen=True)
class StrategyCatalog:
    schema_version: str
    rules_pack_ref: str
    rules_pack_version: str
    effective_from: str
    context_variables: tuple[str, ...]
    conflict_rules: dict[str, tuple[str, ...]]
    strategies: tuple[StrategyDefinition, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StrategyCatalog":
        conflict_rules = {
            str(k): tuple(str(x) for x in v)
            for k, v in dict(raw.get("conflict_rules", {})).items()
        }
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            rules_pack_ref=str(raw.get("rules_pack_ref", "")),
            rules_pack_version=str(raw.get("rules_pack_version", "")),
            effective_from=str(raw.get("effective_from", "")),
            context_variables=tuple(str(x) for x in raw.get("context_variables", [])),
            conflict_rules=conflict_rules,
            strategies=tuple(
                StrategyDefinition.from_dict(s) for s in raw.get("strategies", [])
            ),
        )


def load_strategy_catalog(path: str | Path) -> StrategyCatalog:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Strategy catalog at {path} did not parse to a dict")
    return StrategyCatalog.from_dict(raw)

