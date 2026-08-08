"""HTTP tests for analyze, catalog, and taxable-income summary endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_list_documents_returns_paginated_payload(client) -> None:
    response = client.get("/v1/documents", params={"limit": 10, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert isinstance(body["total"], int)


def test_rename_document_missing_returns_404(client) -> None:
    response = client.patch(
        "/v1/documents/00000000-0000-0000-0000-000000000099",
        json={"filename": "renamed-statement.pdf"},
    )
    assert response.status_code == 404


def test_income_type_catalog_groups_taxability(client) -> None:
    response = client.get("/v1/taxonomy/income-types")
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert "taxable" in body["by_taxability_status"]
    assert any(item["class_key"] == "interest_income" for item in body["items"])


def test_apply_class_batch_reruns_rules(client) -> None:
    response = client.post(
        "/v1/transactions/apply-class-batch",
        json={
            "bank_code": "BOC",
            "document_type": "bank_statement",
            "items": [
                {
                    "row_id": "row-1",
                    "raw_desc": "FD interest credit",
                    "amount_lkr": "1500.00",
                    "tx_date": "2025-01-15",
                    "direction": "CR",
                    "class_key": "interest_income",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["result"]["semantic_category"] == "interest_income"
    assert body["results"][0]["result"]["class_source"] == "manual"
    assert body["results"][0]["result"]["narrative_interpretation"]


def test_analyze_transactions_batch_returns_aligned_results(client) -> None:
    response = client.post(
        "/v1/transactions/analyze-batch",
        json={
            "bank_code": "BOC",
            "document_type": "bank_statement",
            "persist": False,
            "items": [
                {
                    "row_id": "row-1",
                    "raw_desc": "FD interest credit",
                    "amount_lkr": "1500.00",
                    "tx_date": "2025-01-15",
                    "direction": "CR",
                },
                {
                    "row_id": "row-2",
                    "raw_desc": "ATM withdrawal",
                    "amount_lkr": "5000.00",
                    "tx_date": "2025-01-16",
                    "direction": "DR",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processed_count"] == 2
    assert len(body["results"]) == 2
    assert body["results"][0]["row_id"] == "row-1"
    assert body["results"][0]["result"]["tax_rule_code"]
    assert body["results"][1]["row_id"] == "row-2"


def test_analyze_transaction_applies_rules(client) -> None:
    response = client.post(
        "/v1/transactions/analyze",
        json={
            "raw_desc": "FD interest credit",
            "amount_lkr": "1500.00",
            "tx_date": "2025-01-15",
            "direction": "CR",
            "bank_code": "BOC",
            "persist": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_rule_code"]
    assert body["taxability"]["taxability_status"] in {
        "taxable",
        "exempt",
        "partially_taxable",
        "unknown",
    }
    assert body["rule_reference"]
    assert body["explanation"]


def test_taxable_income_summary_empty_window(client) -> None:
    response = client.post(
        "/v1/taxable-income/summary",
        json={
            "date_from": "2099-01-01",
            "date_to": "2099-12-31",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_count"] == 0
    assert Decimal(body["total_taxable_lkr"]) == Decimal("0.00")
