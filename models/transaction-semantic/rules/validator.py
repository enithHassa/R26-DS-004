"""Validation helpers for Component 1 taxonomy/rulebook artifacts.

Usage:
    python models/transaction-semantic/rules/validator.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY_PATH = ROOT / "taxonomy.yaml"
DEFAULT_RULEBOOK_PATH = ROOT / "rules" / "sl_tax_rules_ira_2017_v1.yaml"

_ALLOWED_TOP_OPS = {"all", "any"}
_ALLOWED_LEAF_OPS = {"eq", "neq", "in", "not_in", "exists"}


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a top-level mapping object.")
    return raw


def _validate_when_tree(node: Any, *, context: str, errors: list[str]) -> None:
    if not isinstance(node, dict):
        errors.append(f"{context}: condition tree must be a mapping.")
        return

    if any(k in node for k in _ALLOWED_TOP_OPS):
        active = [k for k in _ALLOWED_TOP_OPS if k in node]
        if len(active) != 1:
            errors.append(f"{context}: exactly one of {sorted(_ALLOWED_TOP_OPS)} is allowed.")
            return
        branch_key = active[0]
        children = node.get(branch_key)
        if not isinstance(children, list) or not children:
            errors.append(f"{context}: '{branch_key}' must be a non-empty list.")
            return
        for idx, child in enumerate(children):
            _validate_when_tree(child, context=f"{context}.{branch_key}[{idx}]", errors=errors)
        return

    field = node.get("field")
    op = node.get("op")
    if not isinstance(field, str) or not field.strip():
        errors.append(f"{context}: leaf condition must include non-empty 'field'.")
    if op not in _ALLOWED_LEAF_OPS:
        errors.append(
            f"{context}: leaf condition op '{op}' is invalid; allowed={sorted(_ALLOWED_LEAF_OPS)}.",
        )
    if op != "exists" and "value" not in node:
        errors.append(f"{context}: leaf condition with op '{op}' must include 'value'.")


def validate_taxonomy_rulebook(
    taxonomy_path: Path = DEFAULT_TAXONOMY_PATH,
    rulebook_path: Path = DEFAULT_RULEBOOK_PATH,
) -> ValidationResult:
    errors: list[str] = []
    taxonomy = _load_yaml(taxonomy_path)
    rulebook = _load_yaml(rulebook_path)

    labels = taxonomy.get("labels")
    rules = rulebook.get("rules")
    if not isinstance(labels, list) or not labels:
        return ValidationResult(errors=["taxonomy.labels must be a non-empty list."])
    if not isinstance(rules, dict) or not rules:
        return ValidationResult(errors=["rulebook.rules must be a non-empty mapping."])

    taxonomy_version = taxonomy.get("version")
    rulebook_taxonomy_version = rulebook.get("taxonomy_version")
    if taxonomy_version != rulebook_taxonomy_version:
        errors.append(
            "version mismatch: taxonomy.version "
            f"'{taxonomy_version}' != rulebook.taxonomy_version '{rulebook_taxonomy_version}'.",
        )

    taxonomy_labels: dict[str, str] = {}
    for idx, item in enumerate(labels):
        if not isinstance(item, dict):
            errors.append(f"taxonomy.labels[{idx}] must be a mapping.")
            continue
        label = item.get("key")
        code = item.get("tax_rule_code")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"taxonomy.labels[{idx}] missing valid 'key'.")
            continue
        if not isinstance(code, str) or not code.strip():
            errors.append(f"taxonomy label '{label}' missing valid 'tax_rule_code'.")
            continue
        taxonomy_labels[label] = code
        if code not in rules:
            errors.append(f"taxonomy label '{label}' points to unknown rule code '{code}'.")

    seen_rule_class_keys: set[str] = set()
    for rule_code, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"rule '{rule_code}' must be a mapping.")
            continue
        class_key = rule.get("class_key")
        if not isinstance(class_key, str) or not class_key.strip():
            errors.append(f"rule '{rule_code}' missing valid 'class_key'.")
            continue
        seen_rule_class_keys.add(class_key)
        if class_key not in taxonomy_labels:
            errors.append(f"rule '{rule_code}' references unknown taxonomy class '{class_key}'.")
        expected = taxonomy_labels.get(class_key)
        if expected and expected != rule_code:
            errors.append(
                f"rule code mismatch for class '{class_key}': taxonomy expects "
                f"'{expected}', but rulebook key is '{rule_code}'.",
            )

        has_conditions = "conditions" in rule
        if has_conditions:
            conditions = rule.get("conditions")
            if not isinstance(conditions, list) or not conditions:
                errors.append(f"rule '{rule_code}' has invalid conditions list.")
            else:
                for idx, cond in enumerate(conditions):
                    context = f"rule '{rule_code}' condition[{idx}]"
                    if not isinstance(cond, dict):
                        errors.append(f"{context} must be a mapping.")
                        continue
                    if not isinstance(cond.get("condition_id"), str):
                        errors.append(f"{context} missing 'condition_id'.")
                    if "when" not in cond:
                        errors.append(f"{context} missing 'when' tree.")
                    else:
                        _validate_when_tree(cond["when"], context=f"{context}.when", errors=errors)

    for label in taxonomy_labels:
        if label not in seen_rule_class_keys:
            errors.append(f"taxonomy label '{label}' has no corresponding rule.class_key.")

    return ValidationResult(errors=errors)


def main() -> int:
    result = validate_taxonomy_rulebook()
    if result.ok:
        print("taxonomy-rulebook validation passed")
        return 0
    print("taxonomy-rulebook validation failed:")
    for err in result.errors:
        print(f" - {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
