"""Phase 2 RAG seed — years and reliefs from approved catalogs."""

from __future__ import annotations


def _personal(entries: list[dict]) -> dict:
    matches = [e for e in entries if e.get("compare_group_id") == "personal_relief"]
    assert matches, "personal_relief missing from indexed year"
    return matches[0]


def test_refresh_excludes_2026_27_when_not_in_catalog(client) -> None:
    refresh = client.post("/api/v1/index/refresh")
    assert refresh.status_code == 200
    payload = refresh.json()
    years = payload["years"]
    assert "2018_19" in years
    assert "2025_26" in years
    assert "2026_27" not in years

    listed = client.get("/api/v1/years")
    assert listed.status_code == 200
    body = listed.json()
    assert "2026_27" not in body["assessment_years"]
    assert body["year_count"] == len(body["assessment_years"])


def test_phase6_watcher_new_year_indexed_when_not_synthetic(tmp_path) -> None:
    from opt_explain_app.config import OptimizationExplainableSettings
    from opt_explain_app.services import rag_index

    approved = tmp_path / "approved"
    rates = tmp_path / "rates"
    index = tmp_path / "index"
    approved.mkdir()
    rates.mkdir()
    (approved / "2026_27.json").write_text(
        __import__("json").dumps(
            {
                "assessment_year": "2026_27",
                "promotion_source": "phase6_watcher",
                "watcher_source_doc_id": "ird-amend-2026-99-a14a4e3c",
                "phase1_empty_skeleton": False,
                "entries": [
                    {
                        "entry_id": "personal-2026",
                        "compare_group_id": "personal_relief",
                        "display_name": "Personal relief",
                        "question_prompt": "Personal relief is applied automatically.",
                        "input_kind": "notice",
                        "auto_applied": True,
                        "cap_amount": "2000000",
                        "unit": "lkr",
                        "engine_binding": {"kind": "none"},
                        "act_name": "Act No. 99 of 2026",
                        "section_ref": "Fifth Schedule",
                        "quote": "Rs. 2,000,000",
                        "source_doc_id": "ird-amend-2026-99-a14a4e3c",
                        "sort_order": 10,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = OptimizationExplainableSettings(
        COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR=str(approved),
        COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR=str(rates),
        COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR=str(index),
    )
    try:
        result = rag_index.refresh_index(cfg)
        assert "2026_27" in result["years"]
        docs = rag_index.reliefs_for_year("2026_27")
        assert docs is not None and docs
        assert docs[0]["cap_amount"] == "2000000"
    finally:
        rag_index.refresh_index()


def test_synthetic_watcher_2026_27_excluded_from_index(tmp_path) -> None:
    from opt_explain_app.config import OptimizationExplainableSettings
    from opt_explain_app.services import rag_index

    approved = tmp_path / "approved"
    rates = tmp_path / "rates"
    index = tmp_path / "index"
    approved.mkdir()
    rates.mkdir()
    (approved / "2026_27.json").write_text(
        __import__("json").dumps(
            {
                "assessment_year": "2026_27",
                "promotion_source": "phase6_watcher",
                "notes": "SYNTHETIC FIXTURE for watcher demo",
                "watcher_source_doc_id": "ird-amend-watcher-demo-2026",
                "entries": [
                    {
                        "entry_id": "watcher-only",
                        "compare_group_id": "personal_relief",
                        "display_name": "Personal relief",
                        "question_prompt": "Synthetic",
                        "input_kind": "notice",
                        "auto_applied": True,
                        "cap_amount": "2000000",
                        "unit": "lkr",
                        "engine_binding": {"kind": "none"},
                        "act_name": "SYNTHETIC FIXTURE",
                        "section_ref": "Fifth Schedule",
                        "quote": "Rs. 2,000,000",
                        "source_doc_id": "ird-amend-watcher-demo-2026",
                        "sort_order": 10,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = OptimizationExplainableSettings(
        COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR=str(approved),
        COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR=str(rates),
        COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR=str(index),
    )
    try:
        result = rag_index.refresh_index(cfg)
        assert "2026_27" not in result["years"]
        assert rag_index.reliefs_for_year("2026_27") is None
    finally:
        rag_index.refresh_index()


def test_catalog_admin_promoted_2026_27_indexed_from_fixture(tmp_path) -> None:
    from opt_explain_app.config import OptimizationExplainableSettings
    from opt_explain_app.services import rag_index

    approved = tmp_path / "approved"
    rates = tmp_path / "rates"
    index = tmp_path / "index"
    approved.mkdir()
    rates.mkdir()
    (approved / "2026_27.json").write_text(
        __import__("json").dumps(
            {
                "assessment_year": "2026_27",
                "promotion_source": "catalog_admin_update",
                "watcher_source_doc_id": "ird-amend-2026-99",
                "entries": [
                    {
                        "entry_id": "digital-demo",
                        "compare_group_id": "digital_productivity_equipment_relief",
                        "display_name": "Digital Productivity Equipment Relief",
                        "question_prompt": "Qualifying digital equipment?",
                        "input_kind": "yes_no_amount",
                        "auto_applied": False,
                        "cap_amount": "300000",
                        "unit": "lkr",
                        "engine_binding": {"kind": "none"},
                        "act_name": "Act No. 99 of 2026",
                        "section_ref": "Fifth Schedule",
                        "quote": "Rs. 300,000",
                        "source_doc_id": "ird-amend-2026-99",
                        "sort_order": 100,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = OptimizationExplainableSettings(
        COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR=str(approved),
        COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR=str(rates),
        COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR=str(index),
    )
    try:
        result = rag_index.refresh_index(cfg)
        assert "2026_27" in result["years"]
        docs = rag_index.reliefs_for_year("2026_27")
        assert docs is not None
        digital = next(d for d in docs if d["compare_group_id"] == "digital_productivity_equipment_relief")
        assert digital["cap_amount"] == "300000"
        assert digital["source_doc_id"] == "ird-amend-2026-99"
    finally:
        rag_index.refresh_index()


def test_personal_relief_2025_26_checkpoint(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/reliefs/2025_26")
    assert response.status_code == 200
    personal = _personal(response.json()["entries"])
    assert personal["cap_amount"] == "1800000"
    assert personal["source_doc_id"] == "ird-amend-2025-02"
    assert personal["assessment_year"] == "2025_26"
    assert personal["question_prompt"]
    assert personal["input_kind"]
    assert personal["quote"]


def test_personal_relief_2018_19_checkpoint(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/reliefs/2018_19")
    assert response.status_code == 200
    personal = _personal(response.json()["entries"])
    assert personal["cap_amount"] == "500000"
    assert personal["source_doc_id"]


def test_unknown_year_404(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/reliefs/1999_00")
    assert response.status_code == 404


def test_year_change_loads_different_caps(client) -> None:
    """Checkpoint: different years expose different reliefs/caps from the index."""
    client.post("/api/v1/index/refresh")
    y2018 = client.get("/api/v1/reliefs/2018_19").json()
    y2025 = client.get("/api/v1/reliefs/2025_26").json()
    assert y2018["entry_count"] != y2025["entry_count"]
    p2018 = _personal(y2018["entries"])["cap_amount"]
    p2025 = _personal(y2025["entries"])["cap_amount"]
    assert p2018 == "500000"
    assert p2025 == "1800000"
    assert p2018 != p2025
    groups_2018 = {e["compare_group_id"] for e in y2018["entries"]}
    groups_2025 = {e["compare_group_id"] for e in y2025["entries"]}
    assert groups_2018 != groups_2025


def test_rates_indexed_for_2025_26(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/rates/2025_26")
    assert response.status_code == 200
    body = response.json()
    assert body["band_count"] >= 1
    assert body["bands"][0]["source_doc_id"]
    assert body["bands"][0]["assessment_year"] == "2025_26"


def test_acts_for_2025_26_lists_amendment_02(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/acts/2025_26")
    assert response.status_code == 200
    body = response.json()
    by_id = {row["source_doc_id"]: row for row in body["acts"]}
    assert "ird-amend-2025-02" in by_id
    act = by_id["ird-amend-2025-02"]
    assert act["relief_count"] >= 1
    assert "02 of 2025" in act["title"]
    assert body["act_count"] == len(body["acts"])


def test_reliefs_exclude_falls_back_to_prior_personal_cap(client) -> None:
    """Drop Act 02 of 2025 → remaining personal_relief is the prior 1.2M row."""
    client.post("/api/v1/index/refresh")
    included = client.get("/api/v1/reliefs/2025_26").json()
    assert _personal(included["entries"])["cap_amount"] == "1800000"
    excluded = client.get(
        "/api/v1/reliefs/2025_26",
        params={"exclude_source_doc_id": "ird-amend-2025-02"},
    )
    assert excluded.status_code == 200
    personal = _personal(excluded.json()["entries"])
    assert personal["cap_amount"] == "1200000"
    assert personal["source_doc_id"] == "ird-amend-2022-45"
    restored = client.get("/api/v1/reliefs/2025_26").json()
    assert _personal(restored["entries"])["cap_amount"] == "1800000"


def test_refresh_indexes_help_and_question_prompt(client) -> None:
    client.post("/api/v1/index/refresh")
    personal = _personal(client.get("/api/v1/reliefs/2025_26").json()["entries"])
    assert personal["question_prompt"]
    assert "help" in personal


def test_unpublished_approved_file_is_the_only_index_source(tmp_path) -> None:
    """Rejected/proposed rows never index: the RAG store only reads approved/*.json."""
    from opt_explain_app.config import OptimizationExplainableSettings
    from opt_explain_app.services import rag_index

    approved = tmp_path / "approved"
    rates = tmp_path / "rates"
    index = tmp_path / "index"
    approved.mkdir()
    rates.mkdir()
    (approved / "2025_26.json").write_text(
        __import__("json").dumps(
            {
                "assessment_year": "2025_26",
                "entries": [
                    {
                        "entry_id": "accepted-only",
                        "compare_group_id": "personal_relief",
                        "display_name": "Personal relief",
                        "question_prompt": "Shown after auditor accept.",
                        "help": "Accepted help.",
                        "input_kind": "notice",
                        "auto_applied": True,
                        "cap_amount": "1800000",
                        "unit": "lkr",
                        "engine_binding": {"kind": "none"},
                        "act_name": "Test Act",
                        "section_ref": "Fifth Schedule",
                        "quote": "Rs. 1,800,000",
                        "source_doc_id": "ird-amend-2025-02",
                        "sort_order": 10,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    proposed = tmp_path / "proposed"
    proposed.mkdir()
    (proposed / "secret.json").write_text(
        __import__("json").dumps(
            {
                "rows": [
                    {
                        "entry_id": "rejected-never",
                        "compare_group_id": "unpublished_solar_bonus",
                        "question_prompt": "Should this unpublished relief appear?",
                        "cap_amount": "250000",
                        "included": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = OptimizationExplainableSettings(
        COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR=str(approved),
        COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR=str(rates),
        COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR=str(index),
    )
    try:
        rag_index.refresh_index(cfg)
        docs = rag_index.reliefs_for_year("2025_26")
        assert docs is not None
        ids = {d["entry_id"] for d in docs}
        groups = {d["compare_group_id"] for d in docs}
        assert "accepted-only" in ids
        assert "rejected-never" not in ids
        assert "unpublished_solar_bonus" not in groups
        prompts = {d["question_prompt"] for d in docs}
        assert "Should this unpublished relief appear?" not in prompts
        assert docs[0]["help"] == "Accepted help."
    finally:
        rag_index.refresh_index()

