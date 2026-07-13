"""ML-based strategy ranking service."""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from tax_opt_b_app.tax_opt_b_schemas_ml_rank_v1 import (
    MLRankRequestV1,
    MLRankResponseV1,
    RankedStrategyV1,
)
from tax_opt_b_app.services.tax_opt_b_tax_computation import run_compliance_and_compute_tax


class MLRankingService:
    """Service for ML-based strategy ranking."""

    def __init__(self, ml_strategy_ranker, feature_engineer, legal_rag):
        """Initialize with ML components."""
        self.ml_ranker = ml_strategy_ranker
        self.feature_engineer = feature_engineer
        self.legal_rag = legal_rag

    def rank_strategies(
        self,
        request: MLRankRequestV1,
        rules_pack,
        strategies_grid: List[Dict[str, Any]],
    ) -> MLRankResponseV1:
        """Rank strategies using ML model and legal explanations."""

        # 1. Calculate baseline (no reliefs)
        baseline_tax = self._calculate_tax_for_strategy(
            request=request,
            reliefs={},
            rules_pack=rules_pack,
        )

        # 2. Rank all strategies
        ranked = []
        for strategy in strategies_grid:
            # Get reliefs for this strategy
            reliefs_dict = self._strategy_to_reliefs_dict(request, strategy)

            # Calculate tax
            strategy_tax = self._calculate_tax_for_strategy(
                request=request,
                reliefs=reliefs_dict,
                rules_pack=rules_pack,
            )

            # Engineer features
            try:
                # Add actual relief amounts to strategy for feature engineering
                strategy_with_amounts = dict(strategy)
                strategy_with_amounts['relief_amounts'] = reliefs_dict
                strategy_with_amounts['reliefs_claimed'] = strategy.get('reliefs', [])

                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[DEBUG] Strategy: {strategy.get('name')}, Reliefs: {strategy.get('reliefs', [])}, Amounts: {reliefs_dict}, Tax: {strategy_tax}")

                features = self.feature_engineer.engineer_features(
                    persona={
                        'salary': request.salary,
                        'rental_income': request.rental_income,
                        'interest_income': request.interest_income,
                        'business_income': request.business_income,
                        'complexity_tolerance': request.complexity_tolerance,
                        'audit_risk_tolerance': request.audit_risk_tolerance,
                        'time_available': request.time_available,
                    },
                    strategy=strategy_with_amounts,
                    tax_outcome={
                        'tax_liability': strategy_tax,
                        'effective_rate': strategy_tax / (request.salary + request.rental_income + request.interest_income + request.business_income + 1),
                    },
                )

                # Log key feature values
                logger.info(f"[DEBUG] Features - total_relief_claimed: {features.get('total_relief_claimed')}, num_reliefs: {features.get('num_reliefs_claimed')}")
            except Exception as e:
                # Fallback: skip if feature engineering fails
                continue

            # Get ML score
            utility_score = self.ml_ranker.predict_utility_score(
                features_dict=features,
                tax_year=request.tax_year,
            )

            # Get legal explanation
            legal_explanation = self.legal_rag.get_explanation_for_strategy(
                reliefs=strategy.get('reliefs', []),
                tax_year=request.tax_year,
                income_profile={
                    'salary': request.salary,
                    'rental': request.rental_income,
                    'interest': request.interest_income,
                    'business': request.business_income,
                },
            )

            ranked.append({
                'strategy': strategy,
                'utility_score': utility_score,
                'tax_liability': strategy_tax,
                'tax_savings': baseline_tax - strategy_tax,
                'legal_summary': legal_explanation.get('summary', ''),
                'compliance_status': 'COMPLIANT',  # Placeholder
                'audit_risk_level': self._get_audit_risk_level(
                    legal_explanation.get('audit_risk', 0),
                ),
            })

        # 3. Sort by utility score (descending)
        ranked.sort(key=lambda x: x['utility_score'], reverse=True)

        # 4. Build response with top 10
        gross_income = (
            request.salary + request.rental_income +
            request.interest_income + request.business_income
        )

        ranked_strategies_response = []
        for rank, item in enumerate(ranked[:10], 1):
            strategy = item['strategy']
            ranked_strategies_response.append(
                RankedStrategyV1(
                    strategy_id=strategy.get('id', rank),
                    strategy_name=strategy.get('name', f'Strategy {rank}'),
                    reliefs_claimed=strategy.get('reliefs', []),
                    num_reliefs=len(strategy.get('reliefs', [])),
                    utility_score=item['utility_score'],
                    rank=rank,
                    estimated_tax_liability=item['tax_liability'],
                    estimated_tax_savings=item['tax_savings'],
                    compliance_status=item['compliance_status'],
                    audit_risk_level=item['audit_risk_level'],
                    legal_summary=item['legal_summary'],
                )
            )

        # 5. Build response
        return MLRankResponseV1(
            tax_year=request.tax_year,
            gross_income=gross_income,
            taxable_basis=gross_income,  # Simplified; use actual calculation
            baseline_tax_liability=baseline_tax,
            ranked_strategies=ranked_strategies_response,
            best_strategy_index=0,  # Index 0 is the best (sorted by utility score)
            personalization_note=self._build_personalization_note(request),
            timestamp=datetime.utcnow().isoformat(),
        )

    def _strategy_to_reliefs_dict(
        self, request: MLRankRequestV1, strategy: Dict
    ) -> Dict[str, float]:
        """Convert strategy to reliefs dictionary."""
        mapping = {
            'life_insurance_premium': request.life_insurance_premium,
            'health_insurance_premium': request.health_insurance_premium,
            'home_loan_interest': request.home_loan_interest,
            'rent_relief': request.rent_relief,
            'charitable_donations': request.charitable_donations,
            'retirement_contribution': request.retirement_contribution,
        }

        reliefs = {}
        for relief_code in strategy.get('reliefs', []):
            if relief_code in mapping:
                reliefs[relief_code] = mapping[relief_code]

        return reliefs

    def _calculate_tax_for_strategy(
        self,
        request: MLRankRequestV1,
        reliefs: Dict[str, float],
        rules_pack,
    ) -> float:
        """Calculate tax for a strategy (simplified)."""
        # Calculate taxable basis
        gross_income = (
            request.salary + request.rental_income +
            request.interest_income + request.business_income
        )

        # Subtract reliefs
        total_reliefs = sum(reliefs.values())
        taxable_basis = max(0, gross_income - total_reliefs)

        # Apply tax brackets (simplified Sri Lankan brackets)
        if taxable_basis <= 1_800_000:
            return 0
        elif taxable_basis <= 3_500_000:
            return (taxable_basis - 1_800_000) * 0.12
        elif taxable_basis <= 5_500_000:
            return (
                (3_500_000 - 1_800_000) * 0.12 +
                (taxable_basis - 3_500_000) * 0.18
            )
        else:
            return (
                (3_500_000 - 1_800_000) * 0.12 +
                (5_500_000 - 3_500_000) * 0.18 +
                (taxable_basis - 5_500_000) * 0.24
            )

    def _get_audit_risk_level(self, audit_risk_score: float) -> str:
        """Convert audit risk score to level."""
        if audit_risk_score < 0.33:
            return "LOW"
        elif audit_risk_score < 0.67:
            return "MEDIUM"
        else:
            return "HIGH"

    def _build_personalization_note(self, request: MLRankRequestV1) -> str:
        """Build personalization note based on user preferences."""
        notes = []

        if request.complexity_tolerance <= 2:
            notes.append("Prioritizing simpler strategies (low complexity tolerance)")
        elif request.complexity_tolerance >= 4:
            notes.append("Including more complex optimization strategies")

        if request.audit_risk_tolerance <= 2:
            notes.append("Favoring low-risk strategies (conservative approach)")
        elif request.audit_risk_tolerance >= 4:
            notes.append("Open to optimized strategies with higher potential returns")

        return "; ".join(notes) if notes else "Balanced approach to optimization"
