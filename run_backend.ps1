# Tax Optimization Backend Startup Script
# Runs FastAPI server on port 8002 from the comp-tax-optimization directory

$ErrorActionPreference = "Stop"

Write-Host "Killing any existing Python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Write-Host "Starting backend on port 8002..." -ForegroundColor Green
$projectRoot = "D:\R26-DS-004\R26-DS-004"
$backendRoot = "$projectRoot\backend\comp-tax-optimization"

# Set PYTHONPATH to include both project root (for backend.shared) and backend directory (for relative imports)
$env:PYTHONPATH = "$projectRoot;$backendRoot"

# Set absolute path to Phase 2 models for the ML ranker
$env:PHASE2_MODELS_ABSOLUTE = "$backendRoot\phase2_models"

Write-Host "Working directory: $backendRoot" -ForegroundColor Gray
Write-Host "PYTHONPATH: $($env:PYTHONPATH)" -ForegroundColor Gray
Write-Host ""

Set-Location $backendRoot

# Run from the comp-tax-optimization directory
$venv = "$projectRoot\.venv-backend\Scripts\python.exe"
& $venv -m uvicorn `
    tax_opt_b_app.main:app `
    --host 127.0.0.1 `
    --port 8002 `
    --reload
