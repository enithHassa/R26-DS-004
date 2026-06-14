"""Backend wrapper around the YAML tax-rule executor."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

from .tax_semantic_paths import repo_root, rulebook_yaml_path, taxonomy_yaml_path


def _load_executor_module():
    mod_path = repo_root() / "models" / "transaction-semantic" / "rules" / "executor.py"
    spec = importlib.util.spec_from_file_location("tx_semantic_rule_executor", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def get_rule_executor():
    mod = _load_executor_module()
    return mod.TaxRuleExecutor(
        taxonomy_path=taxonomy_yaml_path(),
        rulebook_path=rulebook_yaml_path(),
    )
