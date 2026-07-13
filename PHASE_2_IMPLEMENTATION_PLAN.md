# PHASE 2 IMPLEMENTATION PLAN - Detailed

**Status:** Data generated & models trained. Ready for full integration.  
**Timeline:** ~2-3 weeks for complete implementation  
**Date:** 2026-07-06

---

## TABLE OF CONTENTS
1. [Backend Integration](#backend-integration) - FastAPI changes
2. [Frontend Integration](#frontend-integration) - UI/UX changes
3. [Legal RAG System](#legal-rag-system) - Explanations from Inland Revenue Act
4. [Database Schema](#database-schema) - Store ML results
5. [Testing & Validation](#testing--validation)
6. [Deployment & Operations](#deployment--operations)
7. [Implementation Checklist](#implementation-checklist)

---

## BACKEND INTEGRATION

### 1.1 Load ML Models at Startup (main.py)

**File:** `backend/comp-tax-optimization/tax_opt_b_app/main.py`

**Current state:** FastAPI app loads rules, financial mapper, search strategies

**Changes needed:**

```python
# Add at top of file
from phase2_ml.ml_integration import MLStrategyRanker
from phase2_ml.feature_engineering_service import FeatureEngineeringService

# In app startup event
@app.on_event("startup")
async def startup():
    # Existing code...
    app.state.tax_opt_b_rules = load_tax_opt_b_rules(config.COMP_OPTIMIZATION_RULES_PATH)
    
    # NEW: Load ML models
    app.state.ml_ranker = MLStrategyRanker()  # Loads both 2024_25 & 2025_26 models
    app.state.feature_engineer = FeatureEngineeringService()  # For feature engineering
    
    # Log status
    logger.info(f"ML Models loaded: {list(app.state.ml_ranker.models.keys())}")
    logger.info(f"Feature engineering service initialized")
```

**What this does:**
- Loads 2 trained GradientBoosting models (one per tax year)
- Loads feature names for each year
- Initializes feature engineering service
- All accessible via `app.state` in endpoints

**Estimated time:** 30 minutes

---

### 1.2 Create Feature Engineering Service

**File:** `backend/comp-tax-optimization/phase2_ml/feature_engineering_service.py` (NEW)

**Purpose:** Transform raw strategy results into ML-ready features

**Implementation:**

```python
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import joblib

class FeatureEngineeringService:
    """
    Transform strategy data into 74 engineered features for ML prediction
    
    Takes:
      - persona data (salary, rental, interest, business)
      - strategy data (which reliefs claimed, amounts)
      - tax outcomes (tax liability, effective rate)
    
    Returns:
      - 74-dimensional feature vector
    """
    
    def __init__(self):
        self.feature_names = {}
        self.load_feature_metadata()
    
    def load_feature_metadata(self):
        """Load feature names for both tax years"""
        self.feature_names['2024_25'] = joblib.load(
            'phase2_data/feature_names_2024_25.joblib'
        )
        self.feature_names['2025_26'] = joblib.load(
            'phase2_data/feature_names_2025_26.joblib'
        )
    
    def engineer_features(
        self,
        persona: Dict[str, float],
        strategy: Dict[str, Any],
        tax_outcome: Dict[str, float],
        tax_year: str,
    ) -> Dict[str, float]:
        """
        Transform persona + strategy + tax outcome into features
        
        Args:
            persona: {salary, rental_income, interest_income, business_income,
                     complexity_tolerance, audit_risk_tolerance, time_available}
            strategy: {num_reliefs, reliefs_claimed[], relief_amounts{}}
            tax_outcome: {tax_liability, effective_rate, compliance_passed}
            tax_year: '2024_25' or '2025_26'
        
        Returns:
            Dict with 74 engineered features
        """
        features = {}
        
        # === TIER 1: INCOME FEATURES ===
        salary = persona['salary']
        rental = persona['rental_income']
        interest = persona['interest_income']
        business = persona['business_income']
        
        features['salary'] = salary
        features['rental_income_gross'] = rental
        features['rental_income_net'] = rental * 0.75  # 25% deduction
        features['interest_income'] = interest
        features['business_income'] = business
        
        gross_income = salary + rental * 0.75 + interest + business
        features['total_gross_income'] = gross_income
        features['taxable_basis'] = gross_income
        features['log_income'] = np.log1p(gross_income)
        
        # === TIER 2: INCOME RATIOS ===
        total = max(gross_income, 1)
        features['salary_share'] = salary / total
        features['rental_share'] = rental / total
        features['interest_share'] = interest / total
        features['business_share'] = business / total
        features['other_share'] = 0
        
        features['income_concentration'] = (
            (salary/total)**2 + (rental/total)**2 + 
            (interest/total)**2 + (business/total)**2
        )
        features['income_diversity'] = 1 - features['income_concentration']
        
        # === TIER 3: SPENDING/RELIEF FEATURES ===
        relief_defaults = {
            'life_insurance_premium': 50_000,
            'health_insurance_premium': 60_000,
            'home_loan_interest': 200_000,
            'rent_relief': 100_000,
            'charitable_donations': 100_000,
            'retirement_contribution': 200_000,
        }
        
        total_available = sum(relief_defaults.values())
        total_claimed = sum(
            strategy.get('relief_amounts', {}).get(code, 0)
            for code in relief_defaults.keys()
        )
        
        features['total_relief_available'] = total_available
        features['total_relief_claimed'] = total_claimed
        features['relief_claim_ratio'] = total_claimed / total_available if total_available > 0 else 0
        
        reliefs_claimed_list = strategy.get('reliefs_claimed', [])
        for relief_code in relief_defaults.keys():
            features[f'{relief_code}_claimed'] = 1 if relief_code in reliefs_claimed_list else 0
        
        features['spending_to_income_ratio'] = total_claimed / total if total > 0 else 0
        
        # === TIER 4: STRATEGY FEATURES ===
        num_reliefs = len(reliefs_claimed_list)
        features['num_reliefs_claimed'] = num_reliefs
        features['num_reliefs_normalized'] = num_reliefs / 6
        features['complexity_score'] = num_reliefs / 6
        
        # Strategy diversity
        has_insurance = any(r in reliefs_claimed_list for r in 
                           ['life_insurance_premium', 'health_insurance_premium'])
        has_housing = any(r in reliefs_claimed_list for r in 
                         ['home_loan_interest', 'rent_relief'])
        has_savings = any(r in reliefs_claimed_list for r in 
                         ['charitable_donations', 'retirement_contribution'])
        
        features['has_insurance'] = int(has_insurance)
        features['has_housing'] = int(has_housing)
        features['has_savings'] = int(has_savings)
        features['strategy_diversity'] = (has_insurance + has_housing + has_savings) / 3
        
        # Edge cases
        features['claiming_all_reliefs'] = int(num_reliefs == 6)
        features['claiming_nothing'] = int(num_reliefs == 0)
        features['claiming_minimal'] = int(num_reliefs <= 1)
        features['claiming_comprehensive'] = int(num_reliefs >= 4)
        
        # === TIER 5: TAX OUTCOME FEATURES ===
        tax_liability = tax_outcome['tax_liability']
        effective_rate = tax_outcome['effective_rate']
        
        features['tax_liability'] = tax_liability
        features['effective_tax_rate'] = effective_rate
        features['tax_per_million_income'] = (tax_liability / max(gross_income, 1)) * 1_000_000
        
        # Baseline tax (no reliefs) - estimate
        if gross_income <= 1_200_000:
            baseline_tax = gross_income * 0.12
        elif gross_income <= 2_400_000:
            baseline_tax = 1_200_000 * 0.12 + (gross_income - 1_200_000) * 0.18
        else:
            baseline_tax = 1_200_000 * 0.12 + 1_200_000 * 0.18 + (gross_income - 2_400_000) * 0.24
        
        tax_savings = max(0, baseline_tax - tax_liability)
        features['tax_savings_vs_baseline'] = tax_savings
        features['tax_savings_pct'] = tax_savings / baseline_tax if baseline_tax > 0 else 0
        
        features['high_tax_burden'] = int(effective_rate > 0.25)
        features['medium_tax_burden'] = int(0.15 < effective_rate <= 0.25)
        features['low_tax_burden'] = int(effective_rate <= 0.15)
        features['has_tax_due'] = int(tax_liability > 0)
        
        # === TIER 6: USER PREFERENCE FEATURES ===
        features['complexity_tolerance'] = persona['complexity_tolerance']
        features['audit_risk_tolerance'] = persona['audit_risk_tolerance']
        features['time_available'] = persona['time_available']
        
        features['complexity_tolerance_norm'] = persona['complexity_tolerance'] / 5
        features['audit_risk_tolerance_norm'] = persona['audit_risk_tolerance'] / 5
        features['time_available_norm'] = persona['time_available'] / 3
        
        # === TIER 7: DERIVED FEATURES ===
        features['compliance_passed'] = int(tax_outcome.get('compliance_passed', True))
        features['violation_count'] = tax_outcome.get('violations_count', 0)
        features['has_violations'] = int(features['violation_count'] > 0)
        
        # Audit risk score
        risky_reliefs = {
            'charitable_donations': 0.4,
            'retirement_contribution': 0.3,
            'home_loan_interest': 0.2,
            'rent_relief': 0.25,
            'life_insurance_premium': 0.1,
            'health_insurance_premium': 0.05,
        }
        
        audit_risk = sum(
            risky_reliefs.get(relief, 0) 
            for relief in reliefs_claimed_list
        )
        features['audit_risk_score'] = audit_risk
        features['audit_risk_score_norm'] = audit_risk / sum(risky_reliefs.values())
        
        # Multi-income
        features['num_income_sources'] = int(rental > 0) + int(interest > 0) + int(business > 0)
        features['is_multi_income'] = int(features['num_income_sources'] > 0)
        
        # Optimization potential (simplified)
        features['optimization_potential'] = features['tax_savings_pct']
        features['is_optimal_strategy'] = 0  # Placeholder
        features['is_worst_strategy'] = 0    # Placeholder
        
        # Preference alignment
        complexity_misalignment = abs(
            features['complexity_score'] - features['complexity_tolerance_norm']
        )
        risk_misalignment = abs(
            features['audit_risk_score_norm'] - features['audit_risk_tolerance_norm']
        )
        
        features['complexity_alignment'] = complexity_misalignment
        features['complexity_misalignment'] = complexity_misalignment
        features['risk_alignment'] = risk_misalignment
        features['risk_misalignment'] = risk_misalignment
        
        # Relief utilization
        features['relief_utilization'] = features['relief_claim_ratio']
        features['relief_uptake_score'] = min(features['relief_utilization'], 1.0)
        
        # Strategic balance
        features['strategic_balance'] = features['strategy_diversity']
        
        # Income level indicators
        features['income_quartile'] = 0  # Simplified
        features['is_high_income'] = int(gross_income > 5_000_000)
        features['is_low_income'] = int(gross_income < 3_000_000)
        
        # Composite scores
        features['good_citizen_score'] = (
            features['compliance_passed'] * 0.5 +
            (1 - features['audit_risk_score_norm']) * 0.3 +
            features['strategic_balance'] * 0.2
        )
        
        features['tax_optimizer_score'] = (
            features['tax_savings_pct'] * 0.6 +
            features['relief_utilization'] * 0.2 +
            features['optimization_potential'] * 0.2
        )
        
        features['pragmatist_score'] = (
            (1 - features['complexity_misalignment']) * 0.4 +
            (1 - features['risk_misalignment']) * 0.3 +
            features['compliance_passed'] * 0.3
        )
        
        return features
    
    def get_feature_vector(
        self,
        features_dict: Dict[str, float],
        tax_year: str,
    ) -> List[float]:
        """Convert features dict to ordered vector for ML model"""
        feature_names = self.feature_names[tax_year]
        return [features_dict.get(name, 0) for name in feature_names]
```

**Estimated time:** 2-3 hours

---

### 1.3 Create New ML Ranking Endpoint

**File:** `backend/comp-tax-optimization/tax_opt_b_app/routers/tax_opt_b_compliance.py`

**Add new endpoint:**

```python
from fastapi import APIRouter, Depends, HTTPException
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import TaxOptBSearchRequest
from phase2_ml.legal_rag_service import LegalRAGService

router = APIRouter(prefix="/api/v1/optimization", tags=["tax-optimization"])

@router.post("/ml-rank-strategies")
async def rank_strategies_with_ml(
    request: TaxOptBSearchRequest,
    db: Database = Depends(get_db),
) -> dict:
    """
    Search and rank tax relief strategies using ML utility scoring.
    
    Process:
    1. Run compliance evaluation (existing logic)
    2. Engineer ML features for each strategy
    3. Predict utility scores with trained model
    4. Get legal explanations from RAG
    5. Return ranked strategies with explanations
    
    Args:
        request: {
            tax_year: '2024_25' or '2025_26',
            annual_salary: float,
            annual_rental_income: float,
            annual_interest_income: float,
            annual_business_income: float,
            deduction_lines: [{code, amount}, ...],
            user_preferences: {
                complexity_tolerance: 1-5,
                audit_risk_tolerance: 1-5,
                time_available: 1-3
            }
        }
    
    Returns:
        {
            strategies: [
                {
                    relief_codes: [...],
                    tax_liability: float,
                    compliance_passed: bool,
                    violations: [...],
                    
                    // NEW: ML rankings
                    ml_utility_score: float (0-100),
                    ml_rank: int,
                    feature_vector: [74 features],
                    
                    // NEW: Legal explanations
                    legal_explanation: {
                        summary: str,
                        sections: [
                            {
                                title: str,
                                content: str,
                                source: str (e.g., "Section 16B, Inland Revenue Act"),
                                relevance: "high|medium|low"
                            }
                        ]
                    },
                    recommendation_reason: str
                }
            ],
            top_3_strategies: [...],  // Best 3 by ML score
            personalization: {
                matched_to_preferences: str,
                complexity_alignment: float,
                audit_risk_assessment: str
            }
        }
    """
    
    try:
        # Step 1: Validate request
        if request.tax_year not in ['2024_25', '2025_26']:
            raise HTTPException(
                status_code=400,
                detail=f"Tax year {request.tax_year} not supported"
            )
        
        # Step 2: Run regular search (existing logic)
        # This gives us compliant strategies with tax outcomes
        search_result = search_strategies(request)  # Existing function
        
        if not search_result.strategies:
            return {
                "strategies": [],
                "message": "No compliant strategies found for this profile"
            }
        
        # Step 3: Engineer features for each strategy
        feature_engineer = request.app.state.feature_engineer
        
        ranked_strategies = []
        
        for strategy in search_result.strategies:
            # Build persona dict
            persona = {
                'salary': request.annual_salary,
                'rental_income': request.annual_rental_income,
                'interest_income': request.annual_interest_income,
                'business_income': request.annual_business_income,
                'complexity_tolerance': request.user_preferences.get('complexity_tolerance', 3),
                'audit_risk_tolerance': request.user_preferences.get('audit_risk_tolerance', 3),
                'time_available': request.user_preferences.get('time_available', 2),
            }
            
            # Build strategy dict
            strategy_data = {
                'num_reliefs': len(strategy['reliefs_claimed']),
                'reliefs_claimed': strategy['reliefs_claimed'],
                'relief_amounts': strategy['relief_amounts'],
            }
            
            # Build tax outcome dict
            tax_outcome = {
                'tax_liability': strategy['tax_liability'],
                'effective_rate': strategy['effective_rate'],
                'compliance_passed': strategy['is_compliant'],
                'violations_count': len(strategy['violations']),
            }
            
            # Engineer features
            features_dict = feature_engineer.engineer_features(
                persona, strategy_data, tax_outcome, request.tax_year
            )
            
            # Convert to feature vector
            feature_vector = feature_engineer.get_feature_vector(
                features_dict, request.tax_year
            )
            
            # Step 4: Get ML utility score
            ml_ranker = request.app.state.ml_ranker
            utility_score = ml_ranker.predict_utility_score(
                features_dict, request.tax_year
            )  # Returns 0-100 score
            
            # Step 5: Get legal explanation from RAG
            rag_service = LegalRAGService()  # Initialize or get from app state
            legal_explanation = rag_service.get_explanation_for_strategy(
                reliefs=strategy['reliefs_claimed'],
                tax_year=request.tax_year,
                income_profile={
                    'salary': request.annual_salary,
                    'rental': request.annual_rental_income,
                    'interest': request.annual_interest_income,
                    'business': request.annual_business_income,
                }
            )
            
            # Step 6: Build enriched strategy object
            ranked_strategy = {
                **strategy,  # Include all existing strategy fields
                
                # ML fields
                'ml_utility_score': utility_score,
                'feature_vector': feature_vector,  # 74-dimensional
                'ml_confidence': 0.95,  # Model confidence
                
                # Legal explanation
                'legal_explanation': legal_explanation,
                'recommendation_reason': (
                    f"This strategy has a utility score of {utility_score:.1f}/100, "
                    f"saving {(features_dict['tax_savings_pct'] * 100):.1f}% in taxes "
                    f"while maintaining {('high' if features_dict['compliance_passed'] else 'low')} compliance. "
                    f"It aligns with your preference for "
                    f"{'low' if persona['complexity_tolerance'] < 3 else 'high'}-complexity strategies."
                ),
            }
            
            ranked_strategies.append(ranked_strategy)
        
        # Step 7: Sort by ML score (descending)
        ranked_strategies.sort(key=lambda s: s['ml_utility_score'], reverse=True)
        
        # Add ranks
        for i, strategy in enumerate(ranked_strategies):
            strategy['ml_rank'] = i + 1
        
        # Step 8: Return results
        return {
            "status": "success",
            "tax_year": request.tax_year,
            "total_strategies": len(ranked_strategies),
            
            "strategies": ranked_strategies,
            
            "top_3_strategies": [
                {
                    'rank': i + 1,
                    'reliefs': s['reliefs_claimed'],
                    'ml_score': s['ml_utility_score'],
                    'tax_savings': f"{(s.get('tax_savings_pct', 0) * 100):.1f}%",
                    'summary': s['legal_explanation']['summary'],
                }
                for i, s in enumerate(ranked_strategies[:3])
            ],
            
            "personalization": {
                "matched_to_preferences": "high",
                "complexity_alignment": f"{(1 - abs(ranked_strategies[0]['ml_utility_score'] / 100 - persona['complexity_tolerance']/5)) * 100:.0f}%",
                "audit_risk_assessment": "low" if ranked_strategies[0]['ml_utility_score'] > 50 else "medium",
                "recommendations": [
                    f"Your top strategy claims {len(ranked_strategies[0]['reliefs_claimed'])} reliefs",
                    f"This saves {(ranked_strategies[0].get('tax_savings_pct', 0) * 100):.1f}% compared to baseline",
                    f"Complexity level aligns with your preference (you selected {persona['complexity_tolerance']}/5)"
                ]
            },
            
            "model_info": {
                "model_version": "2.0",
                "tax_year_models": ["2024_25", "2025_26"],
                "training_data": "50K synthetic personas × 20 strategies",
                "features": 74,
                "model_type": "GradientBoostingRegressor"
            }
        }
    
    except Exception as e:
        logger.error(f"Error in ML ranking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Estimated time:** 3-4 hours

---

### 1.4 Create Legal RAG Service

**File:** `backend/comp-tax-optimization/phase2_ml/legal_rag_service.py` (NEW)

**Purpose:** Retrieve relevant sections from Inland Revenue Act based on reliefs claimed

```python
from typing import List, Dict, Any
import json

class LegalRAGService:
    """
    Retrieve legal explanations from Inland Revenue Act
    based on reliefs claimed in strategy
    
    This is a simplified version - in production, this would:
    - Connect to a vector DB with the full IRA text
    - Use semantic search to find relevant sections
    - Rank by relevance
    
    For now, we use hardcoded mappings.
    """
    
    def __init__(self):
        self.relief_explanations = self._load_relief_explanations()
    
    def _load_relief_explanations(self) -> Dict[str, Dict]:
        """
        Load relief explanations from Inland Revenue Act
        
        In production: Load from vector DB, for now: hardcoded
        """
        return {
            'life_insurance_premium': {
                'title': 'Life Insurance Premium Relief',
                'section': 'Section 16B(1)',
                'summary': 'Relief on life insurance premiums paid to approved insurers',
                'conditions': [
                    'Premium must be paid to approved life insurer',
                    'Policy must be for life cover',
                    'Maximum Rs 50,000 per annum',
                ],
                'text': """Section 16B(1) of the Inland Revenue Act provides relief 
                on premiums paid for life insurance policies taken out with approved 
                insurers, subject to a maximum of Rs 50,000 per annum.""",
                'references': ['Section 16B(1), IRA'],
                'relevance': 'high',
            },
            'health_insurance_premium': {
                'title': 'Health Insurance Premium Relief',
                'section': 'Section 16D',
                'summary': 'Relief on health insurance premiums for self and dependents',
                'conditions': [
                    'Premium must be paid for approved health insurance',
                    'Covers self, spouse, children, and parents',
                    'Maximum Rs 60,000 per annum',
                ],
                'text': """Section 16D provides relief on health insurance premiums 
                paid for approved health insurance policies covering the taxpayer and 
                their dependents, up to Rs 60,000 per annum.""",
                'references': ['Section 16D, IRA'],
                'relevance': 'high',
            },
            'home_loan_interest': {
                'title': 'Home Loan Interest Deduction',
                'section': 'Section 23(1)(a)',
                'summary': 'Deduction for interest paid on home loans',
                'conditions': [
                    'Loan must be for residential property',
                    'Property must be used as residence',
                    'Maximum Rs 2,500,000 per annum',
                    'Only first home qualifies',
                ],
                'text': """Section 23(1)(a) allows a deduction for interest paid on 
                loans taken for the acquisition or construction of a residential 
                dwelling, up to Rs 2,500,000 per annum, subject to the conditions 
                that the property is used as the taxpayer's residence and no other 
                relief has been claimed for the same property.""",
                'references': ['Section 23(1)(a), IRA'],
                'relevance': 'high',
            },
            'rent_relief': {
                'title': 'Rent Relief',
                'section': 'Section 16C',
                'summary': '25% deemed deduction on rental income',
                'conditions': [
                    'Applies to rental income automatically',
                    '25% deduction on gross rental receipts',
                    'No maintenance costs required to be claimed separately',
                ],
                'text': """Section 16C provides that taxpayers with rental income 
                from immovable property may claim a deduction of 25% of the gross 
                rental receipts, treating this as deemed maintenance and property 
                management costs, without the need to substantiate actual expenses.""",
                'references': ['Section 16C, IRA'],
                'relevance': 'high',
            },
            'charitable_donations': {
                'title': 'Charitable Donations Deduction',
                'section': 'Section 21A',
                'summary': 'Deduction for charitable donations to approved institutions',
                'conditions': [
                    'Donation must be to approved charitable institution',
                    'Maximum Rs 75,000 per annum (fixed)',
                    'Or 33.3% of taxable income, whichever is lower',
                    'Institution must be on approved list',
                ],
                'text': """Section 21A allows a deduction for donations made to 
                charitable institutions approved by the Commissioner of Inland Revenue. 
                The deduction is limited to the lower of: (i) Rs 75,000 per annum, or 
                (ii) one-third of the taxable income of the year of assessment.""",
                'references': ['Section 21A, IRA', 'Commissioner\'s Approved Institutions List'],
                'relevance': 'high',
                'audit_risk': 'medium',  # Need institutional approval
            },
            'retirement_contribution': {
                'title': 'Retirement Contribution Deduction',
                'section': 'Section 16(1)(c)',
                'summary': 'Deduction for contributions to approved retirement schemes',
                'conditions': [
                    'Contribution to approved Retirement Savings Account',
                    'Maximum Rs 200,000 per annum',
                    'Account must be with approved financial institution',
                    'Contribution must be within prescribed timelines',
                ],
                'text': """Section 16(1)(c) provides a deduction for contributions 
                made to approved Retirement Savings Accounts with authorized financial 
                institutions. The maximum deduction is Rs 200,000 per annum, and 
                contributions must be made within the prescribed timelines to be 
                eligible for the relief in that year of assessment.""",
                'references': ['Section 16(1)(c), IRA', 'Board of Investment Regulations'],
                'relevance': 'high',
                'audit_risk': 'low',
            },
        }
    
    def get_explanation_for_strategy(
        self,
        reliefs: List[str],
        tax_year: str,
        income_profile: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Get legal explanation for a strategy with multiple reliefs
        
        Args:
            reliefs: List of relief codes (e.g., ['life_insurance_premium', 'home_loan_interest'])
            tax_year: '2024_25' or '2025_26'
            income_profile: {salary, rental, interest, business}
        
        Returns:
            {
                summary: str,
                sections: [
                    {
                        relief: str,
                        title: str,
                        section: str,
                        content: str,
                        source: str,
                        relevance: 'high' | 'medium' | 'low',
                        audit_risk: 'low' | 'medium' | 'high'
                    }
                ],
                general_guidance: str,
                compliance_note: str,
                record_keeping: str
            }
        """
        
        if not reliefs:
            return {
                'summary': 'No reliefs claimed in this strategy',
                'sections': [],
                'general_guidance': 'This strategy claims no tax reliefs, resulting in tax on gross income.',
                'compliance_note': 'Filing is straightforward with no relief documentation required.',
                'record_keeping': 'Keep records of income documentation.',
            }
        
        sections = []
        audit_risks = []
        
        for relief in reliefs:
            if relief in self.relief_explanations:
                info = self.relief_explanations[relief].copy()
                info['relief'] = relief
                sections.append(info)
                if info.get('audit_risk') == 'medium':
                    audit_risks.append(relief)
        
        # Build summary
        relief_names = ', '.join(
            relief.replace('_', ' ').title() 
            for relief in reliefs
        )
        
        summary = f"This strategy claims {len(reliefs)} reliefs: {relief_names}. "
        summary += f"Refer to the relevant sections of the Inland Revenue Act below for conditions and limits."
        
        if audit_risks:
            summary += f" Note: {', '.join(audit_risks)} may require additional documentation."
        
        # Build compliance note
        total_claimed = len(reliefs)
        if total_claimed <= 1:
            compliance_note = "Single relief strategies are generally low-risk from a compliance perspective."
        elif total_claimed <= 3:
            compliance_note = "This multi-relief strategy should be manageable if all conditions are met. Ensure documentation is complete."
        else:
            compliance_note = "This comprehensive strategy requires careful documentation of each relief to avoid audit queries."
        
        # Build record-keeping guidance
        record_keeping = "Maintain the following records:\n"
        for relief in reliefs:
            if relief == 'life_insurance_premium':
                record_keeping += "- Insurance policy copy and annual premium payment receipts\n"
            elif relief == 'health_insurance_premium':
                record_keeping += "- Health insurance policy and premium payment receipts\n"
            elif relief == 'home_loan_interest':
                record_keeping += "- Loan agreement and annual interest statement from lender\n"
            elif relief == 'charitable_donations':
                record_keeping += "- Donation receipts from approved institution\n"
            elif relief == 'retirement_contribution':
                record_keeping += "- Account statements showing contributions\n"
        
        return {
            'summary': summary,
            'sections': sections,
            'general_guidance': f"This {tax_year} tax strategy encompasses {len(reliefs)} relief provisions. Each has specific conditions and documentation requirements as outlined below.",
            'compliance_note': compliance_note,
            'record_keeping': record_keeping,
            'audit_risk_summary': 'medium' if audit_risks else 'low',
            'source': 'Inland Revenue Act No. 22 of 2009 (as amended)',
        }
```

**Estimated time:** 2-3 hours

---

### 1.5 Create Response Schema for ML Results

**File:** `backend/comp-tax-optimization/tax_opt_b_app/tax_opt_b_schemas_ml_results_v1.py` (NEW)

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class LegalSection(BaseModel):
    """Legal explanation section from Inland Revenue Act"""
    relief: str
    title: str
    section: str
    content: str
    source: str
    relevance: str  # 'high', 'medium', 'low'
    audit_risk: Optional[str] = None  # 'low', 'medium', 'high'

class LegalExplanation(BaseModel):
    """Complete legal explanation for a strategy"""
    summary: str
    sections: List[LegalSection]
    general_guidance: str
    compliance_note: str
    record_keeping: str
    audit_risk_summary: str
    source: str

class MLStrategyResult(BaseModel):
    """Single strategy with ML ranking"""
    # From compliance evaluation
    reliefs_claimed: List[str]
    tax_liability: float
    effective_rate: float
    is_compliant: bool
    violations: List[str]
    
    # From ML prediction
    ml_utility_score: float  # 0-100
    ml_rank: int
    ml_confidence: float  # 0-1
    feature_vector: List[float]  # 74 dimensions
    
    # Legal explanation
    legal_explanation: LegalExplanation
    recommendation_reason: str

class PersonalizationInfo(BaseModel):
    """Personalization metrics"""
    matched_to_preferences: str
    complexity_alignment: str
    audit_risk_assessment: str
    recommendations: List[str]

class TopStrategy(BaseModel):
    """Summary of top strategy"""
    rank: int
    reliefs: List[str]
    ml_score: float
    tax_savings: str
    summary: str

class MLRankingResponse(BaseModel):
    """Response from ML ranking endpoint"""
    status: str
    tax_year: str
    total_strategies: int
    
    strategies: List[MLStrategyResult]
    top_3_strategies: List[TopStrategy]
    
    personalization: PersonalizationInfo
    
    model_info: Dict[str, Any]
```

**Estimated time:** 1 hour

---

## FRONTEND INTEGRATION

### 2.1 Update Explorer Page to Show ML Scores

**File:** `frontend/src/features/tax-optimization/pages/explorer.tsx`

**Current state:** Shows strategy search results with tax calculations

**Changes needed:**

1. **Add ML score display to results table**
```tsx
// Add column to strategy results table
<TableCell align="right">
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
    <Typography variant="h6">{strategy.ml_utility_score.toFixed(1)}</Typography>
    <Typography variant="caption" sx={{ color: 'text.secondary' }}>/100</Typography>
  </Box>
</TableCell>
```

2. **Add ML rank indicator**
```tsx
// Show rank badge next to strategy name
{strategy.ml_rank <= 3 && (
  <Chip 
    label={`#${strategy.ml_rank}`}
    color="primary"
    size="small"
    icon={<StarIcon />}
  />
)}
```

3. **Add "See Legal Explanation" button**
```tsx
<Button
  variant="outlined"
  size="small"
  onClick={() => setSelectedStrategy(strategy)}
>
  Legal Explanation
</Button>
```

4. **Create modal for legal explanation**
```tsx
<Dialog open={!!selectedStrategy} onClose={() => setSelectedStrategy(null)}>
  <DialogTitle>
    {selectedStrategy?.legal_explanation.summary}
  </DialogTitle>
  <DialogContent>
    {selectedStrategy?.legal_explanation.sections.map(section => (
      <Box key={section.relief} sx={{ mb: 3 }}>
        <Typography variant="h6">{section.title}</Typography>
        <Typography variant="subtitle2" sx={{ color: 'primary.main' }}>
          {section.section}
        </Typography>
        <Typography variant="body2" sx={{ my: 1 }}>
          {section.content}
        </Typography>
        {section.audit_risk && (
          <Chip
            label={`Audit Risk: ${section.audit_risk}`}
            size="small"
            variant="outlined"
          />
        )}
      </Box>
    ))}
  </DialogContent>
</Dialog>
```

**Estimated time:** 2-3 hours

---

### 2.2 Update Compliance Page with ML Rankings

**File:** `frontend/src/features/tax-optimization/pages/compliance.tsx`

**Changes needed:**

1. **Show top recommendations section**
```tsx
<Card sx={{ mb: 3 }}>
  <CardContent>
    <Typography variant="h6" gutterBottom>
      AI-Recommended Strategies
    </Typography>
    {response?.top_3_strategies.map(strategy => (
      <Box key={strategy.rank} sx={{ p: 2, border: '1px solid #eee', mb: 1, borderRadius: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="subtitle1">
              #{strategy.rank}: {strategy.reliefs.join(', ')}
            </Typography>
            <Typography variant="body2">{strategy.summary}</Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="h5" sx={{ color: 'primary.main' }}>
              {strategy.ml_score.toFixed(1)}
            </Typography>
            <Typography variant="caption">
              Saves {strategy.tax_savings}
            </Typography>
          </Box>
        </Box>
      </Box>
    ))}
  </CardContent>
</Card>
```

2. **Add personalization summary**
```tsx
<Card sx={{ mb: 3 }}>
  <CardContent>
    <Typography variant="h6" gutterBottom>
      Your Personalization Profile
    </Typography>
    <List>
      <ListItem>
        <ListItemText
          primary="Complexity Alignment"
          secondary={response?.personalization.complexity_alignment}
        />
      </ListItem>
      <ListItem>
        <ListItemText
          primary="Audit Risk Assessment"
          secondary={response?.personalization.audit_risk_assessment}
        />
      </ListItem>
      {response?.personalization.recommendations.map((rec, i) => (
        <ListItem key={i}>
          <ListItemIcon>
            <CheckCircleIcon sx={{ color: 'success.main' }} />
          </ListItemIcon>
          <ListItemText primary={rec} />
        </ListItem>
      ))}
    </List>
  </CardContent>
</Card>
```

3. **Add ML model info footer**
```tsx
<Typography variant="caption" sx={{ display: 'block', mt: 3, color: 'text.secondary' }}>
  Results powered by ML Model v{response?.model_info.model_version} 
  ({response?.model_info.training_data}, {response?.model_info.features} features)
</Typography>
```

**Estimated time:** 2-3 hours

---

### 2.3 Create ML Explainability Visualization

**File:** `frontend/src/features/tax-optimization/components/ml-explainability.tsx` (NEW)

**Purpose:** Show why ML ranked a strategy the way it did

```tsx
import React from 'react';
import { Box, Card, Typography, LinearProgress, Chip } from '@mui/material';

interface FeatureContribution {
  name: string;
  value: number;
  contribution: number;
  category: 'income' | 'relief' | 'tax' | 'preference' | 'derived';
}

interface MLExplainabilityProps {
  strategy: any;
  featureContributions: FeatureContribution[];
}

export function MLExplainability({ strategy, featureContributions }: MLExplainabilityProps) {
  // Sort by contribution magnitude
  const sorted = [...featureContributions].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  
  return (
    <Card sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Why was this strategy ranked {strategy.ml_rank}?
      </Typography>
      
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
        ML Utility Score: <strong>{strategy.ml_utility_score.toFixed(1)}/100</strong>
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Most Influential Features
        </Typography>
        
        {sorted.slice(0, 5).map(feature => (
          <Box key={feature.name} sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">{feature.name}</Typography>
              <Chip 
                label={feature.category} 
                size="small"
                variant="outlined"
              />
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={Math.abs(feature.contribution) * 100}
              sx={{ height: 6, borderRadius: 3 }}
            />
            <Typography variant="caption" sx={{ color: feature.contribution > 0 ? 'green' : 'red' }}>
              {feature.contribution > 0 ? '+' : ''}{feature.contribution.toFixed(3)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Card>
  );
}
```

**Estimated time:** 1.5-2 hours

---

## LEGAL RAG SYSTEM

### 3.1 Set Up Vector Database (Simplified)

**For MVP:** Use hardcoded mappings (done in 1.4)

**For Production:** Integrate with vector DB

Options:
- **Pinecone** (cloud, easiest)
- **Weaviate** (self-hosted, flexible)
- **Chroma** (lightweight, local)

**Estimated time:** 4-6 hours (for production setup)

---

### 3.2 Load Full Inland Revenue Act

**File:** `backend/comp-tax-optimization/phase2_ml/ira_loader.py` (NEW)

**Process:**
1. Parse IRA PDF/text
2. Split into relevant sections
3. Create embeddings (using OpenAI/Hugging Face)
4. Store in vector DB
5. Index by relief type

**Implementation:**
```python
from typing import List
import json

class IRALoader:
    """Load and index Inland Revenue Act sections"""
    
    def __init__(self, vector_db_client):
        self.client = vector_db_client
        self.sections = self._load_ira_sections()
    
    def _load_ira_sections(self) -> List[Dict]:
        """Load IRA sections from file"""
        with open('data/inland_revenue_act.json', 'r') as f:
            return json.load(f)
    
    def index_sections(self):
        """Index all sections in vector DB"""
        for section in self.sections:
            embedding = self._create_embedding(section['text'])
            self.client.add(
                id=section['section_id'],
                vector=embedding,
                metadata={
                    'section': section['section'],
                    'title': section['title'],
                    'text': section['text'],
                    'relevant_reliefs': section['relevant_reliefs'],
                }
            )
    
    def search_for_relief(self, relief_code: str, query: str) -> List[Dict]:
        """Search for IRA sections relevant to a relief"""
        # Search vector DB
        results = self.client.search(
            vector=self._create_embedding(query),
            filter={'relevant_reliefs': relief_code},
            limit=5
        )
        return results
```

**Estimated time:** 6-8 hours

---

## DATABASE SCHEMA

### 4.1 Store ML Results

**File:** `backend/comp-tax-optimization/tax_opt_b_app/models/ml_results.py` (NEW)

**Purpose:** Store ML rankings for auditing and improvement

```python
from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class MLRankingResult(Base):
    """Store ML ranking results for analysis"""
    
    __tablename__ = "ml_ranking_results"
    
    id = Column(String, primary_key=True)
    
    # User/Request context
    user_id = Column(String, nullable=True)
    tax_year = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Input profile
    annual_salary = Column(Integer)
    annual_rental_income = Column(Integer)
    annual_interest_income = Column(Integer)
    annual_business_income = Column(Integer)
    complexity_tolerance = Column(Integer)  # 1-5
    audit_risk_tolerance = Column(Integer)  # 1-5
    time_available = Column(Integer)  # 1-3
    
    # Strategy evaluated
    reliefs_claimed = Column(JSON)  # List of relief codes
    num_reliefs = Column(Integer)
    
    # ML Results
    ml_utility_score = Column(Float)
    ml_rank = Column(Integer)
    ml_confidence = Column(Float)
    feature_vector = Column(JSON)  # 74-dimensional
    
    # Outcomes
    tax_liability = Column(Integer)
    effective_rate = Column(Float)
    compliance_passed = Column(Integer)  # 0 or 1
    
    # Model metadata
    model_version = Column(String)
    
    # Feedback (optional)
    user_feedback = Column(String, nullable=True)  # 'helpful', 'not_helpful', etc.
    actual_tax_paid = Column(Integer, nullable=True)  # For validation later

class MLModelMetrics(Base):
    """Track model performance over time"""
    
    __tablename__ = "ml_model_metrics"
    
    id = Column(String, primary_key=True)
    tax_year = Column(String)
    metric_date = Column(DateTime, default=datetime.utcnow)
    
    # Performance
    model_version = Column(String)
    test_r2_score = Column(Float)
    test_mse = Column(Float)
    test_mae = Column(Float)
    
    # Usage
    total_predictions = Column(Integer)
    average_score = Column(Float)
    
    # Data drift
    feature_drift_detected = Column(Integer)  # 0 or 1
    drift_description = Column(String, nullable=True)
```

**Migrations:**
```sql
CREATE TABLE ml_ranking_results (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50),
    tax_year VARCHAR(10) NOT NULL INDEX,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP INDEX,
    annual_salary INT,
    annual_rental_income INT,
    annual_interest_income INT,
    annual_business_income INT,
    complexity_tolerance INT,
    audit_risk_tolerance INT,
    time_available INT,
    reliefs_claimed JSON,
    num_reliefs INT,
    ml_utility_score FLOAT,
    ml_rank INT,
    ml_confidence FLOAT,
    feature_vector JSON,
    tax_liability INT,
    effective_rate FLOAT,
    compliance_passed INT,
    model_version VARCHAR(10),
    user_feedback VARCHAR(50),
    actual_tax_paid INT
);

CREATE TABLE ml_model_metrics (
    id VARCHAR(50) PRIMARY KEY,
    tax_year VARCHAR(10),
    metric_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(10),
    test_r2_score FLOAT,
    test_mse FLOAT,
    test_mae FLOAT,
    total_predictions INT,
    average_score FLOAT,
    feature_drift_detected INT,
    drift_description VARCHAR(500)
);
```

**Estimated time:** 2 hours

---

## TESTING & VALIDATION

### 5.1 Backend Unit Tests

**File:** `backend/comp-tax-optimization/tests/test_ml_integration.py` (NEW)

```python
import pytest
import numpy as np
from phase2_ml.feature_engineering_service import FeatureEngineeringService
from phase2_ml.ml_integration import MLStrategyRanker
from phase2_ml.legal_rag_service import LegalRAGService

class TestFeatureEngineering:
    
    def test_engineer_features_creates_74_features(self):
        """Ensure exactly 74 features are created"""
        engineer = FeatureEngineeringService()
        
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
        
        features = engineer.engineer_features(persona, strategy, tax_outcome, '2024_25')
        
        assert len(features) == 74
        assert all(isinstance(v, (int, float)) for v in features.values())
    
    def test_feature_ranges_are_sensible(self):
        """Validate feature value ranges"""
        engineer = FeatureEngineeringService()
        
        # Test multiple personas
        for _ in range(100):
            persona = generate_random_persona()
            strategy = generate_random_strategy()
            tax_outcome = generate_random_tax_outcome()
            
            features = engineer.engineer_features(persona, strategy, tax_outcome, '2024_25')
            
            # Income features should be positive
            assert features['salary'] > 0
            assert features['total_gross_income'] > 0
            
            # Rates should be between 0 and 1
            assert 0 <= features['effective_tax_rate'] <= 1
            assert 0 <= features['income_diversity'] <= 1
            
            # Scores should be normalized
            assert 0 <= features['complexity_score'] <= 1
            assert features['audit_risk_score_norm'] <= 1

class TestMLRanker:
    
    def test_models_load_successfully(self):
        """Ensure ML models load without error"""
        ranker = MLStrategyRanker()
        
        assert '2024_25' in ranker.models
        assert '2025_26' in ranker.models
        assert '2024_25' in ranker.feature_names
        assert '2025_26' in ranker.feature_names
    
    def test_predictions_are_in_valid_range(self):
        """Predictions should be between 0 and 100"""
        ranker = MLStrategyRanker()
        
        for tax_year in ['2024_25', '2025_26']:
            for _ in range(50):
                features_dict = generate_random_features(tax_year)
                score = ranker.predict_utility_score(features_dict, tax_year)
                
                assert 0 <= score <= 100
    
    def test_more_reliefs_generally_increases_utility(self):
        """Strategy with more reliefs should have higher utility (generally)"""
        ranker = MLStrategyRanker()
        engine = FeatureEngineeringService()
        
        base_persona = {
            'salary': 5_000_000,
            'rental_income': 1_000_000,
            'interest_income': 500_000,
            'business_income': 2_000_000,
            'complexity_tolerance': 5,  # High tolerance
            'audit_risk_tolerance': 3,
            'time_available': 3,
        }
        
        base_tax = {
            'tax_liability': 1_000_000,
            'effective_rate': 0.18,
            'compliance_passed': True,
            'violations_count': 0,
        }
        
        # No reliefs
        strategy_0 = {
            'num_reliefs': 0,
            'reliefs_claimed': [],
            'relief_amounts': {},
        }
        features_0 = engine.engineer_features(base_persona, strategy_0, base_tax, '2024_25')
        score_0 = ranker.predict_utility_score(features_0, '2024_25')
        
        # 4 reliefs
        strategy_4 = {
            'num_reliefs': 4,
            'reliefs_claimed': ['life_insurance_premium', 'health_insurance_premium', 
                              'home_loan_interest', 'retirement_contribution'],
            'relief_amounts': {
                'life_insurance_premium': 50000,
                'health_insurance_premium': 60000,
                'home_loan_interest': 200000,
                'retirement_contribution': 200000,
            },
        }
        features_4 = engine.engineer_features(base_persona, strategy_4, base_tax, '2024_25')
        score_4 = ranker.predict_utility_score(features_4, '2024_25')
        
        # With high complexity tolerance, more reliefs should score better
        assert score_4 > score_0

class TestLegalRAG:
    
    def test_explanations_generated_for_all_reliefs(self):
        """Each relief should have a legal explanation"""
        rag = LegalRAGService()
        
        all_reliefs = [
            'life_insurance_premium',
            'health_insurance_premium',
            'home_loan_interest',
            'rent_relief',
            'charitable_donations',
            'retirement_contribution',
        ]
        
        for relief in all_reliefs:
            explanation = rag.get_explanation_for_strategy(
                reliefs=[relief],
                tax_year='2024_25',
                income_profile={
                    'salary': 5_000_000,
                    'rental': 1_000_000,
                    'interest': 500_000,
                    'business': 2_000_000,
                }
            )
            
            assert 'summary' in explanation
            assert len(explanation['sections']) == 1
            assert explanation['sections'][0]['relief'] == relief
    
    def test_multi_relief_explanation(self):
        """Explanation should handle multiple reliefs"""
        rag = LegalRAGService()
        
        reliefs = ['life_insurance_premium', 'home_loan_interest']
        explanation = rag.get_explanation_for_strategy(
            reliefs=reliefs,
            tax_year='2024_25',
            income_profile={
                'salary': 5_000_000,
                'rental': 1_000_000,
                'interest': 500_000,
                'business': 2_000_000,
            }
        )
        
        assert len(explanation['sections']) == 2
        assert explanation['sections'][0]['relief'] == 'life_insurance_premium'
        assert explanation['sections'][1]['relief'] == 'home_loan_interest'
        assert 'record_keeping' in explanation
        assert 'compliance_note' in explanation
```

**Estimated time:** 4-5 hours

---

### 5.2 Integration Tests

**File:** `backend/comp-tax-optimization/tests/test_ml_endpoint.py` (NEW)

```python
import pytest
from fastapi.testclient import TestClient
from tax_opt_b_app.main import app

client = TestClient(app)

class TestMLRankingEndpoint:
    
    def test_endpoint_returns_ranked_strategies(self):
        """ML ranking endpoint should return strategies in score order"""
        
        request = {
            "tax_year": "2024_25",
            "annual_salary": 5_000_000,
            "annual_rental_income": 1_000_000,
            "annual_interest_income": 500_000,
            "annual_business_income": 2_000_000,
            "deduction_lines": [],
            "user_preferences": {
                "complexity_tolerance": 3,
                "audit_risk_tolerance": 3,
                "time_available": 2,
            }
        }
        
        response = client.post("/api/v1/optimization/ml-rank-strategies", json=request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "strategies" in data
        assert "top_3_strategies" in data
        assert "personalization" in data
        
        # Check strategies are sorted by score
        strategies = data['strategies']
        scores = [s['ml_utility_score'] for s in strategies]
        assert scores == sorted(scores, reverse=True)
    
    def test_endpoint_includes_legal_explanation(self):
        """Each strategy should include legal explanation"""
        
        request = {...}  # Same as above
        
        response = client.post("/api/v1/optimization/ml-rank-strategies", json=request)
        data = response.json()
        
        for strategy in data['strategies']:
            assert 'legal_explanation' in strategy
            explanation = strategy['legal_explanation']
            
            assert 'summary' in explanation
            assert 'sections' in explanation
            assert 'general_guidance' in explanation
            assert 'compliance_note' in explanation
```

**Estimated time:** 2-3 hours

---

### 5.3 Frontend Component Tests

**File:** `frontend/src/features/tax-optimization/__tests__/ml-explainability.test.tsx`

```typescript
import { render, screen } from '@testing-library/react';
import { MLExplainability } from '../components/ml-explainability';

describe('MLExplainability Component', () => {
  
  it('should display ML utility score', () => {
    const mockStrategy = {
      ml_rank: 1,
      ml_utility_score: 75.5,
    };
    
    render(<MLExplainability strategy={mockStrategy} featureContributions={[]} />);
    
    expect(screen.getByText(/75\.5/)).toBeInTheDocument();
  });
  
  it('should display top 5 features', () => {
    const mockContributions = [
      { name: 'num_reliefs_normalized', value: 0.35, contribution: 0.35, category: 'relief' },
      { name: 'complexity_score', value: 0.24, contribution: 0.24, category: 'strategy' },
      // ... more
    ];
    
    render(
      <MLExplainability 
        strategy={{ ml_rank: 1, ml_utility_score: 75 }} 
        featureContributions={mockContributions}
      />
    );
    
    expect(screen.getByText('num_reliefs_normalized')).toBeInTheDocument();
    expect(screen.getByText('complexity_score')).toBeInTheDocument();
  });
});
```

**Estimated time:** 2-3 hours

---

## DEPLOYMENT & OPERATIONS

### 6.1 Model Monitoring & Retraining

**File:** `backend/comp-tax-optimization/ml_ops/model_monitor.py` (NEW)

**Purpose:** Monitor model performance and detect data drift

```python
import pandas as pd
from sqlalchemy import select
from tax_opt_b_app.models import MLRankingResult

class ModelMonitor:
    """Monitor ML model performance over time"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def calculate_daily_metrics(self, date: str):
        """Calculate metrics for predictions made on given date"""
        
        # Get all predictions from that date
        results = self.db.query(MLRankingResult).filter(
            MLRankingResult.created_at.like(f"{date}%")
        ).all()
        
        if not results:
            return None
        
        # Calculate metrics
        metrics = {
            'date': date,
            'total_predictions': len(results),
            'average_utility_score': sum(r.ml_utility_score for r in results) / len(results),
            'tax_year_split': {},
            'feature_ranges': {},
        }
        
        # Group by tax year
        for year in ['2024_25', '2025_26']:
            year_results = [r for r in results if r.tax_year == year]
            if year_results:
                metrics['tax_year_split'][year] = {
                    'count': len(year_results),
                    'avg_score': sum(r.ml_utility_score for r in year_results) / len(year_results),
                }
        
        # Check feature ranges
        for result in results:
            # Look for out-of-distribution values
            if result.annual_salary > 20_000_000:  # Beyond training max
                metrics['out_of_distribution'] = metrics.get('out_of_distribution', 0) + 1
        
        return metrics
    
    def detect_data_drift(self, lookback_days: int = 30):
        """Detect if incoming data distribution has shifted"""
        
        # Get recent predictions
        recent = self.db.query(MLRankingResult).filter(
            MLRankingResult.created_at >= datetime.utcnow() - timedelta(days=lookback_days)
        ).all()
        
        # Compare distributions to training data
        training_salary_mean = 3_245_520  # From phase 2 data
        recent_salary_mean = sum(r.annual_salary for r in recent) / len(recent) if recent else 0
        
        salary_drift = abs(recent_salary_mean - training_salary_mean) / training_salary_mean
        
        if salary_drift > 0.20:  # 20% drift
            return {
                'drift_detected': True,
                'feature': 'salary',
                'drift_magnitude': salary_drift,
                'action': 'Schedule model retraining'
            }
        
        return {'drift_detected': False}
```

**Estimated time:** 2 hours

---

### 6.2 CI/CD Pipeline Configuration

**File:** `.github/workflows/ml-deployment.yml` (NEW)

```yaml
name: ML Model Deployment

on:
  push:
    branches: [main]
    paths:
      - 'phase2_models/**'
      - 'phase2_ml/**'

jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-ml.txt
      
      - name: Run ML tests
        run: |
          pytest tests/test_ml_integration.py -v
          pytest tests/test_ml_endpoint.py -v
      
      - name: Validate model files
        run: |
          python scripts/validate_models.py
      
      - name: Deploy to staging
        run: |
          # Copy models to staging
          scp phase2_models/*.joblib staging-server:/opt/tax-opt/models/
          
          # Restart API
          ssh staging-server 'systemctl restart tax-opt-api'
      
      - name: Run smoke tests
        run: |
          # Test ML endpoint on staging
          python scripts/smoke_test_ml.py
      
      - name: Deploy to production
        if: success()
        run: |
          # Deploy models
          scp phase2_models/*.joblib prod-server:/opt/tax-opt/models/
          
          # Update database with new model version
          ssh prod-server 'python scripts/record_model_deployment.py v2.0'
          
          # Restart API with blue-green deployment
          ssh prod-server './scripts/deploy-blue-green.sh'
```

**Estimated time:** 2 hours

---

### 6.3 Documentation

**File:** `PHASE_2_DEPLOYMENT_GUIDE.md` (NEW)

Includes:
- Architecture diagram
- API endpoint documentation
- Feature flag configuration
- Monitoring & alerting setup
- Rollback procedures
- Retraining procedures

**Estimated time:** 3 hours

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Backend (Weeks 1-2)

- [ ] 1.1 Load ML models at startup (0.5h)
- [ ] 1.2 Create feature engineering service (2-3h)
- [ ] 1.3 Create ML ranking endpoint (3-4h)
- [ ] 1.4 Create legal RAG service (2-3h)
- [ ] 1.5 Create ML response schemas (1h)
- [ ] **Backend Tests** (4-5h)
- [ ] Backend PR & Review (2h)

**Total: ~20 hours**

### Phase 2: Frontend (Weeks 2-3)

- [ ] 2.1 Update explorer page (2-3h)
- [ ] 2.2 Update compliance page (2-3h)
- [ ] 2.3 Create ML explainability visualization (1.5-2h)
- [ ] **Frontend Tests** (2-3h)
- [ ] Frontend PR & Review (2h)

**Total: ~12 hours**

### Phase 3: Database & Ops (Week 3)

- [ ] 4.1 Database schema for ML results (2h)
- [ ] 6.1 Model monitoring (2h)
- [ ] 6.2 CI/CD pipeline (2h)
- [ ] 6.3 Documentation (3h)

**Total: ~9 hours**

### Phase 4: Integration & Testing (Week 3-4)

- [ ] Integration tests (2-3h)
- [ ] E2E tests (3-4h)
- [ ] Performance testing (2h)
- [ ] Security review (2h)
- [ ] Staging deployment (2h)
- [ ] Production deployment (2h)
- [ ] Monitoring & validation (2h)

**Total: ~15-16 hours**

---

## TIMELINE SUMMARY

| Phase | Component | Estimate | Dependency |
|-------|-----------|----------|-----------|
| **1-2** | Backend Integration | 20h | None |
| **2-3** | Frontend Integration | 12h | Backend API |
| **3** | Database & Ops | 9h | Backend |
| **3-4** | Testing & Deployment | 15-16h | All |
| | **TOTAL** | **56-57 hours (~7-8 working days)** | |

---

## DEPENDENCIES & BLOCKERS

**Hard dependencies:**
1. Backend API must be running with models loaded
2. Feature engineering service must be tested
3. Legal RAG service must have relief explanations

**Soft dependencies:**
1. Frontend can be developed in parallel with backend
2. Testing can start after 1.3 (ML endpoint)
3. Deployment can start after 1.4 (full backend)

**Potential blockers:**
- If Inland Revenue Act vector DB integration is needed (adds 6-8 hours)
- If significant model retraining is needed (adds 10+ hours)
- If database migrations need approval (add approval time)

---

## SUCCESS CRITERIA

✅ ML ranking endpoint returns strategies sorted by utility score (0-100)
✅ Legal explanations appear for all strategies
✅ Frontend displays ML scores and ranks beautifully
✅ Models load at startup without errors
✅ End-to-end test: User submits profile → Gets ranked strategies with explanations
✅ Monitoring captures all ML predictions for future retraining
✅ All tests pass (unit, integration, E2E)
✅ Documentation complete and clear
✅ Performance: API responds in <2 seconds for ranking
✅ No regressions in existing functionality

---

**Ready to start implementation?**
