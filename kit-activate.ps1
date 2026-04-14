# kit-activate.ps1
# v1.2.4-TITANIUM: Environment Locking Ritual
# Enforces the single-source-of-truth for Python environment.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$venvPath = Join-Path $PWD ".venv"
if (-Not (Test-Path $venvPath)) {
    Write-Error "ERROR: .venv not found in current directory. Run 'python -m venv .venv' first."
}

# Add venv bin to PATH if not already there
$binPath = Join-Path $venvPath "Scripts"
if ($env:PATH -notlike "*$binPath*") {
    $env:PATH = "$binPath;$env:PATH"
    Write-Host "PASS: .venv/Scripts added to PATH." -ForegroundColor Green
} else {
    Write-Host "NOTE: .venv/Scripts already in PATH." -ForegroundColor Gray
}

# Set environment markers for internal discovery
$env:KIT_VENV = $venvPath
$env:PYTHONPATH = $PWD

Write-Host "`nTITANIUM KERNEL ACTIVE: v1.2.4-STABILIZATION" -ForegroundColor Cyan
Write-Host "Python Path: $( (Get-Command python.exe).Source )" -ForegroundColor Gray
Write-Host "Ready for 'kit run-skill'" -ForegroundColor Green
