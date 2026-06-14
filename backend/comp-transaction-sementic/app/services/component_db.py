"""Runtime import helper for hyphenated component DB models."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

_DB_ROOT = Path(__file__).resolve().parents[2] / "db"
_DB_ALIAS = "comp_transaction_sementic_db_runtime"


def load_component_db() -> str:
    if _DB_ALIAS in sys.modules:
        return _DB_ALIAS
    spec = importlib.util.spec_from_file_location(
        _DB_ALIAS,
        _DB_ROOT / "__init__.py",
        submodule_search_locations=[str(_DB_ROOT)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DB_ALIAS] = module
    spec.loader.exec_module(module)
    return _DB_ALIAS


def taxability_output_model():
    alias = load_component_db()
    return importlib.import_module(f"{alias}.taxability_output").TaxabilityOutput


def transaction_label_model():
    alias = load_component_db()
    return importlib.import_module(f"{alias}.transaction_label").TransactionLabel


def label_source_enum():
    alias = load_component_db()
    return importlib.import_module(f"{alias}.enums").LabelSource


def taxability_status_enum():
    alias = load_component_db()
    return importlib.import_module(f"{alias}.enums").TaxabilityStatus  # noqa: RET504
