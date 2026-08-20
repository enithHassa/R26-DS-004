#!/usr/bin/env python3
"""Adaptive Tax Phase 4/5 end-to-end viva demo (YA adaptivity + optional approve).

Requires Adaptive Tax API on ``--base-url`` (default ``http://127.0.0.1:8005``).

**Primary demo (Phase 5.4):** ex08 dual-YA switch — same employment + QP inputs,
``assessment_year=2024_25`` → T1, ``2025_26`` → T2 ≠ T1 (personal relief 1.2M vs 1.8M).

**Optional approve path:** ``--with-approve`` runs pre-amend personal relief reset →
approve Act 02/2025 personal relief → T2 ≠ T1 on runtime override.

Example::

  $env:COMP_ADAPTIVE_TAX_EXPLAIN_MODE = "fixture"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase4_demo.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent

_DEFAULT_PDF = _REPO / "data" / "raw" / "adaptive-tax" / "IR_Act_No_02-2025_E.pdf"
_EX08 = _REPO / "models" / "adaptive-tax" / "examples" / "ex08_post_amendment_sec52.json"
_VIVA_INPUTS = {
    "assessment_year": "2025_26",
    "resident_status": "resident",
    "employment_income": "3000000",
    "qualifying_payments": "0",
    "param_set": "current",
}
_MINIMAL_PDF = b"%PDF-1.4\n% Adaptive Tax Phase 4 demo stub (fixture extract)\n%%EOF\n"


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def _require_ok(resp: httpx.Response, *, step: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        detail = resp.text
        try:
            detail = _pretty(resp.json())
        except Exception:  # noqa: BLE001
            pass
        raise SystemExit(f"[FAIL] {step}: HTTP {resp.status_code}\n{detail}")
    if not resp.content:
        return {}
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"[FAIL] {step}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"[FAIL] {step}: expected JSON object, got {type(data)}")
    return data


def _resolve_pdf(path: Path, *, allow_stub: bool) -> Path:
    if path.is_file():
        return path
    if not allow_stub:
        raise SystemExit(
            f"[FAIL] PDF not found: {path}\n"
            "  Place IR_Act_No_02-2025_E.pdf under data/raw/adaptive-tax/, "
            "pass --pdf PATH, or use --allow-stub-pdf (fixture extract only)."
        )
    stub = _REPO / "data" / "processed" / "adaptive-tax" / "demo_stub_act_02_2025.pdf"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_bytes(_MINIMAL_PDF)
    print(f"[warn] Real Act PDF missing; wrote stub for fixture extract: {stub}")
    return stub


def _personal_relief_quote(body: dict[str, Any]) -> str | None:
    pr_step = next(
        (
            s
            for s in body.get("calculation_trace") or []
            if s.get("step_id") == "apply_personal_relief"
        ),
        None,
    )
    if not pr_step:
        return None
    pr_ids = pr_step.get("rule_source_ids") or []
    for ref in body.get("rule_source_refs") or []:
        if ref.get("id") in pr_ids and ref.get("source_quote"):
            return str(ref["source_quote"])[:120] + "..."
    return None


def run_ya_switch_demo(client: httpx.Client, *, fe: str) -> tuple[str, str, str, str]:
    """ex08 dual YA: T1 (2024/25) vs T2 (2025/26)."""
    doc = json.loads(_EX08.read_text(encoding="utf-8"))
    v24 = next(v for v in doc["variants"] if "2024_25" in v["id"])
    v25 = next(v for v in doc["variants"] if "2025_26" in v["id"])

    _banner("2) Calculate ex08 YA 2024/25 -> T1")
    t1 = _require_ok(
        client.post(f"{client.base_url}/api/v1/calculate", json=v24["inputs"]),
        step="POST /calculate (ex08 YA24)",
    )
    tax1 = str(t1.get("final_tax_lkr", ""))
    calc_id_1 = str(t1.get("calc_id", ""))
    print(f"T1 final_tax_lkr = {tax1}  (expected {v24['expected_final_tax_lkr']})")
    print(f"calc_id_1        = {calc_id_1}")
    q1 = _personal_relief_quote(t1)
    if q1:
        print(f"Personal relief quote (T1): {q1}")

    _banner("3) Calculate ex08 YA 2025/26 -> T2 (same inputs, different personal relief)")
    t2 = _require_ok(
        client.post(f"{client.base_url}/api/v1/calculate", json=v25["inputs"]),
        step="POST /calculate (ex08 YA25)",
    )
    tax2 = str(t2.get("final_tax_lkr", ""))
    calc_id_2 = str(t2.get("calc_id", ""))
    print(f"T2 final_tax_lkr = {tax2}  (expected {v25['expected_final_tax_lkr']})")
    print(f"calc_id_2        = {calc_id_2}")
    q2 = _personal_relief_quote(t2)
    if q2:
        print(f"Personal relief quote (T2): {q2}")

    if tax1 == tax2:
        raise SystemExit(
            f"[FAIL] expected T2 != T1 for dual-YA ex08; both={tax1!r}"
        )
    print(f"[ok] T2 != T1  ({tax2} != {tax1})  |Δ| = {abs(int(tax1) - int(tax2))}")

    _banner("4) Report URLs (frontend)")
    url1 = f"{fe}/adaptive-tax/report/{calc_id_1}"
    url2 = f"{fe}/adaptive-tax/report/{calc_id_2}"
    print(f"Report T1 (YA 2024/25): {url1}")
    print(f"Report T2 (YA 2025/26): {url2}")
    return tax1, tax2, calc_id_1, calc_id_2


def run_approve_demo(
    client: httpx.Client,
    *,
    pdf: Path,
) -> None:
    """Pre-amend personal relief reset → approve Act 02/2025 → T2 ≠ T1."""
    inputs = dict(_VIVA_INPUTS)

    _banner("A) Reset params -> pre-amend personal relief (1.2M)")
    reset = _require_ok(
        client.post(f"{client.base_url}/api/v1/admin/params/reset-to-pre-amend"),
        step="POST /admin/params/reset-to-pre-amend",
    )
    print(_pretty(reset))

    _banner("B) Calculate viva inputs -> T1 (pre-amend override)")
    t1 = _require_ok(
        client.post(f"{client.base_url}/api/v1/calculate", json=inputs),
        step="POST /calculate (T1)",
    )
    tax1 = str(t1.get("final_tax_lkr", ""))
    print(f"T1 = {tax1}")

    _banner("C) Upload + extract + approve Act 02/2025")
    with pdf.open("rb") as fh:
        upload = _require_ok(
            client.post(
                f"{client.base_url}/api/v1/admin/amendments/upload",
                files={"file": (pdf.name, fh, "application/pdf")},
            ),
            step="POST /admin/amendments/upload",
        )
    job_id = str(upload.get("id", ""))
    _require_ok(
        client.post(f"{client.base_url}/api/v1/admin/amendments/{job_id}/extract"),
        step="POST .../extract",
    )
    approved = _require_ok(
        client.post(f"{client.base_url}/api/v1/admin/amendments/{job_id}/approve"),
        step="POST .../approve",
    )
    print(
        "personal_relief_override:",
        _pretty(approved.get("personal_relief_override") or {}),
    )

    _banner("D) Re-calculate -> T2")
    t2 = _require_ok(
        client.post(f"{client.base_url}/api/v1/calculate", json=inputs),
        step="POST /calculate (T2)",
    )
    tax2 = str(t2.get("final_tax_lkr", ""))
    print(f"T2 = {tax2}")
    if tax1 == tax2:
        raise SystemExit(f"[FAIL] approve demo: T2 == T1 ({tax1})")
    print(f"[ok] approve T2 != T1 ({tax2} != {tax1})")


def run_demo(
    *,
    base_url: str,
    frontend_url: str,
    pdf_path: Path,
    allow_stub_pdf: bool,
    skip_explain: bool,
    with_approve: bool,
    timeout: float,
) -> int:
    api = base_url.rstrip("/")
    fe = frontend_url.rstrip("/")
    pdf = _resolve_pdf(pdf_path, allow_stub=allow_stub_pdf)

    with httpx.Client(base_url=api, timeout=timeout, follow_redirects=True) as client:
        _banner("1) Health check")
        health = _require_ok(client.get("/health"), step="GET /health")
        print(_pretty(health))

        tax1, tax2, calc_id_1, calc_id_2 = run_ya_switch_demo(client, fe=fe)

        if with_approve:
            run_approve_demo(client, pdf=pdf)

        if not skip_explain:
            _banner("5) Explain both calc_ids (YA switch)")
            for label, cid in (("calc_id_1", calc_id_1), ("calc_id_2", calc_id_2)):
                if not cid:
                    continue
                body = _require_ok(
                    client.post("/api/v1/explain", json={"calc_id": cid}),
                    step=f"POST /explain ({label})",
                )
                print(
                    f"{label}: insufficient_evidence={body.get('insufficient_evidence')} "
                    f"sections_cited={body.get('sections_cited')}"
                )

        print()
        print("Summary")
        print(f"  ex08 YA24 T1={tax1}  calc_id_1={calc_id_1}")
        print(f"  ex08 YA25 T2={tax2}  calc_id_2={calc_id_2}")
        if with_approve:
            print("  (also ran personal relief approve override demo)")
        print("[ok] Phase 5.4 viva demo sequence complete")
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8005")
    p.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    p.add_argument("--pdf", type=Path, default=_DEFAULT_PDF)
    p.add_argument("--allow-stub-pdf", action="store_true")
    p.add_argument("--skip-explain", action="store_true")
    p.add_argument(
        "--with-approve",
        action="store_true",
        help="Also run pre-amend personal relief → approve → T2≠T1 path",
    )
    p.add_argument("--timeout", type=float, default=180.0)
    args = p.parse_args()
    try:
        return run_demo(
            base_url=args.base_url,
            frontend_url=args.frontend_url,
            pdf_path=args.pdf if args.pdf.is_absolute() else _REPO / args.pdf,
            allow_stub_pdf=args.allow_stub_pdf,
            skip_explain=args.skip_explain,
            with_approve=args.with_approve,
            timeout=args.timeout,
        )
    except httpx.ConnectError as exc:
        print(
            f"[FAIL] cannot reach {args.base_url}: {exc}\n"
            "  Start Adaptive Tax on :8005 first (see docs/PHASES_RUNBOOK.md).",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
