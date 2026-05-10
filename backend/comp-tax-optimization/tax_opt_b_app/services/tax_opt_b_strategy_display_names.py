"""Human-readable strategy names for Strategy Explorer (deterministic; no LLM).

Maps relief_code subsets to dissertation-friendly display names using YAML
``relief_display_names`` from :class:`TaxOptBRulePack` with a small code fallback.
"""

from __future__ import annotations

from collections.abc import Mapping

# Used when YAML omits a relief_display_names entry.
_FALLBACK_RELIEF_LABELS: dict[str, str] = {
    "life_insurance_premium": "Life insurance premium",
    "health_insurance_premium": "Health insurance premium",
    "home_loan_interest": "Home loan interest",
    "rent_relief": "Rent relief",
    "charitable_donations": "Charitable donations",
    "retirement_contribution": "Retirement contribution",
}


def _merged_labels(yaml_labels: Mapping[str, str] | None) -> dict[str, str]:
    out = dict(_FALLBACK_RELIEF_LABELS)
    if yaml_labels:
        out.update(dict(yaml_labels))
    return out


def relief_label(relief_code: str, yaml_labels: Mapping[str, str] | None) -> str:
    m = _merged_labels(yaml_labels)
    return m.get(relief_code.strip(), relief_code.replace("_", " ").title())


def display_name_for_subset(
    included_codes: tuple[str, ...],
    grid_reliefs: tuple[str, ...],
    yaml_labels: Mapping[str, str] | None,
    *,
    max_join: int = 3,
) -> str:
    """Build a short user-facing name from enabled reliefs at max-cap grid point."""
    inc = tuple(c.strip() for c in included_codes if c and str(c).strip())
    grid = tuple(c.strip() for c in grid_reliefs if c and str(c).strip())
    labels = _merged_labels(yaml_labels)

    if not inc:
        return "Baseline (no statutory claims)"
    if grid and frozenset(inc) == frozenset(grid):
        return "Maximum statutory relief combination"

    human = [relief_label(c, labels) for c in sorted(inc)]
    if len(human) <= max_join:
        return " + ".join(human) + " optimization"
    return f"Multi-relief strategy ({len(human)} reliefs)"


__all__ = ["display_name_for_subset", "relief_label"]
