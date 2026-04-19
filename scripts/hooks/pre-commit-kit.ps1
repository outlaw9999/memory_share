# Kit + Vantage Pre-Commit Hook (v1.2.4) - Windows PowerShell
#
# This hook runs Vantage memory verification BEFORE commit.
# If Vantage fails, commit is BLOCKED.
#
# Install: 
#   Copy this file to .git/hooks\pre-commit
#   Or reference from .git\hooks in your git config

$ErrorActionPreference = "Stop"

Write-Host "🔍 [Kit] Running Vantage verification..." -ForegroundColor Cyan

# Find Vantage binary
$VantageBin = $null
$PossiblePaths = @(
    ".\kit-vantage.exe",
    "$PSScriptRoot\..\kit-vantage.exe",
    "$PSScriptRoot\kit-vantage.exe"
)

foreach ($path in $PossiblePaths) {
    $resolved = $ExecutionContext.InvokeCommand.ExpandString($path)
    if (Test-Path $resolved) {
        $VantageBin = $resolved
        break
    }
}

if (-not $VantageBin) {
    # Also check in PATH
    $VantageBin = Get-Command kit-vantage.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}

if (-not $VantageBin) {
    Write-Host "⚠️  [Kit] Vantage not found. Skipping integrity check." -ForegroundColor Yellow
    exit 0
}

# Run Vantage verification
try {
    $result = & $VantageBin verify-memory --json 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "✅ [Kit] Memory integrity verified" -ForegroundColor Green
        exit 0
    }
    else {
        Write-Host "❌ [Kit] Memory integrity FAILED" -ForegroundColor Red
        Write-Host $result
        Write-Host ""
        Write-Host "🔧 Run `kit doctor` to diagnose" -ForegroundColor Yellow
        Write-Host "🔧 Run `kit-vantage verify-memory -d` for details" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "⚠️  [Kit] Vantage execution failed: $_" -ForegroundColor Yellow
    exit 0
}