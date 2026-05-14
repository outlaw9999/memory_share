# Kit Post-Merge Hook (v1.2.5) - Windows PowerShell
# Emits MEMORY:RECONCILE for graph resolution after merge.
# Safety: 10s timeout — reconciliation should not block merge.

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "kit-runtime"
$psi.Arguments = "runtime --hook post-merge --json"
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
if (-not $p.WaitForExit(10000)) {
    $p.Kill()
}
exit 0
