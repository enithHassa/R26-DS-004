"""Tax return Excel export builds expected sheets."""

from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from oe_engine_app.schemas.tax_return_export import (
    IncomeBreakdown,
    InterestLine,
    PensionLine,
    PensionSchedule,
    TaxableIncomeSummary,
    TaxableSummaryLine,
    TaxpayerHeader,
    TaxReturnExportRequest,
)
from oe_engine_app.services.tax_return_export import build_tax_return_workbook


def test_build_tax_return_workbook_sheets() -> None:
    body = TaxReturnExportRequest(
        header=TaxpayerHeader(
            full_name="MR TEST TAXPAYER",
            tin="123456789",
            assessment_year_label="2025/2026",
            reference_code="REF001",
        ),
        income_breakdown=IncomeBreakdown(
            employment=1_000_000,
            interest=500_000,
            business=0,
            rents=0,
            other=0,
            investment=500_000,
        ),
        calculate_result={
            "assessment_year": "2025_26",
            "gross_income": 1_500_000,
            "employment_income": 1_000_000,
            "business_income": 0,
            "investment_income": 500_000,
            "other_income": 0,
            "total_reliefs": 1_200_000,
            "taxable_income": 300_000,
            "tax_payable": 18_000,
            "wht_credit": 25_000,
            "wht_already_paid": 25_000,
            "apit_credit": 0,
            "balance_payable": 0,
            "tax_refund": 7_000,
            "relief_lines": [
                {
                    "compare_group_id": "personal_relief",
                    "display_name": "Personal relief",
                    "applied": 1_200_000,
                }
            ],
            "slab_lines": [
                {
                    "band_index": 0,
                    "band_label": "First 500,000",
                    "slice": 300_000,
                    "rate_percent": 6,
                    "tax": 18_000,
                }
            ],
        },
        interest_lines=[
            InterestLine(
                bank="People's Bank",
                source_type="FD INTEREST",
                type="FD",
                date="2025/03/31",
                account_or_fd_no="FD-001",
                fd_amount=1_000_000,
                gross_interest=450_000,
                wht=22_500,
            ),
            InterestLine(
                bank="Savings interest",
                source_type="SAVINGS INTEREST",
                type="SAVINGS",
                gross_interest=50_000,
                wht=2_500,
            ),
        ],
        pension=PensionSchedule(
            pensioner_name="MR TEST TAXPAYER",
            status_note="Annual total from tax return profile",
            lines=[
                PensionLine(pen_date="YA total", tpen=120_000, pnet=120_000),
            ],
        ),
        taxable_summary=TaxableIncomeSummary(
            total_taxable_lkr=1_250_000,
            covered_month_count=10,
            missing_month_count=2,
            lines=[
                TaxableSummaryLine(
                    class_key="interest_income",
                    calendar_month="2025-04",
                    taxable_amount_lkr=40_000,
                    transaction_count=3,
                )
            ],
        ),
    )

    raw = build_tax_return_workbook(body)
    assert raw[:2] == b"PK"  # zip/xlsx magic

    wb = load_workbook(BytesIO(raw))
    assert wb.sheetnames == [
        "TAX CALCULATION",
        "SAVINGS",
        "FD",
        "UPLOAD FILE",
        "Pension Sche.",
        "TX TAXABLE SUMMARY",
    ]
    calc = wb["TAX CALCULATION"]
    assert calc["B2"].value == "MR TEST TAXPAYER"
    assert calc["C3"].value == "123456789"
    assert "2025/2026" in str(calc["B4"].value)

    savings = wb["SAVINGS"]
    assert savings["A3"].value == "Savings interest"
    assert float(savings["G3"].value) == 50_000

    fd = wb["FD"]
    assert fd["A3"].value == "People's Bank"
    assert float(fd["G3"].value) == 450_000

    upload = wb["UPLOAD FILE"]
    assert upload["F3"].value in {"FD", "SAVINGS"}
