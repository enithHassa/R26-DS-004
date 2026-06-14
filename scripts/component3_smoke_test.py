#!/usr/bin/env python3
"""Smoke test for Component 3 — Personalized Recommendation & Predictive Impact.

Run from repo root:
  .venv-backend/bin/python scripts/component3_smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "backend" / "comp-personalized-recommendation"
sys.path.insert(0, str(ROOT.resolve()))
sys.path.insert(0, str(COMPONENT.resolve()))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.shared.config.database import Base  # noqa: E402

import app.models  # noqa: F401  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    app = create_app()

    def _db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    print("\n=== Component 3 smoke test ===\n")

    r = client.get("/health")
    check("GET /health", r.status_code == 200)

    profile_payload = {
        "full_name": "Smoke Test",
        "date_of_birth": "1985-03-20",
        "occupation": "employee",
        "gross_monthly_income": "420000",
        "monthly_expenses": "150000",
        "monthly_debt_service": "35000",
        "liquid_savings": "900000",
        "existing_investments": "250000",
        "life_insurance_premium_annual": "55000",
        "health_insurance": True,
        "income_sources": [{"kind": "employment", "monthly_amount": "420000", "is_taxable": True}],
        "tax_year": "2026_27",
    }
    r = client.post("/api/v1/profiles", json=profile_payload)
    check("POST /profiles", r.status_code == 201)
    if r.status_code != 201:
        print("\nAborting: cannot create profile.\n")
        return 1
    profile_id = r.json()["id"]

    r = client.get(f"/api/v1/profiles/{profile_id}/features")
    check(
        "GET /profiles/{id}/features",
        r.status_code == 200,
        f"tax={r.json().get('baseline_tax_liability_annual')}",
    )

    r = client.post("/api/v1/recommendations", json={"profile_id": profile_id, "top_k": 3})
    ok = r.status_code == 200
    detail = ""
    if ok:
        items = r.json().get("items", [])
        detail = f"{len(items)} items, model={r.json().get('model_version')}"
    else:
        detail = r.text[:100]
    check("POST /recommendations", ok, detail)

    r = client.post(
        "/api/v1/impact/simulate",
        json={"profile_id": profile_id, "horizon_years": 5, "n_paths": 200, "random_seed": 7},
    )
    check(
        "POST /impact/simulate (baseline)",
        r.status_code == 200,
        f"years={len(r.json().get('baseline', []))}" if r.status_code == 200 else r.text[:80],
    )

    r = client.post(
        "/api/v1/impact/simulate",
        json={
            "profile_id": profile_id,
            "strategy_code": "S001_health_life_premium_optimisation",
            "horizon_years": 5,
            "n_paths": 200,
            "random_seed": 7,
        },
    )
    ok = r.status_code == 200 and r.json().get("strategy_path")
    s = r.json().get("summary", {}) if r.status_code == 200 else {}
    check(
        "POST /impact/simulate (strategy)",
        ok,
        f"expected_savings={s.get('expected_total_savings')}" if ok else r.text[:80],
    )

    r = client.post(
        "/api/v1/impact/compare",
        json={
            "profile_id": profile_id,
            "strategy_codes": [
                "S001_health_life_premium_optimisation",
                "S002_retirement_contribution_topup",
            ],
            "horizon_years": 4,
        },
    )
    check(
        "POST /impact/compare",
        r.status_code == 200 and len(r.json()) == 2,
        f"{len(r.json())} strategies" if r.status_code == 200 else r.text[:80],
    )

    r = client.post(
        "/api/v1/recommendations/explain",
        json={
            "profile_id": profile_id,
            "strategy_code": "S001_health_life_premium_optimisation",
            "top_k": 3,
        },
    )
    if r.status_code == 503 and "shap" in r.text.lower():
        check("POST /recommendations/explain", True, "skipped — pip install shap")
    else:
        check(
            "POST /recommendations/explain",
            r.status_code == 200 and len(r.json().get("top_reasons", [])) > 0,
            r.text[:80] if r.status_code != 200 else f"{len(r.json()['top_reasons'])} features",
        )

    r = client.post("/api/v1/hybrid", json={"profile_id": profile_id, "top_k": 3})
    ok = r.status_code == 200 and len(r.json().get("items", [])) > 0
    check("POST /hybrid", ok, f"{len(r.json().get('items', []))} items" if ok else r.text[:80])

    r = client.post("/api/v1/rag", json={"profile_id": profile_id, "top_k": 3})
    ok = r.status_code == 200 and len(r.json().get("items", [])) > 0
    check("POST /rag", ok, f"{len(r.json().get('items', []))} items" if ok else r.text[:80])

    r = client.post("/api/v1/strategies/generate", json={"profile_id": profile_id})
    check("POST /strategies/generate (stub 501)", r.status_code == 501)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n=== Summary: {passed} passed, {failed} failed / {len(results)} checks ===\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
