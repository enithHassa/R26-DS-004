# ML Model Retraining Script (PowerShell)
#
# This script retrains the ML utility score model with updated weights to fix clustering
#
# Prerequisites:
# - Activate Python venv
# - cd to backend/comp-tax-optimization directory

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "ML MODEL RETRAINING - Fix Clustering Issue" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$projectRoot = "D:\R26-DS-004\R26-DS-004"
$backendRoot = "$projectRoot\backend\comp-tax-optimization"
$venv = "$projectRoot\.venv-backend\Scripts\python.exe"

# Check if Python venv exists
if (-not (Test-Path $venv)) {
    Write-Host "[ERROR] Python venv not found at: $venv" -ForegroundColor Red
    Write-Host "Please activate the venv first: .venv-backend\Scripts\Activate.ps1" -ForegroundColor Yellow
    exit 1
}

# Step 1: Regenerate utility scores
Write-Host "Step 1: Regenerating utility scores with new weights..." -ForegroundColor Yellow
Write-Host "  - New weights: tax_savings=70%, compliance=15%, simplicity=8%, audit_risk=5%, pref=2%" -ForegroundColor Gray
Write-Host ""

Set-Location $backendRoot
& $venv phase2_ml/02_utility_score.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to regenerate utility scores" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] Utility scores regenerated successfully" -ForegroundColor Green
Write-Host ""

# Step 2: Retrain models
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Step 2: Retraining ML models (this may take 2-5 minutes)..." -ForegroundColor Yellow
Write-Host ""

& $venv phase2_ml/03_train_ml_models.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to train models" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] Models trained successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Verify
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Step 3: Verifying new models..." -ForegroundColor Yellow
Write-Host ""

$model_2024 = "$backendRoot\phase2_models\ml_model_2024_25.joblib"
$model_2025 = "$backendRoot\phase2_models\ml_model_2025_26.joblib"

if ((Test-Path $model_2024) -and (Test-Path $model_2025)) {
    Write-Host "[OK] Both model files exist:" -ForegroundColor Green
    Get-Item $model_2024, $model_2025 | Select-Object FullName, Length
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "SUCCESS! Models retrained with new weights" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "What's next:" -ForegroundColor Cyan
    Write-Host "1. Restart the backend server: Ctrl+C and run_backend.ps1" -ForegroundColor White
    Write-Host "2. Test ML ranking in frontend - scores should now range 0.20-0.90" -ForegroundColor White
    Write-Host "3. Verify strategies ranked by tax savings (primary differentiator)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "[ERROR] Model files not found after training" -ForegroundColor Red
    Write-Host "  Expected: $model_2024" -ForegroundColor Red
    Write-Host "  Expected: $model_2025" -ForegroundColor Red
    exit 1
}
