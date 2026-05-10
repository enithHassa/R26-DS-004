"""Ranking layer (Phase 4 / WP6).

- ``fusion`` — multi-objective score fusion
- ``relevance`` — graded relevance labels for LambdaMART training
- ``scoring_weights.yaml`` — default fusion weights (copy into artifact dir)
"""

from .fusion import FusionWeights, fuse_scores, min_max_norm
from .relevance import relevance_from_evaluation

__all__ = [
    "FusionWeights",
    "fuse_scores",
    "min_max_norm",
    "relevance_from_evaluation",
]
