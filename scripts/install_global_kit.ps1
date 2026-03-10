# Antigravity Global Kit Installer (Windows/PowerShell)
# This script installs the .kit semantic engine globally on your system.

$ErrorActionPreference = "Stop"

$AntigravityDir = Join-Path $HOME ".antigravity"
$BinDir = Join-Path $AntigravityDir "bin"
$EngineDir = Join-Path $AntigravityDir "engine"
$CurrentDir = Get-Location

Write-Host "--- Antigravity Global Kit Installation ---" -ForegroundColor Cyan

# 1. Create directories
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir | Out-Null
    Write-Host "[+] Created bin directory: $BinDir"
}
if (-not (Test-Path $EngineDir)) {
    New-Item -ItemType Directory -Path $EngineDir | Out-Null
    Write-Host "[+] Created engine directory: $EngineDir"
}

# 2. Stage engine files
Write-Host "[*] Staging engine files..."
Copy-Item "kit.py" $EngineDir
Copy-Item "kit_adapters.py" $EngineDir
if (Test-Path "plugins") {
    Copy-Item "plugins" $EngineDir -Recurse -Force
}

# 3. Create 'kit' launcher
$LauncherPath = Join-Path $BinDir "kit.bat"
$LauncherContent = @"
@echo off
set "ANTIGRAVITY_WORKSPACE_ROOT=%CD%"
set "PYTHONPATH=$EngineDir;%PYTHONPATH%"
python "$EngineDir\kit.py" %*
"@
$LauncherContent | Out-File -FilePath $LauncherPath -Encoding ASCII
Write-Host "[+] Created kit launcher: $LauncherPath"

# 4. Update User PATH
Write-Host "[*] Checking PATH..."
$UserPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::User)
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = "$UserPath;$BinDir"
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, [EnvironmentVariableTarget]::User)
    Write-Host "[+] Added $BinDir to User PATH."
    Write-Host "[!] NOTE: You may need to restart your terminal for changes to take effect." -ForegroundColor Yellow
} else {
    Write-Host "[i] $BinDir is already in PATH."
}

Write-Host "`n--- Installation Complete! ---" -ForegroundColor Green
Write-Host "You can now run 'kit' from any directory."
