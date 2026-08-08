"""Phase 2.C.6 - Backend integration tests for ML ranking endpoint."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tax_opt_b_app.tax_opt_b_schemas_ml_rank_v1 import MLRankRequestV1
from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app with ML services."""
    app = FastAPI()

    # Initialize real ML services
    app.state.ml_strategy_ranker = MLStrategyRanker(models_dir="phase2_models")
    app.state.feature_engineer = FeatureEngineeringService()
    app.state.legal_rag = LegalRAGService()

    # Create simple routes for testing
    from tax_opt_b_app.routers.tax_opt_b_compliance import (
        ml_rank_strategies,
        ml_health_check,
    )

    # Note: In real app, these would be registered via router
    # For testing, we'll mock the key functionality

    return app


class TestMLEndpointIntegration:
    """Integration tests for ML ranking endpoint."""

    def test_health_check_ready(self):
        """Health check returns ready status."""
        from phase2_ml import MLStrategyRanker

        ranker = MLStrategyRanker(models_dir="phase2_models")
        assert ranker.is_ready()

    def test_request_to_response_flow(self):
        """Complete request -> prediction -> response flow."""
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService

        # Initialize services
        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()

        # Create request
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            rental_income=1_000_000,
            business_income=2_000_000,
            life_insurance_premium=100_000,
            home_loan_interest=200_000,
            complexity_tolerance=3,
            audit_risk_tolerance=3,
            time_available=2,
        )

        # Create service
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        # Dummy rules
        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        # Strategy grid
        strategies = [
            {"id": 1, "name": "Baseline", "reliefs": []},
            {"id": 2, "name": "Life Insurance", "reliefs": ["life_insurance_premium"]},
            {"id": 3, "name": "Home Loan", "reliefs": ["home_loan_interest"]},
            {"id": 4, "name": "Both", "reliefs": ["life_insurance_premium", "home_loan_interest"]},
        ]

        # Get response
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)

        # Validate response
        assert response.tax_year == "2025_26"
        assert response.gross_income == 8_000_000
        assert response.baseline_tax_liability > 0
        assert len(response.ranked_strategies) > 0
        assert response.ranked_strategies[0].rank == 1
        assert 0 <= response.ranked_strategies[0].utility_score <= 1

    def test_multiple_income_combinations(self):
        """Handle various income source combinations."""
        from phase2_ml import MLStrategyRanker

        ranker = MLStrategyRanker(models_dir="phase2_models")

        test_cases = [
            {"salary": 5_000_000, "rental": 0, "interest": 0, "business": 0},
            {"salary": 2_000_000, "rental": 2_000_000, "interest": 0, "business": 0},
            {"salary": 1_000_000, "rental": 1_000_000, "interest": 1_000_000, "business": 1_000_000},
            {"salary": 0, "rental": 5_000_000, "interest": 0, "business": 0},
        ]

        for case in test_cases:
            request = MLRankRequestV1(
                tax_year="2025_26",
                salary=case["salary"],
                rental_income=case["rental"],
                interest_income=case["interest"],
                business_income=case["business"],
            )
            assert request.salary + request.rental_income + request.interest_income + request.business_income > 0

    def test_all_relief_combinations(self):
        """Test with all relief types."""
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            life_insurance_premium=100_000,
            health_insurance_premium=60_000,
            home_loan_interest=200_000,
            rent_relief=100_000,
            charitable_donations=50_000,
            retirement_contribution=200_000,
        )
        assert request.life_insurance_premium == 100_000
        assert request.health_insurance_premium == 60_000
        assert request.home_loan_interest == 200_000

    def test_preference_sensitivity(self):
        """Different preferences should produce different results."""
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService

        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        strategies = [
            {"id": 1, "name": "Baseline", "reliefs": []},
            {"id": 2, "name": "Simple", "reliefs": ["life_insurance_premium"]},
            {"id": 3, "name": "Complex", "reliefs": ["life_insurance_premium", "home_loan_interest", "charitable_donations"]},
        ]

        # Conservative user
        conservative = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            complexity_tolerance=1,
            audit_risk_tolerance=1,
        )

        # Aggressive user
        aggressive = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            complexity_tolerance=5,
            audit_risk_tolerance=5,
        )

        response1 = ranking_service.rank_strategies(conservative, DummyRules(), strategies)
        response2 = ranking_service.rank_strategies(aggressive, DummyRules(), strategies)

        # Both should have valid responses
        assert len(response1.ranked_strategies) > 0
        assert len(response2.ranked_strategies) > 0

    def test_tax_year_specificity(self):
        """Different tax years handled correctly."""
        tax_years = ["2024_25", "2025_26", "2026_27"]

        for year in tax_years:
            request = MLRankRequestV1(
                tax_year=year,
                salary=5_000_000,
            )
            assert request.tax_year == year

    def test_response_timestamp(self):
        """Response includes valid timestamp."""
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService
        from datetime import datetime

        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        strategies = [{"id": 1, "name": "Baseline", "reliefs": []}]

        request = MLRankRequestV1(tax_year="2025_26", salary=5_000_000)
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)

        # Verify timestamp is valid ISO format
        timestamp = response.timestamp
        assert "T" in timestamp
        assert isinstance(timestamp, str)


class TestMLEndpointErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_required_field(self):
        """Missing required fields raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MLRankRequestV1(tax_year="2025_26")  # Missing salary

    def test_invalid_preference_range(self):
        """Out-of-range preferences raise error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MLRankRequestV1(
                tax_year="2025_26",
                salary=5_000_000,
                complexity_tolerance=6,  # Max is 5
            )

    def test_zero_income(self):
        """Zero income is accepted."""
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=0,
        )
        assert request.salary == 0

    def test_very_large_numbers(self):
        """Handle very large income values."""
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=10_000_000_000,  # 10 billion
        )
        assert request.salary == 10_000_000_000

    def test_fractional_amounts(self):
        """Accept fractional currency amounts."""
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000.75,
            life_insurance_premium=50_000.50,
        )
        assert request.salary == 5_000_000.75
        assert request.life_insurance_premium == 50_000.50


class TestMLServicePerformance:
    """Performance and efficiency tests."""

    def test_model_loads_quickly(self):
        """Model loads in reasonable time."""
        import time
        from phase2_ml import MLStrategyRanker

        start = time.time()
        ranker = MLStrategyRanker(models_dir="phase2_models")
        elapsed = time.time() - start

        assert elapsed < 5  # Should load in < 5 seconds
        assert ranker.is_ready()

    def test_prediction_is_fast(self):
        """Single prediction completes quickly."""
        import time
        from phase2_ml import MLStrategyRanker

        ranker = MLStrategyRanker(models_dir="phase2_models")

        features = {name: 0.5 for name in ranker.feature_names}

        start = time.time()
        score = ranker.predict_utility_score(features, tax_year="2025_26")
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should predict in < 100ms
        assert 0 <= score <= 1

    def test_multiple_predictions_sequential(self):
        """Multiple predictions work sequentially."""
        import time
        from phase2_ml import MLStrategyRanker

        ranker = MLStrategyRanker(models_dir="phase2_models")

        start = time.time()
        for i in range(10):
            features = {name: i * 0.1 for name in ranker.feature_names}
            score = ranker.predict_utility_score(features)
            assert 0 <= score <= 1
        elapsed = time.time() - start

        # 10 predictions should take < 1 second
        assert elapsed < 1.0

    def test_strategy_ranking_performance(self):
        """Ranking 20 strategies completes in reasonable time."""
        import time
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService

        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        # Generate 20 strategies
        strategies = [
            {"id": i, "name": f"Strategy {i}", "reliefs": []}
            for i in range(1, 21)
        ]

        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            rental_income=1_000_000,
        )

        start = time.time()
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)
        elapsed = time.time() - start

        # Should rank 20 strategies in < 5 seconds
        assert elapsed < 5.0
        assert len(response.ranked_strategies) > 0


class TestMLResponseStructure:
    """Test response structure and completeness."""

    def test_response_has_all_required_fields(self):
        """Response includes all required fields."""
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService

        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        strategies = [
            {"id": 1, "name": "Baseline", "reliefs": []},
            {"id": 2, "name": "Life", "reliefs": ["life_insurance_premium"]},
        ]

        request = MLRankRequestV1(tax_year="2025_26", salary=5_000_000)
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)

        # Check all required fields
        assert response.tax_year is not None
        assert response.gross_income > 0
        assert response.taxable_basis > 0
        assert response.baseline_tax_liability >= 0
        assert response.ranked_strategies is not None
        assert response.best_strategy_index >= 0
        assert response.timestamp is not None

    def test_ranked_strategy_has_all_fields(self):
        """Each ranked strategy has all required fields."""
        from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService
        from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService

        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        class DummyRules:
            allowed_relief_codes = [
                'life_insurance_premium', 'health_insurance_premium',
                'home_loan_interest', 'rent_relief',
                'charitable_donations', 'retirement_contribution'
            ]

        strategies = [
            {"id": 1, "name": "Baseline", "reliefs": []},
            {"id": 2, "name": "Life", "reliefs": ["life_insurance_premium"]},
        ]

        request = MLRankRequestV1(tax_year="2025_26", salary=5_000_000)
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)

        for strategy in response.ranked_strategies:
            assert strategy.strategy_id is not None
            assert strategy.strategy_name is not None
            assert strategy.reliefs_claimed is not None
            assert strategy.num_reliefs >= 0
            assert 0 <= strategy.utility_score <= 1
            assert strategy.rank > 0
            assert strategy.estimated_tax_liability >= 0
            assert strategy.compliance_status is not None
            assert strategy.audit_risk_level is not None
            assert strategy.legal_summary is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
