"""Synthetic dataset generation and loaders (Phase 1).

Modules landing here:

* ``profile_generator.py`` — Sri Lanka demographics-aware synthetic taxpayer
  generator (Phase 1, WP3, profile slice). Other generators (strategy
  catalog, behavioural simulator) land in this package as Phase 1 progresses.
"""

from .profile_generator import (
    PROFILE_COLUMNS,
    GeneratorConfig,
    generate_profiles,
    write_profiles,
)

__all__ = [
    "PROFILE_COLUMNS",
    "GeneratorConfig",
    "generate_profiles",
    "write_profiles",
]
