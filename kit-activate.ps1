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

# --- Linux Compatibility Layer ---
# Use functions for argument passing. Safety check prevents collisions.
if (-not (Get-Command cat -ErrorAction SilentlyContinue)) {
    function Global:cat { Get-Content @args }
}
if (-not (Get-Command grep -ErrorAction SilentlyContinue)) {
    function Global:grep { 
        param($p, $f=".") 
        Select-String -Pattern $p -Path $f 
    }
}
if (-not (Get-Command ls -ErrorAction SilentlyContinue)) {
    function Global:ls { Get-ChildItem @args }
}
if (-not (Get-Command pwd -ErrorAction SilentlyContinue)) {
    function Global:pwd { Get-Location }
}
if (-not (Get-Command touch -ErrorAction SilentlyContinue)) {
    function Global:touch { 
        param($p) 
        New-Item -ItemType File -Path $p -Force | Out-Null 
    }
}

# --- Kit Ergonomics ---
function Global:kb { kit boot }
function Global:kd { kit doctor }
function Global:kt { python run_sentinel.py }

Write-Host "`nSURFACE COMPATIBILITY: Linux primitives (cat, grep, ls, pwd, touch) active (Global Scope)." -ForegroundColor Gray
Write-Host "SHORTCUTS: kb (boot), kd (doctor), kt (test) active." -ForegroundColor Gray
