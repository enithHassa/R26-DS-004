#!/usr/bin/env python3
"""Amendment adaptivity: pre/post Sec 52 tax delta matches expected param change.

Offline mode (default): run the rule engine on ex08 variants + ex04 with
param overrides (1.2M then 1.8M) without HTTP.

Live mode: call POST /calculate after documenting demo protocol expectations.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_COMP = _REPO / "backend" / "comp-adaptive-tax"
_EX08 = _REPO / "models" / "adaptive-tax" / "examples" / "ex08_post_amendment_sec52.json"
_EX04 = _REPO / "models" / "adaptive-tax" / "examples" / "ex04_salary_qualifying_payment.json"

for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _run_offline() -> dict[str, Any]:
    import os
    import tempfile
    import uuid
    from types import SimpleNamespace

    # Isolate override file so scoring does not touch the developer's demo override.
    tmp = Path(tempfile.mkdtemp(prefix="adaptive_tax_adaptivity_"))
    override_path = tmp / "active_relief_caps.json"
    os.environ["COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH"] = str(override_path)
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")

    from adaptive_tax_app.config import get_adaptive_tax_settings
    from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
    from adaptive_tax_app.services.param_store import (
        clear_param_store_cache,
        reset_param_override,
        seed_pre_amend_override,
        write_sec52_override_from_rules,
    )
    from adaptive_tax_app.services.rule_engine import calculate, default_file_kg

    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()
    settings = get_adaptive_tax_settings()
    reset_param_override(settings=settings)

    cases: list[dict[str, Any]] = []
    ex08 = json.loads(_EX08.read_text(encoding="utf-8"))
    kg = default_file_kg()

    for variant in ex08["variants"]:
        req = CalculateTaxRequestV1.model_validate(variant["inputs"])
        result = calculate(req, kg=kg)
        ok = result.final_tax_lkr == variant["expected_final_tax_lkr"]
        cases.append(
            {
                "id": variant["id"],
                "expected": variant["expected_final_tax_lkr"],
                "actual": result.final_tax_lkr,
                "ok": ok,
            }
        )

    pre = next(c for c in cases if "pre" in c["id"])
    post = next(c for c in cases if "current" in c["id"])
    delta_ok = pre["actual"] != post["actual"]
    expected_delta = abs(
        Decimal(ex08["variants"][0]["expected_final_tax_lkr"])
        - Decimal(ex08["variants"][1]["expected_final_tax_lkr"])
    )
    actual_delta = abs(Decimal(pre["actual"]) - Decimal(post["actual"]))

    ex04 = json.loads(_EX04.read_text(encoding="utf-8"))
    ex04_inputs = CalculateTaxRequestV1.model_validate(ex04["inputs"])

    seed_pre_amend_override(settings=settings)
    clear_param_store_cache()
    t1 = calculate(ex04_inputs, kg=kg).final_tax_lkr

    rule = SimpleNamespace(
        id=uuid.uuid4(),
        section="52",
        amends_section="52",
        concept_id="qualifying_payment_cap",
        maximum=1_800_000.0,
        amendment_job_id=uuid.uuid4(),
    )
    write_sec52_override_from_rules([rule], settings=settings)
    clear_param_store_cache()
    t2 = calculate(ex04_inputs, kg=kg).final_tax_lkr

    demo_ok = t1 != t2 and t1 == "48000" and t2 == "0"
    reset_param_override(settings=settings)
    clear_param_store_cache()

    return {
        "metric": "amendment_adaptivity",
        "ex08_cases": cases,
        "ex08_delta": {
            "pre": pre["actual"],
            "post": post["actual"],
            "expected_abs_delta": format(expected_delta, "f"),
            "actual_abs_delta": format(actual_delta, "f"),
            "ok": delta_ok and actual_delta == expected_delta,
        },
        "demo_ex04_override": {
            "t1": t1,
            "t2": t2,
            "expected_t1": "48000",
            "expected_t2": "0",
            "ok": demo_ok,
        },
        "ok": all(c["ok"] for c in cases) and delta_ok and demo_ok,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode",
        choices=["offline"],
        default="offline",
        help="offline = rule engine + param override (no HTTP)",
    )
    args = p.parse_args()
    if args.mode != "offline":
        print("only --mode offline is implemented", file=sys.stderr)
        return 2

    result = _run_offline()
    print(json.dumps(result, indent=2))
    print(f"amendment_adaptivity ok={result['ok']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
