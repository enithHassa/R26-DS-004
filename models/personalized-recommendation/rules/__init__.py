"""Tax rules engine (Phase 1).

The YAML pack in :file:`sl_tax_2024_25.yaml` is the single source of truth for
tax-free thresholds, APIT slabs, and deduction caps. The engine here loads the
pack and exposes pure functions used by both the synthetic data generator
(Phase 1) and the strategy generator (Phase 3).
"""

from .engine import TaxRules, apply_deductions, compute_annual_tax, load_tax_rules

__all__ = ["TaxRules", "apply_deductions", "compute_annual_tax", "load_tax_rules"]
