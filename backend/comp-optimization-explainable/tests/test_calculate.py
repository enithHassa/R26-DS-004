"""Phase 4 — calculate from RAG caps and slabs."""

from __future__ import annotations


TYPICAL_INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
}


def _personal(lines: list[dict]) -> dict:
    matches = [e for e in lines if e.get("compare_group_id") == "personal_relief"]
    assert matches, "personal_relief missing from calculate result"
    return matches[0]


def test_calculate_2025_26_uses_personal_1_8m(client) -> None:
    """Checkpoint: typical YA 2025/26 income uses personal 1.8M, not 1.2M."""
    client.post("/api/v1/index/refresh")
    response = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    assert response.status_code == 200
    body = response.json()
    personal = _personal(body["relief_lines"])
    assert personal["applied"] == 1_800_000
    assert personal["cap"] == 1_800_000
    assert personal["source_doc_id"] == "ird-amend-2025-02"
    assert personal["binder"] == "auto_cap"
    assert personal["quote"]
    assert 1_200_000 not in {personal["applied"], personal["cap"]}

    groups = {e["compare_group_id"] for e in body["relief_lines"]}
    assert "employment_income_relief" not in groups
    assert body["gross_income"] == 3_800_000
    assert body["taxable_income"] == 2_000_000
    # 1,000,000 @ 6% + 500,000 @ 18% + 500,000 @ 24% from RAG 2025/26 First Schedule.
    assert body["tax_payable"] == 270_000
    assert body["slab_lines"][0]["rate_percent"] == 6.0
    assert body["slab_lines"][0]["source_doc_id"] == "ird-amend-2025-02"


def test_calculate_1_2m_personal_would_change_tax(client) -> None:
    """Same income with a 1.2M cap would not match the 2025/26 tax figure."""
    client.post("/api/v1/index/refresh")
    response = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    actual = response.json()["tax_payable"]
    # Counterfactual: 3,800,000 − 1,200,000 = 2,600,000 taxable (no employment relief post-2019/20).
    assert actual != 246_000
    assert actual == 270_000


def test_calculate_uses_year_slabs_not_2018_table(client) -> None:
    client.post("/api/v1/index/refresh")
    y2025 = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    ).json()
    y2018 = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2018_19", "income": TYPICAL_INCOME, "claims": []},
    ).json()
    assert y2018["relief_lines"]
    personal_2018 = _personal(y2018["relief_lines"])
    assert personal_2018["applied"] == 500_000
    assert y2025["tax_payable"] != y2018["tax_payable"]
    assert y2018["slab_lines"][0]["rate_percent"] == 4.0


def test_calculate_min_claim_cap_solar(client) -> None:
    client.post("/api/v1/index/refresh")
    listed = client.get("/api/v1/reliefs/2025_26").json()["entries"]
    solar = next(e for e in listed if e["compare_group_id"] == "solar_panel_relief")
    response = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2025_26",
            "income": TYPICAL_INCOME,
            "claims": [
                {
                    "entry_id": solar["entry_id"],
                    "amount": 900_000,
                    "affirmed": True,
                    "skipped": False,
                }
            ],
        },
    )
    assert response.status_code == 200
    line = next(
        e
        for e in response.json()["relief_lines"]
        if e["compare_group_id"] == "solar_panel_relief"
    )
    assert line["binder"] == "min(claim, cap)"
    assert line["applied"] == 600_000
    assert line["engine_binding_kind"] == "solar_panel_relief"


def test_calculate_percent_of_base_rent(client) -> None:
    client.post("/api/v1/index/refresh")
    listed = client.get("/api/v1/reliefs/2025_26").json()["entries"]
    rent = next(e for e in listed if e["compare_group_id"] == "rental_income_relief")
    income = {**TYPICAL_INCOME, "rents": 400_000, "investment": 2_400_000}
    response = client.post(
        "/api/v1/calculate",
        json={
            "assessment_year": "2025_26",
            "income": income,
            "claims": [
                {
                    "entry_id": rent["entry_id"],
                    "amount": 0,
                    "affirmed": True,
                    "skipped": False,
                }
            ],
        },
    )
    assert response.status_code == 200
    line = next(
        e
        for e in response.json()["relief_lines"]
        if e["compare_group_id"] == "rental_income_relief"
    )
    assert line["binder"] == "percent_of_base"
    assert line["applied"] == 100_000
    assert line["engine_binding_kind"] == "rent_relief"
    client.post("/api/v1/index/refresh")
    response = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "1999_00", "income": TYPICAL_INCOME},
    )
    assert response.status_code == 404


def test_calculate_exclude_source_doc_id_falls_back_then_restores(client) -> None:
    """Three-step demo: Act 02 on → 1.8M; exclude → prior cap; re-enable → 1.8M."""
    client.post("/api/v1/index/refresh")
    on_body = {
        "assessment_year": "2025_26",
        "income": TYPICAL_INCOME,
        "claims": [],
    }
    included = client.post("/api/v1/calculate", json=on_body)
    assert included.status_code == 200
    personal_on = _personal(included.json()["relief_lines"])
    assert personal_on["applied"] == 1_800_000
    assert personal_on["cap"] == 1_800_000
    assert personal_on["source_doc_id"] == "ird-amend-2025-02"
    tax_on = included.json()["tax_payable"]
    assert tax_on == 270_000

    dropped = client.post(
        "/api/v1/calculate",
        json={**on_body, "exclude_source_doc_id": "ird-amend-2025-02"},
    )
    assert dropped.status_code == 200
    personal_off = _personal(dropped.json()["relief_lines"])
    assert personal_off["applied"] == 1_200_000
    assert personal_off["cap"] == 1_200_000
    assert personal_off["source_doc_id"] == "ird-amend-2022-45"
    assert dropped.json()["tax_payable"] != tax_on
    assert dropped.json()["slab_lines"]

    restored = client.post("/api/v1/calculate", json=on_body)
    assert restored.status_code == 200
    personal_back = _personal(restored.json()["relief_lines"])
    assert personal_back["applied"] == 1_800_000
    assert restored.json()["tax_payable"] == tax_on
