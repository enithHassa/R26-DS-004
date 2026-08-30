"""Predictive impact simulation (Phase 5).

Monte Carlo projection of long-term financial outcomes for adopted strategies.
Produces mean + confidence bands consumed by the dashboard's impact simulator.
"""

from impact.monte_carlo import median_projection, projection_bands, run_monte_carlo
from impact.strategy_effects import build_strategy_snapshot, estimate_first_year_tax_savings
from impact.types import DeductionProfile, ScenarioParams, SimulationSnapshot

__all__ = [
    "DeductionProfile",
    "ScenarioParams",
    "SimulationSnapshot",
    "build_strategy_snapshot",
    "estimate_first_year_tax_savings",
    "median_projection",
    "projection_bands",
    "run_monte_carlo",
]
