"""Offline evaluation (Phase 6).

Ranking metrics (NDCG@k, MAP, MRR), ablation studies isolating the rules /
classifier / ranker / fusion contributions, fairness checks across
occupation and income deciles, and SHAP explainability for LambdaMART pairs.
"""

from evaluation.ablation import (
    AblationConfig,
    evaluate_frozen_adoption,
    evaluate_frozen_ranker,
    run_ablation_study,
)
from evaluation.dataset import build_eval_dataset, row_to_eval_context, row_to_user_dict
from evaluation.explainability import PairExplanation, explain_pair_ranking
from evaluation.fairness import FairnessReport, fairness_reports_for_eval
from evaluation.metrics import adoption_metrics, group_by_query, ranking_metrics
from evaluation.report import EvaluationReport, ModelScoreRow
from evaluation.runner import run_offline_evaluation

__all__ = [
    "AblationConfig",
    "EvaluationReport",
    "FairnessReport",
    "ModelScoreRow",
    "PairExplanation",
    "adoption_metrics",
    "build_eval_dataset",
    "evaluate_frozen_adoption",
    "evaluate_frozen_ranker",
    "explain_pair_ranking",
    "fairness_reports_for_eval",
    "group_by_query",
    "ranking_metrics",
    "row_to_eval_context",
    "row_to_user_dict",
    "run_ablation_study",
    "run_offline_evaluation",
]
