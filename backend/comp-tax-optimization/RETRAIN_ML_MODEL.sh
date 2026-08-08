#!/bin/bash

###############################################################################
# ML Model Retraining Script
#
# This script retrains the ML utility score model with updated weights:
# - Tax savings: 70% (increased from 45%)
# - Compliance: 15% (reduced from 25%)
# - Simplicity: 8% (reduced from 15%)
# - Audit risk: 5% (reduced from 10%)
# - Preferences: 2% (reduced from 5%)
#
# Prerequisites:
# - Activate Python venv: source .venv-backend/bin/activate (Linux/Mac) or .venv-backend\Scripts\Activate.ps1 (Windows)
# - Install dependencies: pip install pandas numpy scikit-learn xgboost joblib
###############################################################################

set -e

cd "$(dirname "$0")"

echo "======================================================================"
echo "ML MODEL RETRAINING - Fix Clustering Issue"
echo "======================================================================"
echo ""
echo "Step 1: Regenerating utility scores with new weights..."
echo "  - Input: phase2_data/features_YEAR.csv, phase2_data/ground_truth_YEAR.csv"
echo "  - New weights: tax_savings=70%, compliance=15%, simplicity=8%, audit_risk=5%, pref=2%"
echo "  - Output: phase2_data/utility_scores_YEAR.csv (regenerated)"
echo ""

python3 phase2_ml/02_utility_score.py

if [ $? -eq 0 ]; then
    echo ""
    echo "[OK] Utility scores regenerated successfully"
else
    echo "[ERROR] Failed to regenerate utility scores"
    exit 1
fi

echo ""
echo "======================================================================"
echo "Step 2: Retraining ML models with new utility score distribution..."
echo "  - Input: phase2_data/utility_scores_YEAR.csv (regenerated)"
echo "  - Output: phase2_models/ml_model_YEAR.joblib (new models)"
echo "  - This may take 2-5 minutes..."
echo ""

python3 phase2_ml/03_train_ml_models.py

if [ $? -eq 0 ]; then
    echo ""
    echo "[OK] Models trained successfully"
else
    echo "[ERROR] Failed to train models"
    exit 1
fi

echo ""
echo "======================================================================"
echo "Step 3: Verify new models..."
echo ""

if [ -f phase2_models/ml_model_2024_25.joblib ] && [ -f phase2_models/ml_model_2025_26.joblib ]; then
    echo "[OK] Both model files exist:"
    ls -lh phase2_models/ml_model_*.joblib
    echo ""
    echo "======================================================================"
    echo "SUCCESS! Models retr ained with new weights"
    echo "======================================================================"
    echo ""
    echo "What's next:"
    echo "1. Restart the backend server: Ctrl+C and run_backend.ps1"
    echo "2. Test ML ranking in frontend - scores should now range 0.20-0.90 (not 0.54-0.55)"
    echo "3. Verify strategies ranked by tax savings (primary differentiator)"
    echo ""
else
    echo "[ERROR] Model files not found after training"
    exit 1
fi
