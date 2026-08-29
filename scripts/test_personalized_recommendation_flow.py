#!/usr/bin/env python3
"""End-to-end smoke test for Component 3 (personalized recommendation + impact).

Usage (services must be running):
  PYTHONPATH=backend/comp-personalized-recommendation:. .venv-backend/bin/python scripts/test_personalized_recommendation_flow.py

Optional env:
  COMP_RECOMMENDATION_URL=http://127.0.0.1:8003
  COMP_OE_ENGINE_URL=http://127.0.0.1:8009
  COMP_OE_RAG_URL=http://127.0.0.1:8008
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

import httpx

REC_URL = os.getenv("COMP_RECOMMENDATION_URL", "http://127.0.0.1:8003").rstrip("/")
OE_ENGINE_URL = os.getenv("COMP_OE_ENGINE_URL", "http://127.0.0.1:8009").rstrip("/")
OE_RAG_URL = os.getenv("COMP_OE_RAG_URL", "http://127.0.0.1:8008").rstrip("/")

PASS = 0
FAIL = 0
WARN = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  ✗ {msg}")


def warn(msg: str) -> None:
    global WARN
    WARN += 1
    print(f"  ⚠ {msg}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    client = httpx.Client(timeout=120.0)

    section("Health checks")
    try:
        r = client.get(f"{REC_URL}/health")
        if r.status_code == 200:
            ok(f"Recommendation API ({REC_URL})")
        else:
            fail(f"Recommendation API returned {r.status_code}")
            return 1
    except httpx.HTTPError as exc:
        fail(f"Recommendation API unreachable: {exc}")
        return 1

    oe_engine_up = False
    oe_rag_up = False
    try:
        r = client.get(f"{OE_ENGINE_URL}/health")
        oe_engine_up = r.status_code == 200
        ok(f"OE Engine ({OE_ENGINE_URL})") if oe_engine_up else warn(f"OE Engine health {r.status_code}")
    except httpx.HTTPError:
        warn(f"OE Engine not reachable on {OE_ENGINE_URL} — tax panels will use Comp 3 fallback")

    try:
        r = client.get(f"{OE_RAG_URL}/health")
        oe_rag_up = r.status_code == 200
        ok(f"OE RAG ({OE_RAG_URL})") if oe_rag_up else warn(f"OE RAG health {r.status_code}")
    except httpx.HTTPError:
        warn(f"OE RAG not reachable on {OE_RAG_URL} — tax panels will use Comp 3 fallback")

    section("1. Financial profile — create + derived features")
    profile_payload = {
        "full_name": "FlowTest_User",
        "age_band": "30-34",
        "province": "Western",
        "occupation": "employee",
        "gross_monthly_income": "350000",
        "monthly_expenses": "180000",
        "monthly_debt_service": "45000",
        "liquid_savings": "1200000",
        "life_insurance_premium_annual": "60000",
        "home_loan_interest_annual": "300000",
        "income_sources": [
            {"kind": "employment", "monthly_amount": "320000", "is_taxable": True},
            {"kind": "interest", "monthly_amount": "30000", "is_taxable": True},
        ],
        "tax_year": "2026_27",
    }
    r = client.post(f"{REC_URL}/api/v1/profiles", json=profile_payload)
    if r.status_code != 201:
        fail(f"Create profile failed: {r.status_code} {r.text[:300]}")
        return 1
    profile = r.json()
    pid = profile["id"]
    ok(f"Created profile {pid}")

    r = client.get(f"{REC_URL}/api/v1/profiles/{pid}/features")
    if r.status_code != 200:
        fail(f"Features endpoint failed: {r.status_code}")
        return 1
    feats = r.json()
    gross = Decimal(feats["gross_annual_taxable_income"])
    tax = Decimal(feats["baseline_tax_liability_annual"])
    if gross <= 0:
        fail(f"Derived gross annual taxable income is {gross}")
    else:
        ok(f"Derived taxable income: LKR {gross:,.0f}")
    if tax < 0:
        fail(f"Baseline tax negative: {tax}")
    else:
        ok(f"Derived baseline tax: LKR {tax:,.0f}")
    if 0 <= feats["effective_tax_rate"] <= 1:
        ok(f"Effective tax rate: {feats['effective_tax_rate']*100:.2f}%")
    else:
        fail(f"Invalid effective tax rate: {feats['effective_tax_rate']}")

    section("2. Eligibility override (auditor manual pin)")
    r = client.patch(
        f"{REC_URL}/api/v1/profiles/{pid}/eligibility-overrides",
        json={"flag": "has_life_insurance", "value": True},
    )
    if r.status_code == 200 and feats["eligibility_flags"].get("has_life_insurance") is not True:
        updated = r.json()
        if updated["eligibility_flags"].get("has_life_insurance") is True:
            ok("Override pinned has_life_insurance=True")
        else:
            fail("Override did not apply")
    elif r.status_code == 200:
        ok("Override endpoint responded (flag already true)")
    else:
        fail(f"Override failed: {r.status_code}")

    section("3. Smart Recommendations (hybrid)")
    r = client.post(f"{REC_URL}/api/v1/hybrid", json={"profile_id": pid, "top_k": 5})
    if r.status_code != 200:
        fail(f"Hybrid query failed: {r.status_code} {r.text[:400]}")
        return 1
    hybrid = r.json()
    items = hybrid.get("items") or []
    if not items:
        fail("Hybrid returned zero recommendations")
        return 1
    ok(f"Hybrid returned {len(items)} strategies")
    for item in items[:3]:
        print(
            f"    #{item['rank']} {item['name']} — "
            f"adoption {item['adoption_probability']*100:.0f}%, "
            f"savings LKR {float(item.get('estimated_annual_savings', 0)):,.0f}"
        )

    section("4. Financial Impact — per strategy (2-year Monte Carlo)")
    impact_ok = 0
    for item in items:
        code = item["strategy_id"]
        r = client.post(
            f"{REC_URL}/api/v1/impact/simulate",
            json={
                "profile_id": pid,
                "strategy_code": code,
                "horizon_years": 2,
                "n_paths": 200,
                "random_seed": 42,
            },
        )
        if r.status_code != 200:
            fail(f"Impact simulate failed for {code}: {r.status_code}")
            continue
        body = r.json()
        if len(body.get("baseline", [])) != 2:
            fail(f"{code}: expected 2 baseline years, got {len(body.get('baseline', []))}")
            continue
        if body.get("strategy_path") is None:
            fail(f"{code}: missing strategy_path")
            continue
        impact_ok += 1
    if impact_ok == len(items):
        ok(f"All {len(items)} strategies have 2-year impact projections")
    elif impact_ok > 0:
        warn(f"{impact_ok}/{len(items)} strategies have impact projections")
    else:
        fail("No strategy impact simulations succeeded")

    section("5. OE Engine tax context (optional)")
    if oe_engine_up:
        warn("Live OE calculate requires interview session payload — verify in UI Features tab")
    else:
        warn("Start OE Engine on :8009 to test live taxable income / reliefs in Features tab")

    section("Cleanup")
    client.delete(f"{REC_URL}/api/v1/profiles/{pid}")
    ok(f"Deleted test profile {pid}")

    print(f"\n{'='*50}")
    print(f"PASS: {PASS}  WARN: {WARN}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
