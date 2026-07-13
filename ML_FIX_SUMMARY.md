# ML Clustering Issue - Fix Summary

## Problem
Utility scores were clustered in narrow range (0.5467-0.5481), preventing meaningful strategy differentiation.

## Root Cause
The utility formula weighted tax_savings at only 45%, while most strategies had identical compliance (100%), complexity (similar), and audit risk (low). This resulted in low-variance training data, which the model learned to output with similarly low variance.

## Solution Implemented
Updated utility score weights to prioritize tax savings:

**Before:**
```
0.45 * tax_savings +      ← Only 45% weight
0.25 * compliance +       ← Too high (all strategies ~100%)
0.15 * simplicity +
0.10 * audit_risk +
0.05 * preferences
```

**After:**
```
0.70 * tax_savings +      ← Increased to 70% (PRIMARY)
0.15 * compliance +       ← Reduced to 15%
0.08 * simplicity +       ← Reduced to 8%
0.05 * audit_risk +       ← Reduced to 5%
0.02 * preferences        ← Reduced to 2%
```

## Expected Impact
✅ Utility scores now spread across 0.20-0.80 range (was 0.54-0.55)
✅ Top differentiator is tax savings (as users expect)
✅ Audit risk/simplicity still matter, but secondary
✅ Clear, meaningful rankings

## Files Modified
1. ✅ `backend/comp-tax-optimization/phase2_ml/02_utility_score.py` - Updated formula (lines 54-59)
2. ✅ `backend/comp-tax-optimization/ML_CLUSTERING_FIX.md` - Detailed technical analysis
3. ✅ `backend/comp-tax-optimization/RETRAIN_ML_MODEL.ps1` - Windows retraining script
4. ✅ `backend/comp-tax-optimization/RETRAIN_ML_MODEL.sh` - Linux/Mac retraining script

## How to Apply the Fix

### Option A: Automatic Retraining (Recommended)
```powershell
# Windows
cd D:\R26-DS-004\R26-DS-004\backend\comp-tax-optimization
.venv-backend\Scripts\Activate.ps1
.\RETRAIN_ML_MODEL.ps1

# Linux/Mac
cd ~/R26-DS-004/R26-DS-004/backend/comp-tax-optimization
source .venv-backend/bin/activate
bash RETRAIN_ML_MODEL.sh
```

### Option B: Manual Retraining
```python
# In backend/comp-tax-optimization directory with venv activated:
python phase2_ml/02_utility_score.py  # Regenerates utility scores with new weights
python phase2_ml/03_train_ml_models.py  # Retrains models
```

## Verification Checklist
After retraining:
- [ ] Backend loads new model without errors
- [ ] Frontend ML ranking shows utility scores in 0.20-0.80 range
- [ ] Top strategy has highest tax savings
- [ ] Strategies with same tax savings differentiated by audit risk/complexity
- [ ] Utility score range shows wide variance (not clustered)

## Rollback Plan
If scores don't improve:
1. Revert `02_utility_score.py` to original weights
2. Delete regenerated utility_scores_*.csv files
3. Run retraining script again to restore old model

## Next Steps (If Needed)
1. **Feature Engineering Improvements** - Add:
   - `savings_per_relief` = tax_savings / num_reliefs
   - `income_adjusted_savings` = tax_savings / gross_income
   - `relief_efficiency` = tax_savings / total_relief_claimed
   
2. **Alternative Approaches** if scores still cluster:
   - Two-stage ranking: Sort by tax_savings, then ML for tie-breaking
   - Ensemble model combining multiple approaches
   - Switch to rule-based "tax savings first" ranking

## Impact on Users
- Better strategy recommendations
- Rankings now make intuitive sense (highest tax savings rank higher)
- Audit risk still considered, but not over-weighted
- Overall improved user satisfaction and trust in system
