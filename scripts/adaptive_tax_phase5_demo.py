#!/usr/bin/env python3
"""Adaptive Tax Phase 5.9 viva demo - dual YA + Sec 52 quotes (calculator-first).

Default mode is **offline** (rule engine + file KG + bootstrap provenance): no API
required. Use ``--http`` for the live Phase 4/5 HTTP sequence on ``:8005``.

Shows dissertation Chapter 4 adaptivity claim:

  same inputs -> YA 2024/25 (T1) != YA 2025/26 (T2)
  with distinct Sec 52 ``source_quote`` text per year.

Also smoke-checks a covered-area golden (ex17 APIT credit) so viva can show
gross ``final_tax_lkr`` vs ``tax_payable_lkr``.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  $env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase5_demo.py

  # Live API (Adaptive Tax on :8005):
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase5_demo.py --http
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_COMP = _REPO / "backend" / "comp-adaptive-tax"
_EX08 = _REPO / "models" / "adaptive-tax" / "examples" / "ex08_post_amendment_sec52.json"
_EX17 = _REPO / "models" / "adaptive-tax" / "examples" / "ex17_apit_credit.json"

for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _cap_quote_from_response(body: Any) -> tuple[str | None, str | None]:
    """Return (section, source_quote) for the Sec 52 cap step."""
    steps = getattr(body, "calculation_trace", None) or body.get("calculation_trace") or []
    refs = getattr(body, "rule_source_refs", None) or body.get("rule_source_refs") or []
    cap_step = next(
        (
            s
            for s in steps
            if (getattr(s, "step_id", None) or s.get("step_id"))
            == "cap_qualifying_payment_cap"
        ),
        None,
    )
    if not cap_step:
        return None, None
    cap_ids = list(
        getattr(cap_step, "rule_source_ids", None) or cap_step.get("rule_source_ids") or []
    )

    def _ref_fields(ref: Any) -> tuple[str | None, str | None, str | None, str | None]:
        rid = getattr(ref, "id", None) or ref.get("id")
        quote = getattr(ref, "source_quote", None) or ref.get("source_quote")
        section = getattr(ref, "section", None) or ref.get("section")
        concept = getattr(ref, "concept_id", None) or ref.get("concept_id")
        return (
            str(rid) if rid else None,
            str(quote) if quote else None,
            str(section) if section else None,
            str(concept) if concept else None,
        )

    # Prefer Sec 52 / qualifying_payment_cap quotes over other ids on the step.
    ranked: list[tuple[int, str, str]] = []
    for ref in refs:
        rid, quote, section, concept = _ref_fields(ref)
        if not rid or rid not in cap_ids or not quote:
            continue
        score = 0
        if section and ("52" in section or section.strip() == "52"):
            score += 3
        if concept and "qualifying_payment" in concept:
            score += 2
        if "sec52" in rid or "qualifying_payment" in rid:
            score += 2
        ranked.append((score, section or "52", quote))
    if not ranked:
        return None, None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1], ranked[0][2]


def _print_quote(label: str, section: str | None, quote: str | None) -> None:
    if not quote:
        print(f"{label}: (no Sec 52 cap quote on response)")
        return
    preview = quote if len(quote) <= 160 else quote[:157] + "..."
    sec = section or "52"
    print(f"{label}: section={sec}")
    print(f"  quote: {preview}")


def run_offline() -> int:
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    os.environ.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")

    from adaptive_tax_app.config import get_adaptive_tax_settings
    from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
    from adaptive_tax_app.services.param_store import clear_param_store_cache
    from adaptive_tax_app.services.provenance import clear_provenance_cache
    from adaptive_tax_app.services.rule_engine import calculate, default_file_kg

    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()
    clear_provenance_cache()
    kg = default_file_kg()

    doc = json.loads(_EX08.read_text(encoding="utf-8"))
    v24 = next(v for v in doc["variants"] if "2024_25" in v["id"])
    v25 = next(v for v in doc["variants"] if "2025_26" in v["id"])

    _banner("1) Offline health - file KG + strict provenance")
    print(f"KG mode     = {os.environ.get('COMP_ADAPTIVE_TAX_KG_MODE')}")
    print(f"Provenance  = {os.environ.get('COMP_ADAPTIVE_TAX_PROVENANCE_MODE')}")

    _banner("2) ex08 YA 2024/25 -> T1")
    t1 = calculate(CalculateTaxRequestV1.model_validate(v24["inputs"]), kg=kg)
    tax1 = t1.final_tax_lkr
    print(f"T1 final_tax_lkr = {tax1}  (expected {v24['expected_final_tax_lkr']})")
    if tax1 != v24["expected_final_tax_lkr"]:
        raise SystemExit(f"[FAIL] T1 mismatch: {tax1}")
    sec1, q1 = _cap_quote_from_response(t1)
    _print_quote("Sec 52 cap quote (T1)", sec1, q1)

    _banner("3) ex08 YA 2025/26 -> T2 (same inputs, different YA pack)")
    t2 = calculate(CalculateTaxRequestV1.model_validate(v25["inputs"]), kg=kg)
    tax2 = t2.final_tax_lkr
    print(f"T2 final_tax_lkr = {tax2}  (expected {v25['expected_final_tax_lkr']})")
    if tax2 != v25["expected_final_tax_lkr"]:
        raise SystemExit(f"[FAIL] T2 mismatch: {tax2}")
    sec2, q2 = _cap_quote_from_response(t2)
    _print_quote("Sec 52 cap quote (T2)", sec2, q2)

    if tax1 == tax2:
        raise SystemExit(f"[FAIL] expected T2 != T1; both={tax1!r}")
    if q1 and q2 and q1 == q2:
        raise SystemExit("[FAIL] Sec 52 quotes identical across YAs (expected distinct)")
    print(f"[ok] T2 != T1  ({tax2} != {tax1})  delta = {abs(int(tax1) - int(tax2))}")
    if q1 and q2:
        print("[ok] Sec 52 source_quote differs by YA")

    _banner("4) Covered-area smoke - ex17 APIT credit (Phase 5.8)")
    ex17 = json.loads(_EX17.read_text(encoding="utf-8"))
    credit = calculate(CalculateTaxRequestV1.model_validate(ex17["inputs"]), kg=kg)
    print(f"gross final_tax_lkr     = {credit.final_tax_lkr}")
    print(f"tax_payable_lkr         = {credit.tax_payable_lkr}")
    print(f"tax_credits_applied_lkr = {credit.tax_credits_applied_lkr}")
    if credit.final_tax_lkr != ex17["expected_final_tax_lkr"]:
        raise SystemExit("[FAIL] ex17 gross tax mismatch")
    if credit.tax_payable_lkr != ex17["expected_tax_payable_lkr"]:
        raise SystemExit("[FAIL] ex17 tax_payable mismatch")
    if "apply_tax_credit" not in credit.rules_applied:
        raise SystemExit("[FAIL] ex17 missing apply_tax_credit step")
    print("[ok] gross liability unchanged; payable after Act-backed credit")

    _banner("5) Coverage snapshot")
    cov_path = _REPO / "models" / "adaptive-tax" / "harvest" / "coverage_checklist_v1.json"
    import importlib.util

    scorer = _REPO / "evaluation" / "adaptive-tax" / "coverage" / "score_coverage.py"
    spec = importlib.util.spec_from_file_location("score_coverage", scorer)
    assert spec and spec.loader
    cov_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cov_mod)

    cov = cov_mod.score_coverage(json.loads(cov_path.read_text(encoding="utf-8")))
    print(
        f"Coverage = {cov['n_covered']}/{cov['n_planned']} "
        f"({cov['coverage_pct']}%)"
    )
    print(f"Areas: {', '.join(cov['covered_area_ids'])}")

    print()
    print("Summary")
    print(f"  ex08 YA24 T1={tax1}")
    print(f"  ex08 YA25 T2={tax2}")
    print(
        f"  ex17 gross={credit.final_tax_lkr} "
        f"payable={credit.tax_payable_lkr}"
    )
    print("[ok] Phase 5.9 offline viva demo complete")
    return 0


def run_http(*, base_url: str, frontend_url: str, skip_explain: bool, timeout: float) -> int:
    """Delegate to Phase 4 HTTP demo (same dual-YA + Sec 52 quotes)."""
    from adaptive_tax_phase4_demo import run_demo  # type: ignore

    return run_demo(
        base_url=base_url,
        frontend_url=frontend_url,
        pdf_path=_REPO / "data" / "raw" / "adaptive-tax" / "IR_Act_No_02-2025_E.pdf",
        allow_stub_pdf=True,
        skip_explain=skip_explain,
        with_approve=False,
        timeout=timeout,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--http",
        action="store_true",
        help="Call Adaptive Tax API on --base-url instead of offline engine",
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8005")
    p.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    p.add_argument("--skip-explain", action="store_true")
    p.add_argument("--timeout", type=float, default=180.0)
    args = p.parse_args()

    if args.http:
        # Import sibling script by path.
        sys.path.insert(0, str(_SCRIPTS))
        try:
            return run_http(
                base_url=args.base_url,
                frontend_url=args.frontend_url,
                skip_explain=args.skip_explain,
                timeout=args.timeout,
            )
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            return code
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] HTTP demo: {exc}", file=sys.stderr)
            return 2

    try:
        return run_offline()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code


if __name__ == "__main__":
    raise SystemExit(main())
