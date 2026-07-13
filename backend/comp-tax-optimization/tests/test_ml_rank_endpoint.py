"""Tests for Phase 2.C.3 - ML ranking endpoint."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from tax_opt_b_app.tax_opt_b_schemas_ml_rank_v1 import (
    MLRankRequestV1,
    MLRankResponseV1,
    RankedStrategyV1,
    MLHealthCheckResponseV1,
)
from tax_opt_b_app.services.tax_opt_b_ml_rank_service import MLRankingService
from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService


class TestMLRankRequestValidation:
    """Test request schema validation."""

    def test_valid_minimal_request(self):
        """Minimal request with required fields only."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
        )
        assert req.tax_year == "2025_26"
        assert req.salary == 5_000_000
        assert req.rental_income == 0
        assert req.complexity_tolerance == 3

    def test_valid_full_request(self):
        """Complete request with all fields."""
        req = MLRankRequestV1(
            tax_year="2024_25",
            salary=3_000_000,
            rental_income=1_000_000,
            interest_income=500_000,
            business_income=2_000_000,
            life_insurance_premium=100_000,
            health_insurance_premium=60_000,
            home_loan_interest=200_000,
            rent_relief=100_000,
            charitable_donations=50_000,
            retirement_contribution=200_000,
            complexity_tolerance=5,
            audit_risk_tolerance=4,
            time_available=3,
        )
        assert req.salary == 3_000_000
        assert req.life_insurance_premium == 100_000
        assert req.complexity_tolerance == 5

    def test_custom_tax_year(self):
        """Accept custom tax year formats."""
        req = MLRankRequestV1(tax_year="custom_year", salary=1_000_000)
        assert req.tax_year == "custom_year"

    def test_negative_income(self):
        """Negative income not allowed."""
        with pytest.raises(ValidationError):
            MLRankRequestV1(tax_year="2025_26", salary=-1_000_000)

    def test_negative_relief(self):
        """Negative relief amount not allowed."""
        with pytest.raises(ValidationError):
            MLRankRequestV1(
                tax_year="2025_26",
                salary=1_000_000,
                life_insurance_premium=-50_000,
            )

    def test_invalid_complexity_tolerance(self):
        """Complexity tolerance must be 1-5."""
        with pytest.raises(ValidationError):
            MLRankRequestV1(
                tax_year="2025_26",
                salary=1_000_000,
                complexity_tolerance=6,
            )

    def test_invalid_audit_risk_tolerance(self):
        """Audit risk tolerance must be 1-5."""
        with pytest.raises(ValidationError):
            MLRankRequestV1(
                tax_year="2025_26",
                salary=1_000_000,
                audit_risk_tolerance=0,
            )

    def test_invalid_time_available(self):
        """Time available must be 1-3."""
        with pytest.raises(ValidationError):
            MLRankRequestV1(
                tax_year="2025_26",
                salary=1_000_000,
                time_available=4,
            )


class TestMLRankResponseSchema:
    """Test response schema structure."""

    def test_ranked_strategy_schema(self):
        """Ranked strategy has all required fields."""
        strategy = RankedStrategyV1(
            strategy_id=1,
            strategy_name="Test Strategy",
            reliefs_claimed=["life_insurance_premium"],
            num_reliefs=1,
            utility_score=0.75,
            rank=1,
            estimated_tax_liability=1_000_000,
            estimated_tax_savings=100_000,
            compliance_status="COMPLIANT",
            audit_risk_level="LOW",
            legal_summary="Test explanation",
        )
        assert strategy.strategy_id == 1
        assert strategy.utility_score == 0.75
        assert strategy.rank == 1
        assert strategy.audit_risk_level == "LOW"

    def test_utility_score_bounds(self):
        """Utility score must be 0-1."""
        with pytest.raises(ValidationError):
            RankedStrategyV1(
                strategy_id=1,
                strategy_name="Test",
                reliefs_claimed=[],
                num_reliefs=0,
                utility_score=1.5,  # Invalid: > 1
                rank=1,
                estimated_tax_liability=1_000_000,
                compliance_status="COMPLIANT",
                audit_risk_level="LOW",
                legal_summary="Test",
            )

    def test_rank_must_be_positive(self):
        """Rank must be >= 1."""
        with pytest.raises(ValidationError):
            RankedStrategyV1(
                strategy_id=1,
                strategy_name="Test",
                reliefs_claimed=[],
                num_reliefs=0,
                utility_score=0.5,
                rank=0,  # Invalid: < 1
                estimated_tax_liability=1_000_000,
                compliance_status="COMPLIANT",
                audit_risk_level="LOW",
                legal_summary="Test",
            )

    def test_response_has_top_10_strategies(self):
        """Response should have up to 10 ranked strategies."""
        strategies = [
            RankedStrategyV1(
                strategy_id=i,
                strategy_name=f"Strategy {i}",
                reliefs_claimed=[],
                num_reliefs=0,
                utility_score=0.5 + i * 0.01,
                rank=i,
                estimated_tax_liability=1_000_000 - i * 10_000,
                compliance_status="COMPLIANT",
                audit_risk_level="LOW",
                legal_summary="Test",
            )
            for i in range(1, 11)
        ]

        response = MLRankResponseV1(
            tax_year="2025_26",
            gross_income=8_500_000,
            taxable_basis=7_000_000,
            baseline_tax_liability=1_500_000,
            ranked_strategies=strategies,
            best_strategy_index=0,
            timestamp=datetime.utcnow().isoformat(),
        )

        assert len(response.ranked_strategies) == 10
        assert response.ranked_strategies[0].rank == 1
        assert response.ranked_strategies[-1].rank == 10


