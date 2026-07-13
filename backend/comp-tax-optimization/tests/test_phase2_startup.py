"""Test Phase 2 ML modules startup and initialization"""

import pytest
from pathlib import Path
from phase2_ml import MLStrategyRanker, FeatureEngineeringService, LegalRAGService


class TestMLStrategyRanker:
    """Test MLStrategyRanker initialization and basic functionality"""

    def test_ranker_initializes(self):
        """Test that ranker can initialize"""
        ranker = MLStrategyRanker(models_dir="phase2_models")
        assert ranker is not None
        assert isinstance(ranker, MLStrategyRanker)

    def test_ranker_has_models_attribute(self):
        """Test that ranker has models dict"""
        ranker = MLStrategyRanker(models_dir="phase2_models")
        assert hasattr(ranker, 'models')
        assert isinstance(ranker.models, dict)

    def test_ranker_has_feature_names_attribute(self):
        """Test that ranker has feature_names dict"""
        ranker = MLStrategyRanker(models_dir="phase2_models")
        assert hasattr(ranker, 'feature_names')
        assert isinstance(ranker.feature_names, dict)

    def test_ranker_is_ready_checks_models(self):
        """Test that is_ready() method works"""
        ranker = MLStrategyRanker(models_dir="phase2_models")
        is_ready = ranker.is_ready()
        assert isinstance(is_ready, bool)


class TestFeatureEngineeringService:
    """Test FeatureEngineeringService initialization and functionality"""

    def test_service_initializes(self):
        """Test that service can initialize"""
        service = FeatureEngineeringService()
        assert service is not None
        assert isinstance(service, FeatureEngineeringService)

    def test_service_has_relief_defaults(self):
        """Test that service has relief defaults"""
        service = FeatureEngineeringService()
        assert hasattr(service, 'RELIEF_DEFAULTS')
        assert len(service.RELIEF_DEFAULTS) == 6

    def test_service_has_risky_reliefs(self):
        """Test that service has risky reliefs mapping"""
        service = FeatureEngineeringService()
        assert hasattr(service, 'RISKY_RELIEFS')
        assert len(service.RISKY_RELIEFS) == 6

    def test_engineer_features_creates_features(self):
        """Test that engineer_features creates a features dict"""
        service = FeatureEngineeringService()

        persona = {
            'salary': 5_000_000,
            'rental_income': 1_000_000,
            'interest_income': 500_000,
            'business_income': 2_000_000,
            'complexity_tolerance': 3,
            'audit_risk_tolerance': 3,
            'time_available': 2,
        }

        strategy = {
            'num_reliefs': 2,
            'reliefs_claimed': ['life_insurance_premium', 'home_loan_interest'],
            'relief_amounts': {'life_insurance_premium': 50000, 'home_loan_interest': 200000},
        }

        tax_outcome = {
            'tax_liability': 1_000_000,
            'effective_rate': 0.18,
            'compliance_passed': True,
            'violations_count': 0,
        }

        features = service.engineer_features(persona, strategy, tax_outcome)

        assert features is not None
        assert isinstance(features, dict)
        assert len(features) > 0

    def test_engineered_features_are_numeric(self):
        """Test that all engineered features are numeric"""
        service = FeatureEngineeringService()

        persona = {
            'salary': 5_000_000,
            'rental_income': 1_000_000,
            'interest_income': 500_000,
            'business_income': 2_000_000,
            'complexity_tolerance': 3,
            'audit_risk_tolerance': 3,
            'time_available': 2,
        }

        strategy = {
            'num_reliefs': 2,
            'reliefs_claimed': ['life_insurance_premium', 'home_loan_interest'],
            'relief_amounts': {'life_insurance_premium': 50000, 'home_loan_interest': 200000},
        }

        tax_outcome = {
            'tax_liability': 1_000_000,
            'effective_rate': 0.18,
            'compliance_passed': True,
            'violations_count': 0,
        }

        features = service.engineer_features(persona, strategy, tax_outcome)

        for key, value in features.items():
            assert isinstance(value, (int, float)), f"Feature {key} is not numeric: {type(value)}"


class TestLegalRAGService:
    """Test LegalRAGService initialization and functionality"""

    def test_service_initializes(self):
        """Test that service can initialize"""
        service = LegalRAGService()
        assert service is not None
        assert isinstance(service, LegalRAGService)

    def test_service_has_relief_explanations(self):
        """Test that service has relief explanations"""
        service = LegalRAGService()
        assert hasattr(service, 'relief_explanations')
        assert isinstance(service.relief_explanations, dict)
        assert len(service.relief_explanations) == 6

    def test_get_explanation_for_no_reliefs(self):
        """Test getting explanation when no reliefs claimed"""
        service = LegalRAGService()

        explanation = service.get_explanation_for_strategy(
            reliefs=[],
            tax_year='2024_25',
            income_profile={'salary': 5_000_000, 'rental': 1_000_000, 'interest': 500_000, 'business': 2_000_000}
        )

        assert 'summary' in explanation
        assert 'sections' in explanation
        assert len(explanation['sections']) == 0

    def test_get_explanation_for_single_relief(self):
        """Test getting explanation for single relief"""
        service = LegalRAGService()

        explanation = service.get_explanation_for_strategy(
            reliefs=['life_insurance_premium'],
            tax_year='2024_25',
            income_profile={'salary': 5_000_000, 'rental': 1_000_000, 'interest': 500_000, 'business': 2_000_000}
        )

        assert 'summary' in explanation
        assert 'sections' in explanation
        assert len(explanation['sections']) == 1
        assert explanation['sections'][0]['relief'] == 'life_insurance_premium'

    def test_get_explanation_for_multiple_reliefs(self):
        """Test getting explanation for multiple reliefs"""
        service = LegalRAGService()

        reliefs = ['life_insurance_premium', 'home_loan_interest', 'retirement_contribution']
        explanation = service.get_explanation_for_strategy(
            reliefs=reliefs,
            tax_year='2024_25',
            income_profile={'salary': 5_000_000, 'rental': 1_000_000, 'interest': 500_000, 'business': 2_000_000}
        )

        assert 'summary' in explanation
        assert 'sections' in explanation
        assert 'general_guidance' in explanation
        assert 'compliance_note' in explanation
        assert 'record_keeping' in explanation
        assert len(explanation['sections']) == 3

    def test_explanation_has_required_fields(self):
        """Test that explanation has all required fields"""
        service = LegalRAGService()

        explanation = service.get_explanation_for_strategy(
            reliefs=['charitable_donations'],
            tax_year='2024_25',
            income_profile={'salary': 5_000_000, 'rental': 1_000_000, 'interest': 500_000, 'business': 2_000_000}
        )

        required_fields = ['summary', 'sections', 'general_guidance', 'compliance_note', 'record_keeping', 'audit_risk_summary', 'source']
        for field in required_fields:
            assert field in explanation, f"Missing required field: {field}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
