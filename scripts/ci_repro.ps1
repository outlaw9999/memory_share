# CI Repro Harness v1.2.4 (Windows)
# Replicates GitHub Actions 'Royal Guard' flow locally

Write-Host ">>> Starting CI Repro Harness (DER v1)" -ForegroundColor Cyan

# 1. Sync dependencies
Write-Host "`n[1/3] Syncing dependencies..." -ForegroundColor Yellow
uv sync --all-extras
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to sync dependencies"; exit 1 }

# 2. Fingerprint
Write-Host "`n[2/3] Environment Fingerprint..." -ForegroundColor Yellow
uv run python -c "import sys; print(f'Interpreter: {sys.executable}'); print(f'Version: {sys.version}')"
uv run python -c "import os; print('PYTHONPATH:', os.environ.get('PYTHONPATH'))"

# 3. Validate
Write-Host "`n[3/3] Running Unified Validator..." -ForegroundColor Yellow
$env:PYTHONUTF8=1
uv run python -m scripts.unified_validator

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ CI Repro: PASS" -ForegroundColor Green
} else {
    Write-Host "`n❌ CI Repro: FAIL" -ForegroundColor Red
    exit 1
}
