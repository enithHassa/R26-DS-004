"""Deterministic tax-rule evaluation for Component 1 (no eval)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY_PATH = ROOT / "taxonomy.yaml"
DEFAULT_RULEBOOK_PATH = ROOT / "rules" / "sl_tax_rules_ira_2017_v1.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a top-level mapping object.")
    return raw

_ALLOWED_TOP_OPS = frozenset({"all", "any"})
_ALLOWED_LEAF_OPS = frozenset({"eq", "neq", "in", "not_in", "exists"})


@dataclass(frozen=True)
class TaxRuleDecision:
    class_key: str
    tax_rule_code: str
    taxability_status: str
    taxable_fraction: Decimal
    taxable_amount_lkr: Decimal
    treatment: str | None
    rule_reference: str
    explanation: str
    condition_id_matched: str | None = None
    review_reason: str | None = None
    decision_mode: str = "auto"


def _quantize_lkr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _coerce_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _evaluate_leaf(node: Mapping[str, Any], facts: Mapping[str, Any]) -> bool:
    field = node.get("field")
    op = node.get("op")
    if not isinstance(field, str) or op not in _ALLOWED_LEAF_OPS:
        return False
    actual = facts.get(field)
    if op == "exists":
        return field in facts and actual is not None
    if "value" not in node:
        return False
    expected = node["value"]
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "in":
        return actual in expected if isinstance(expected, (list, tuple, set)) else False
    if op == "not_in":
        return actual not in expected if isinstance(expected, (list, tuple, set)) else False
    return False


def _fields_in_when(node: Any) -> set[str]:
    if not isinstance(node, dict):
        return set()
    active = [key for key in _ALLOWED_TOP_OPS if key in node]
    if active:
        branch = active[0]
        children = node.get(branch)
        if not isinstance(children, list):
            return set()
        fields: set[str] = set()
        for child in children:
            fields |= _fields_in_when(child)
        return fields
    field = node.get("field")
    return {field} if isinstance(field, str) else set()


def _evaluate_when(node: Any, facts: Mapping[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False
    active = [key for key in _ALLOWED_TOP_OPS if key in node]
    if active:
        if len(active) != 1:
            return False
        branch = active[0]
        children = node.get(branch)
        if not isinstance(children, list) or not children:
            return False
        if branch == "all":
            return all(_evaluate_when(child, facts) for child in children)
        return any(_evaluate_when(child, facts) for child in children)
    return _evaluate_leaf(node, facts)


def _rule_branch_fields(rule: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "taxability_status": rule.get("taxability_status", "unknown"),
        "taxable_fraction": rule.get("taxable_fraction", 0.0),
        "treatment": rule.get("treatment"),
        "rule_reference": rule.get("rule_reference", ""),
        "explanation": rule.get("explanation", ""),
    }


class TaxRuleExecutor:
    def __init__(
        self,
        *,
        taxonomy_path: Path = DEFAULT_TAXONOMY_PATH,
        rulebook_path: Path = DEFAULT_RULEBOOK_PATH,
    ) -> None:
        self.taxonomy_path = taxonomy_path
        self.rulebook_path = rulebook_path
        self._taxonomy = _load_yaml(taxonomy_path)
        self._rulebook = _load_yaml(rulebook_path)
        self._rules: dict[str, Any] = self._rulebook.get("rules", {})
        self._label_to_rule: dict[str, str] = {}
        for item in self._taxonomy.get("labels", []):
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            code = item.get("tax_rule_code")
            if isinstance(key, str) and isinstance(code, str):
                self._label_to_rule[key] = code

    @property
    def taxonomy_version(self) -> str:
        return str(self._taxonomy.get("version", "unknown"))

    @property
    def rulebook_version(self) -> str:
        return str(self._rulebook.get("version", "unknown"))

    def rule_code_for_class(self, class_key: str) -> str | None:
        return self._label_to_rule.get(class_key)

    def evaluate(
        self,
        *,
        class_key: str,
        amount_lkr: Decimal | float | int | str,
        facts: Mapping[str, Any] | None = None,
        rule_code: str | None = None,
    ) -> TaxRuleDecision:
        facts_map: dict[str, Any] = dict(facts or {})
        code = rule_code or self._label_to_rule.get(class_key)
        if not code:
            return TaxRuleDecision(
                class_key=class_key,
                tax_rule_code="UNMAPPED_CLASS",
                taxability_status="unknown",
                taxable_fraction=Decimal("0"),
                taxable_amount_lkr=Decimal("0.00"),
                treatment="route_to_review_queue",
                rule_reference="Operational control",
                explanation=f"No tax rule mapped for class '{class_key}'.",
                review_reason="unmapped_class",
                decision_mode="human_required",
            )

        rule = self._rules.get(code)
        if not isinstance(rule, dict):
            return TaxRuleDecision(
                class_key=class_key,
                tax_rule_code=code,
                taxability_status="unknown",
                taxable_fraction=Decimal("0"),
                taxable_amount_lkr=Decimal("0.00"),
                treatment="route_to_review_queue",
                rule_reference="Operational control",
                explanation=f"Rule '{code}' is missing from the rulebook.",
                review_reason="missing_rule",
                decision_mode="human_required",
            )

        resolved_class = str(rule.get("class_key", class_key))
        amount = _coerce_decimal(amount_lkr)
        conditions = rule.get("conditions")
        if isinstance(conditions, list) and conditions:
            for cond in conditions:
                if not isinstance(cond, dict):
                    continue
                when = cond.get("when")
                required_fields = _fields_in_when(when)
                if required_fields and not required_fields.issubset(facts_map.keys()):
                    continue
                if when is not None and _evaluate_when(when, facts_map):
                    fraction = _coerce_decimal(cond.get("taxable_fraction", 0.0))
                    status = str(cond.get("taxability_status", "unknown"))
                    return TaxRuleDecision(
                        class_key=resolved_class,
                        tax_rule_code=code,
                        taxability_status=status,
                        taxable_fraction=fraction,
                        taxable_amount_lkr=_quantize_lkr(amount * fraction),
                        treatment=str(cond.get("treatment", rule.get("treatment")))
                        if cond.get("treatment") is not None or rule.get("treatment") is not None
                        else None,
                        rule_reference=str(cond.get("rule_reference", rule.get("rule_reference", ""))),
                        explanation=str(cond.get("explanation", rule.get("explanation", ""))),
                        condition_id_matched=str(cond.get("condition_id"))
                        if cond.get("condition_id") is not None
                        else None,
                    )

            base = _rule_branch_fields(rule)
            status = str(base["taxability_status"])
            if status == "partially_taxable":
                return TaxRuleDecision(
                    class_key=resolved_class,
                    tax_rule_code=code,
                    taxability_status="unknown",
                    taxable_fraction=Decimal("0"),
                    taxable_amount_lkr=Decimal("0.00"),
                    treatment=str(base["treatment"]) if base["treatment"] is not None else None,
                    rule_reference=str(base["rule_reference"]),
                    explanation=(
                        f"{base['explanation']} Additional facts are required to choose a branch."
                    ),
                    review_reason="conditional_facts_missing",
                    decision_mode="human_required",
                )

        base = _rule_branch_fields(rule)
        fraction = _coerce_decimal(base["taxable_fraction"])
        status = str(base["taxability_status"])
        decision_mode = "human_required" if status == "unknown" else "auto"
        review_reason = "review_required" if status == "unknown" else None
        return TaxRuleDecision(
            class_key=resolved_class,
            tax_rule_code=code,
            taxability_status=status,
            taxable_fraction=fraction,
            taxable_amount_lkr=_quantize_lkr(amount * fraction),
            treatment=str(base["treatment"]) if base["treatment"] is not None else None,
            rule_reference=str(base["rule_reference"]),
            explanation=str(base["explanation"]),
            review_reason=review_reason,
            decision_mode=decision_mode,
        )
