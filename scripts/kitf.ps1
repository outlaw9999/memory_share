function kitf {
    <#
    .SYNOPSIS
    Friction Log Wizard v1.2.3.3.1-ULTRA-GOLD (Armor-Plated Edition)
    Dot-source this file in your $PROFILE to enable.
    #>
    try {
        # Force UTF-8 for reliable IO
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        [Console]::InputEncoding = [System.Text.Encoding]::UTF8

        Write-Host "`n[FRICTION HUNT MODE v1.2.3.3.1-ULTRA-GOLD (ARMOR-PLATED)]" -ForegroundColor Cyan
        Write-Host "Recall: kit recall forensic_friction_schema" -ForegroundColor Gray

        $symptom = Read-Host "1. Symptom"
        $trigger = Read-Host "2. Trigger"
        
        $category = Read-Host "3. Category [ux/perf/logic/invariant_clash] (Default: ux)"
        if ([string]::IsNullOrWhiteSpace($category)) { $category = "ux" }
        
        $severity = Read-Host "4. Severity [low/med/high/critical] (Default: med)"
        if ([string]::IsNullOrWhiteSpace($severity)) { $severity = "med" }
        
        $expectation = Read-Host "5. Expectation"

        Write-Host "`n[SURGICAL METRICS]" -ForegroundColor Yellow
        $shim_status = Read-Host "6. Shim Status [ok/delay/error] (Default: ok)"
        if ([string]::IsNullOrWhiteSpace($shim_status)) { $shim_status = "ok" }

        $vantage_signal = Read-Host "7. Vantage Signal [deterministic/noise/drift] (Default: deterministic)"
        if ([string]::IsNullOrWhiteSpace($vantage_signal)) { $vantage_signal = "deterministic" }

        $agent_compliance = Read-Host "8. Agent Compliance [compliant/non_compliant] (Default: compliant)"
        if ([string]::IsNullOrWhiteSpace($agent_compliance)) { $agent_compliance = "compliant" }

        # Atomic JSON packaging
        $payloadObj = @{
            symptom = $symptom
            trigger = $trigger
            category = $category
            severity = $severity
            expectation = $expectation
            metrics = @{
                shim_status = $shim_status
                vantage_signal = $vantage_signal
                agent_compliance = $agent_compliance
                version_context = "v1.2.3.3.1-ULTRA-GOLD"
            }
        }
        
        $rawJson = $payloadObj | ConvertTo-Json -Depth 3 -Compress

        # EXECUTION: Atomic ingestion into memory
        kit learn --tag note --kind friction --content $rawJson

        Write-Host "PASS: Friction Log JSON ingested into vault." -ForegroundColor Green

    } catch {
        Write-Warning "`nExiting friction hunt mode (Ctrl+C) or error occurred."
    }
}
