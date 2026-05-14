# Kit Pre-Commit Hook (v1.2.5) - Windows PowerShell
# Emits LIFECYCLE:PRE_COMMIT via kit-runtime. Blocks commit on failure.
# Safety: 5s timeout via .NET Process prevents blocking git workflow.

$ErrorActionPreference = "Stop"
Write-Host "[Kit] Pre-commit runtime check..." -ForegroundColor Cyan

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "kit-runtime"
$psi.Arguments = "runtime --hook pre-commit --json"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$p = [System.Diagnostics.Process]::Start($psi)

if ($p.WaitForExit(5000)) {
    $result = $p.StandardOutput.ReadToEnd()
    $exitCode = $p.ExitCode
    if ($exitCode -eq 0) {
        Write-Host "[Kit] Pre-commit check passed" -ForegroundColor Green
        exit 0
    }
    Write-Host "[Kit] Pre-commit check FAILED" -ForegroundColor Red
    Write-Host $result
    exit 1
}

$p.Kill()
Write-Host "[Kit] Pre-commit timed out (5s) — allowing commit" -ForegroundColor Yellow
exit 0