class TestMLServicesIntegration:
    """Test integration of ML services."""

    @pytest.fixture
    def ml_services(self):
        """Initialize ML services."""
        ml_ranker = MLStrategyRanker(models_dir="phase2_models")
        feature_engineer = FeatureEngineeringService()
        legal_rag = LegalRAGService()
        return ml_ranker, feature_engineer, legal_rag

    def test_ml_ranker_loads(self, ml_services):
        """ML ranker loads unified model."""
        ml_ranker, _, _ = ml_services
        assert ml_ranker.is_ready()
        assert ml_ranker.model is not None
        assert len(ml_ranker.feature_names) == 74

    def test_feature_engineer_initializes(self, ml_services):
        """Feature engineer initializes correctly."""
        _, feature_engineer, _ = ml_services
        assert feature_engineer is not None

    def test_legal_rag_initializes(self, ml_services):
        """Legal RAG initializes correctly."""
        _, _, legal_rag = ml_services
        assert legal_rag is not None

    def test_predict_utility_score(self, ml_services):
        """ML ranker predicts utility scores."""
        ml_ranker, _, _ = ml_services

        # Create test features
        test_features = {}
        for name in ml_ranker.feature_names:
            test_features[name] = 0.5

        score = ml_ranker.predict_utility_score(test_features, tax_year="2025_26")
        assert 0 <= score <= 1
        assert isinstance(score, float)

    def test_legal_explanation_generation(self, ml_services):
        """Legal RAG generates explanations."""
        _, _, legal_rag = ml_services

        explanation = legal_rag.get_explanation_for_strategy(
            reliefs=["life_insurance_premium", "home_loan_interest"],
            tax_year="2025_26",
            income_profile={"salary": 5_000_000, "rental": 1_000_000},
        )

        assert "summary" in explanation
        assert len(explanation["summary"]) > 0

    def test_ranking_service_workflow(self, ml_services):
        """Complete ranking service workflow."""
        ml_ranker, feature_engineer, legal_rag = ml_services

        # Create service
        ranking_service = MLRankingService(ml_ranker, feature_engineer, legal_rag)

        # Create test request
        request = MLRankRequestV1(
            tax_year="2025_26",
            salary=5_000_000,
            rental_income=1_000_000,
            interest_income=500_000,
            business_income=2_000_000,
            life_insurance_premium=100_000,
            home_loan_interest=200_000,
            complexity_tolerance=3,
            audit_risk_tolerance=3,
        )

        # Dummy rules pack
        class DummyRules:
            allowed_relief_codes = [
                "life_insurance_premium",
                "health_insurance_premium",
                "home_loan_interest",
                "rent_relief",
                "charitable_donations",
                "retirement_contribution",
            ]

        # Strategy grid
        strategies = [
            {"id": 1, "name": "Baseline", "reliefs": []},
            {
                "id": 2,
                "name": "Life Insurance",
                "reliefs": ["life_insurance_premium"],
            },
            {
                "id": 3,
                "name": "Home Loan",
                "reliefs": ["home_loan_interest"],
            },
            {
                "id": 4,
                "name": "Both",
                "reliefs": ["life_insurance_premium", "home_loan_interest"],
            },
        ]

        # Rank
        response = ranking_service.rank_strategies(request, DummyRules(), strategies)

        assert response.tax_year == "2025_26"
        assert response.gross_income == 8_500_000
        assert response.baseline_tax_liability > 0
        assert len(response.ranked_strategies) > 0


class TestMLHealthCheck:
    """Test health check endpoint."""

    def test_health_check_response(self):
        """Health check returns valid response."""
        health = MLHealthCheckResponseV1(
            status="ready",
            model_version="unified-xgboost-50k",
            num_features=74,
            model_size_mb=0.45,
        )
        assert health.status == "ready"
        assert health.num_features == 74
        assert health.model_size_mb == 0.45

    def test_not_ready_status(self):
        """Health check can report not ready."""
        health = MLHealthCheckResponseV1(status="not_ready")
        assert health.status == "not_ready"
        assert health.num_features == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_high_income(self):
        """Handle very high income."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=500_000_000,
            rental_income=100_000_000,
        )
        assert req.salary == 500_000_000

    def test_very_low_income(self):
        """Handle very low income."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=100_000,
        )
        assert req.salary == 100_000

    def test_all_reliefs_zero(self):
        """Handle zero reliefs."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=1_000_000,
            life_insurance_premium=0,
            health_insurance_premium=0,
            home_loan_interest=0,
        )
        assert req.life_insurance_premium == 0

    def test_high_preference_values(self):
        """Handle maximum preference values."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=1_000_000,
            complexity_tolerance=5,
            audit_risk_tolerance=5,
            time_available=3,
        )
        assert req.complexity_tolerance == 5
        assert req.audit_risk_tolerance == 5

    def test_low_preference_values(self):
        """Handle minimum preference values."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=1_000_000,
            complexity_tolerance=1,
            audit_risk_tolerance=1,
            time_available=1,
        )
        assert req.complexity_tolerance == 1
        assert req.audit_risk_tolerance == 1


class TestDataValidation:
    """Test data validation and type checking."""

    def test_income_is_float(self):
        """Income can be float."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=1_000_000.50,
        )
        assert isinstance(req.salary, float)

    def test_income_is_int(self):
        """Income can be int."""
        req = MLRankRequestV1(
            tax_year="2025_26",
            salary=1_000_000,
        )
        assert req.salary == 1_000_000

    def test_tax_year_formats(self):
        """Support various tax year formats."""
        for year in ["2024_25", "2025_26", "2026_27"]:
            req = MLRankRequestV1(tax_year=year, salary=1_000_000)
            assert req.tax_year == year


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
