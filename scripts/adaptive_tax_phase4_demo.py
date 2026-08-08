#!/usr/bin/env python3
"""Adaptive Tax Phase 4 end-to-end viva demo (amendment adaptivity + explain).

Requires Adaptive Tax API on ``--base-url`` (default ``http://127.0.0.1:8005``)
with Postgres reachable for amendments, and preferably:

* ``COMP_ADAPTIVE_TAX_EXTRACTION_MODE=fixture`` (offline Act 02/2025 Sec 52 extract)
* ``COMP_ADAPTIVE_TAX_EXPLAIN_MODE=fixture`` (offline narrative)
* Chroma indexed for non-empty explain evidence (optional; insufficient_evidence ok)

Sequence::

  health -> reset-to-pre-amend -> calc ex04 (T1) -> upload/extract/approve Act
  -> calc ex04 (T2 != T1) -> explain both calc_ids -> print report URLs

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
_EX04 = _REPO / "models" / "adaptive-tax" / "examples" / "ex04_salary_qualifying_payment.json"
_MINIMAL_PDF = b"%PDF-1.4\n% Adaptive Tax Phase 4 demo stub (fixture extract)\n%%EOF\n"


def _load_ex04_inputs() -> dict[str, Any]:
    raw = json.loads(_EX04.read_text(encoding="utf-8"))
    return dict(raw["inputs"])


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


def run_demo(
    *,
    base_url: str,
    frontend_url: str,
    pdf_path: Path,
    allow_stub_pdf: bool,
    skip_explain: bool,
    timeout: float,
) -> int:
    api = base_url.rstrip("/")
    fe = frontend_url.rstrip("/")
    inputs = _load_ex04_inputs()
    pdf = _resolve_pdf(pdf_path, allow_stub=allow_stub_pdf)

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        _banner("1) Health check")
        health = _require_ok(client.get(f"{api}/health"), step="GET /health")
        print(_pretty(health))

        _banner("2) Reset params -> pre-amend Sec 52 cap (1.2M)")
        reset = _require_ok(
            client.post(f"{api}/api/v1/admin/params/reset-to-pre-amend"),
            step="POST /admin/params/reset-to-pre-amend",
        )
        print(_pretty(reset))
        print(f"override_path: {reset.get('override_path')}")
        print(f"qualifying_payment_cap: {reset.get('qualifying_payment_cap')}")

        _banner("3) Calculate ex04 inputs -> T1")
        t1 = _require_ok(
            client.post(f"{api}/api/v1/calculate", json=inputs),
            step="POST /calculate (T1)",
        )
        tax1 = str(t1.get("final_tax_lkr", ""))
        calc_id_1 = str(t1.get("calc_id", ""))
        print(f"T1 final_tax_lkr = {tax1}")
        print(f"calc_id_1        = {calc_id_1}")
        if not calc_id_1:
            raise SystemExit("[FAIL] calculate did not return calc_id")

        _banner("4) Upload Act 02/2025 PDF")
        print(f"pdf: {pdf}")
        with pdf.open("rb") as fh:
            upload = _require_ok(
                client.post(
                    f"{api}/api/v1/admin/amendments/upload",
                    files={"file": (pdf.name, fh, "application/pdf")},
                ),
                step="POST /admin/amendments/upload",
            )
        job_id = str(upload.get("id", ""))
        print(f"job_id = {job_id}  status={upload.get('status')}")
        if not job_id:
            raise SystemExit("[FAIL] upload did not return job id")

        _banner("5) Extract rules (fixture|openai per server env)")
        extracted = _require_ok(
            client.post(f"{api}/api/v1/admin/amendments/{job_id}/extract"),
            step="POST .../extract",
        )
        print(
            f"mode={extracted.get('mode')} model={extracted.get('model_name')} "
            f"rule_count={extracted.get('rule_count')}"
        )
        if extracted.get("warnings"):
            print(f"warnings: {extracted['warnings']}")

        _banner("6) Approve -> Neo4j MODIFIES + Chroma + param override")
        approved = _require_ok(
            client.post(f"{api}/api/v1/admin/amendments/{job_id}/approve"),
            step="POST .../approve",
        )
        merge = approved.get("merge") or {}
        override = approved.get("param_override") or {}
        print("merge:")
        print(_pretty(merge))
        print("param_override:")
        print(_pretty(override))
        details = merge.get("details") if isinstance(merge, dict) else None
        if isinstance(details, dict):
            print(f"MODIFIES targets: {details.get('modifies') or details.get('section_uids')}")
            print(f"chroma / merge details keys: {sorted(details.keys())}")

        _banner("7) Re-calculate same ex04 inputs -> T2")
        t2 = _require_ok(
            client.post(f"{api}/api/v1/calculate", json=inputs),
            step="POST /calculate (T2)",
        )
        tax2 = str(t2.get("final_tax_lkr", ""))
        calc_id_2 = str(t2.get("calc_id", ""))
        print(f"T2 final_tax_lkr = {tax2}")
        print(f"calc_id_2        = {calc_id_2}")
        if tax1 == tax2:
            raise SystemExit(
                f"[FAIL] expected T2 != T1 after Sec 52 approve; both={tax1!r}"
            )
        print(f"[ok] T2 != T1  ({tax2} != {tax1})")

        explain_1: dict[str, Any] | None = None
        explain_2: dict[str, Any] | None = None
        if not skip_explain:
            _banner("8) Explain both calc_ids")
            explain_1 = _require_ok(
                client.post(f"{api}/api/v1/explain", json={"calc_id": calc_id_1}),
                step="POST /explain (calc_id_1)",
            )
            explain_2 = _require_ok(
                client.post(f"{api}/api/v1/explain", json={"calc_id": calc_id_2}),
                step="POST /explain (calc_id_2)",
            )
            for label, body in (("calc_id_1", explain_1), ("calc_id_2", explain_2)):
                print(
                    f"{label}: insufficient_evidence={body.get('insufficient_evidence')} "
                    f"sections_cited={body.get('sections_cited')} "
                    f"final_tax_lkr={body.get('final_tax_lkr')}"
                )
        else:
            print("\n[skip] --skip-explain set; not calling POST /explain")

        _banner("9) Report URLs (frontend)")
        url1 = f"{fe}/adaptive-tax/report/{calc_id_1}"
        url2 = f"{fe}/adaptive-tax/report/{calc_id_2}"
        print(f"Report T1: {url1}")
        print(f"Report T2: {url2}")
        print()
        print("Summary")
        print(f"  T1={tax1}  calc_id_1={calc_id_1}")
        print(f"  T2={tax2}  calc_id_2={calc_id_2}")
        print(f"  job_id={job_id}")
        if override.get("path"):
            print(f"  override_path={override.get('path')}")
        if explain_1 is not None:
            print(
                f"  explain_1 insufficient={explain_1.get('insufficient_evidence')}"
            )
        if explain_2 is not None:
            print(
                f"  explain_2 insufficient={explain_2.get('insufficient_evidence')}"
            )
        print("[ok] Phase 4 demo sequence complete")
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default="http://127.0.0.1:8005",
        help="Adaptive Tax service base URL",
    )
    p.add_argument(
        "--frontend-url",
        default="http://127.0.0.1:5173",
        help="Vite frontend origin for report links",
    )
    p.add_argument(
        "--pdf",
        type=Path,
        default=_DEFAULT_PDF,
        help="Path to Act 02/2025 PDF (or any PDF when extraction_mode=fixture)",
    )
    p.add_argument(
        "--allow-stub-pdf",
        action="store_true",
        help="If --pdf is missing, write a minimal PDF stub (fixture extract only)",
    )
    p.add_argument(
        "--skip-explain",
        action="store_true",
        help="Skip POST /explain (still asserts T2 != T1)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="HTTP timeout seconds (extract may be slow in openai mode)",
    )
    args = p.parse_args()
    try:
        return run_demo(
            base_url=args.base_url,
            frontend_url=args.frontend_url,
            pdf_path=args.pdf if args.pdf.is_absolute() else _REPO / args.pdf,
            allow_stub_pdf=args.allow_stub_pdf,
            skip_explain=args.skip_explain,
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
