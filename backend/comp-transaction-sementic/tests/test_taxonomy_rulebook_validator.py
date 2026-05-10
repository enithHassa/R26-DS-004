"""Validation tests for taxonomy/rulebook consistency artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_validator_module():
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / "models" / "transaction-semantic" / "rules" / "validator.py"
    spec = importlib.util.spec_from_file_location("tx_semantic_rules_validator", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_taxonomy_rulebook_validator_passes_current_artifacts() -> None:
    mod = _load_validator_module()
    result = mod.validate_taxonomy_rulebook()
    assert result.ok, "\n".join(result.errors)
