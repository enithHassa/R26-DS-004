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
            "total_reliefs": 2_725_000,
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
                    "applied": 1_800_000,
                },
                {
                    "compare_group_id": "solar_panel_relief",
                    "display_name": "Solar panel relief",
                    "applied": 600_000,
                },
                {
                    "compare_group_id": "donation_to_approved_charity",
                    "display_name": "Donation to approved charitable institution",
                    "applied": 75_000,
                },
                {
                    "compare_group_id": "rental_income_relief",
                    "display_name": "Rental income relief",
                    "applied": 250_000,
                },
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

    # Less- Sec -52 is a section header only — no amount (blank, not dash/total).
    sec52_row = None
    for row in range(1, 40):
        if calc.cell(row=row, column=2).value == "Less- Sec -52":
            sec52_row = row
            break
    assert sec52_row is not None
    assert calc.cell(row=sec52_row, column=6).value in (None, "")

    savings = wb["SAVINGS"]
    assert savings["A3"].value == "Savings interest"
    assert float(savings["G3"].value) == 50_000

    fd = wb["FD"]
    assert fd["A3"].value == "People's Bank"
    assert float(fd["G3"].value) == 450_000

    upload = wb["UPLOAD FILE"]
    assert upload["F3"].value in {"FD", "SAVINGS"}


def test_wht_falls_back_to_interest_lines_when_calculate_omits_credit() -> None:
    """Profile SAVINGS/FD WHT must appear on TAX CALCULATION even if snapshot credit is 0."""
    body = TaxReturnExportRequest(
        header=TaxpayerHeader(
            full_name="MR WHT TAXPAYER",
            tin="567890357",
            assessment_year_label="2025/2026",
        ),
        income_breakdown=IncomeBreakdown(employment=25_000_000, interest=2_310),
        calculate_result={
            "assessment_year": "2025_26",
            "gross_income": 31_940_375,
            "taxable_income": 29_215_375,
            "tax_payable": 10_037_535,
            "wht_credit": 0,
            "wht_already_paid": 0,
            "apit_credit": 768_000,
            "apit_already_paid": 768_000,
            "balance_payable": 9_269_535,
            "tax_refund": 0,
            "relief_lines": [],
            "slab_lines": [],
        },
        interest_lines=[
            InterestLine(
                bank="Savings interest",
                source_type="SAVINGS INTEREST",
                type="SAVINGS",
                gross_interest=2_310,
                wht=115,
            ),
            InterestLine(
                bank="People's Bank",
                source_type="FD INTEREST",
                type="FD",
                gross_interest=450_000,
                wht=22_500,
            ),
        ],
    )

    wb = load_workbook(BytesIO(build_tax_return_workbook(body)))
    calc = wb["TAX CALCULATION"]

    wht_row = None
    for row in range(1, 60):
        if calc.cell(row=row, column=2).value == "WHT":
            wht_row = row
            break
    assert wht_row is not None
    # Cap after APIT: min(22_615, 10_037_535 - 768_000) = 22_615
    assert float(calc.cell(row=wht_row, column=6).value) == -22_615

    bal_row = None
    for row in range(1, 60):
        if calc.cell(row=row, column=2).value == "Balance Tax Payable/(Refund)":
            bal_row = row
            break
    assert bal_row is not None
    assert float(calc.cell(row=bal_row, column=6).value) == 10_037_535 - 768_000 - 22_615
