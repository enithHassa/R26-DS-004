"""Load hyphenated ``comp-adaptive-tax/db`` ORM into a stable module alias."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_DB_ROOT = Path(__file__).resolve().parents[1] / "db"
_DB_ALIAS = "comp_adaptive_tax_db_runtime"


def load_adaptive_tax_db() -> ModuleType:
    """Import ``backend/comp-adaptive-tax/db`` (hyphenated path) once."""
    if _DB_ALIAS in sys.modules:
        return sys.modules[_DB_ALIAS]

    init_file = _DB_ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        _DB_ALIAS,
        init_file,
        submodule_search_locations=[str(_DB_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load adaptive-tax db package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DB_ALIAS] = module
    spec.loader.exec_module(module)
    return module


_db = load_adaptive_tax_db()

AmendmentJob = _db.amendment_job.AmendmentJob
AmendmentExtractRun = _db.amendment_extract_run.AmendmentExtractRun
RuleSource = _db.rule_source.RuleSource
RuleVersion = _db.rule_version.RuleVersion
AmendmentJobStatus = _db.enums.AmendmentJobStatus
AmendmentExtractRunStatus = _db.enums.AmendmentExtractRunStatus
RuleSourceStatus = _db.enums.RuleSourceStatus
RuleType = _db.enums.RuleType
