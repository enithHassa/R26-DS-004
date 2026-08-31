# ML Utility Score Clustering Issue - Fix Proposal

## Problem Analysis
Utility scores are clustered in narrow range (0.5467-0.5481) because:
1. Training data (ground truth utility scores) has low variance
2. Current formula weights tax_savings too low (45%)
3. Most strategies have identical compliance (100%), complexity (similar), and audit risk (low)
4. Model learns to output narrow range based on training data

## Current Formula
```
utility_score = 
  0.45 * tax_savings_norm +      ← TOO LOW
  0.25 * compliance_norm +        ← all ~1.0
  0.15 * simplicity_norm +        ← all similar
  0.10 * audit_risk_inv +         ← all ~0.9
  0.05 * pref_alignment           ← low weight
```

## Proposed Solution
**Phase 1 (Immediate): Adjust Weights**
```
utility_score = 
  0.70 * tax_savings_norm +       ← INCREASED from 0.45
  0.15 * compliance_norm +        ← reduced from 0.25
  0.08 * simplicity_norm +        ← reduced from 0.15
  0.05 * audit_risk_inv +         ← reduced from 0.10
  0.02 * pref_alignment           ← reduced from 0.05
```

**Rationale:**
- Tax savings should be PRIMARY differentiator (70% weight)
- Compliance less important (most strategies compliant)
- Simplicity/complexity matters less than pure tax benefit
- Audit risk low for most strategies anyway
- User preference minimal impact

## Impact Analysis
**Current (unbalanced):**
- Strategies with 5% tax savings: 0.5470
- Strategies with 10% tax savings: 0.5475
- Difference: 0.0005 (essentially undetectable)

**Proposed (balanced):**
- Strategy with 5% tax savings: 0.35 (70% × 0.05 = 0.035)
- Strategy with 10% tax savings: 0.70 (70% × 0.10 = 0.070)
- Difference: 0.35 (clear differentiation!)

## Implementation Steps

### Step 1: Update Utility Formula
**File:** `02_utility_score.py`
- Change line 54-59 weights
- Keep other logic same

### Step 2: Regenerate Training Data
```bash
# Recalculate utility scores with new weights
python 02_utility_score.py
# Outputs: phase2_data/utility_scores_2024_25.csv
#          phase2_data/utility_scores_2025_26.csv
```

### Step 3: Retrain ML Model
```bash
# Train with new utility score distribution
python 03_train_ml_models.py
# Outputs: phase2_models/ml_model_unified.joblib
```

### Step 4: Test & Validate
- Run ML ranking on test personas
- Verify utility scores now have 0.30-0.80 range (not 0.54-0.55)
- Confirm strategies ranked by tax savings primarily
- Check if audit risk/simplicity still differentiate when tax savings equal

## Alternative Approaches (if needed)

### A: Two-Stage Ranking
1. **Stage 1:** Sort by tax_savings_pct only
2. **Stage 2:** Within same tax bracket, apply ML for tie-breaking
   - Benefit: Clear tax priority + nuance for close strategies

### B: Ensemble Approach
- Combine multiple models trained on different aspects
- Weight by importance

### C: Feature Engineering Improvements
- Add derived features:
  - savings_per_relief (tax_savings / num_reliefs)
  - income_adjusted_savings (tax_savings / gross_income)
  - relief_efficiency (tax_savings / total_relief_claimed)
- These better capture "quality" of strategy

## Expected Outcomes
✅ Utility scores spread across 0.20-0.90 range (wide variance)
✅ Strategies differentiated by tax impact (primary)
✅ Audit risk/simplicity still considered (secondary)
✅ User rankings now meaningful

## Testing Checklist
- [ ] Utility score stats show wide variance (std_dev > 0.15)
- [ ] Top strategy always has highest tax savings
- [ ] Scores range from ~0.20 to ~0.90
- [ ] Same tax savings → audit risk determines rank
- [ ] Model outputs range matching training data range

## Rollback Plan
If scores too extreme or skewed:
- Adjust weights to intermediate values (e.g., 0.60 for tax_savings)
- Add feature engineering improvements
- Consider hybrid ranking approach
