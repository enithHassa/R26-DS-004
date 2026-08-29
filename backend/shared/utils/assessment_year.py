"""Sri Lanka Year of Assessment helpers (1 April – 31 March)."""

from __future__ import annotations

from datetime import date


def ya_bounds_from_orm_tax_year(tax_year: str) -> tuple[date, date]:
    """``2025_26`` → (2025-04-01, 2026-03-31)."""
    cleaned = tax_year.strip()
    if "_" not in cleaned:
        raise ValueError(f"Expected ORM tax_year like 2025_26, got {tax_year!r}")
    start_year = int(cleaned.split("_", 1)[0])
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def ya_calendar_month_starts(tax_year: str) -> list[date]:
    """First day of each calendar month in the YA, April → March."""
    start_year = int(tax_year.strip().split("_", 1)[0])
    return [
        *[date(start_year, month, 1) for month in range(4, 13)],
        *[date(start_year + 1, month, 1) for month in range(1, 4)],
    ]


def month_start(value: date) -> date:
    return value.replace(day=1)


def ya_label_from_orm_tax_year(tax_year: str) -> str:
    """``2025_26`` → ``2025/26``."""
    start_year, end = ya_bounds_from_orm_tax_year(tax_year)
    return f"{start_year.year}/{str(end.year)[-2:]}"


def orm_tax_year_for_date(value: date) -> str:
    """Map a calendar date to its Sri Lanka ORM tax_year (Apr–Mar)."""
    start_year = value.year if value.month >= 4 else value.year - 1
    return f"{start_year}_{str(start_year + 1)[-2:]}"


def ya_contains_date(tax_year: str, value: date) -> bool:
    ya_start, ya_end = ya_bounds_from_orm_tax_year(tax_year)
    return ya_start <= value <= ya_end

