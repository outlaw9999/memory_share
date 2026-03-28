function kitf {
    <#
    .SYNOPSIS
    Friction Log Wizard v1.2.3 (Armor-Plated Edition)
    Dot-source this file in your $PROFILE to enable.
    #>
    try {
        # Unicode Resilience: Force UTF-8 for Vietnamese input
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        [Console]::InputEncoding = [System.Text.Encoding]::UTF8

        Write-Host "`n[🤖 CHẾ ĐỘ SĂN MA SÁT v1.2.3 (BỌC THÉP)]" -ForegroundColor Cyan

        $symptom = Read-Host "1. Triệu chứng (Symptom)"
        $trigger = Read-Host "2. Tác nhân (Trigger)"
        
        $category = Read-Host "3. Phân loại [ux/perf/logic/invariant_clash] (Mặc định: ux)"
        if ([string]::IsNullOrWhiteSpace($category)) { $category = "ux" }
        
        $severity = Read-Host "4. Mức độ [low/med/high/critical] (Mặc định: med)"
        if ([string]::IsNullOrWhiteSpace($severity)) { $severity = "med" }
        
        $expectation = Read-Host "5. Kỳ vọng (Expectation)"

        # Atomic JSON Packaging
        $payloadObj = @{
            symptom = $symptom
            trigger = $trigger
            category = $category
            severity = $severity
            expectation = $expectation
        }
        
        $rawJson = $payloadObj | ConvertTo-Json -Depth 3 -Compress

        # Armor-plating: Escape double quotes for PowerShell-to-Python boundary
        $safePayload = $rawJson.Replace('"', '\"')

        # EXECUTION: Ingest as 'tag: note' with 'kind: friction' to pass v1.2.3 Policy
        python kit.py learn --tag note --kind friction --content "$safePayload"

        Write-Host "✅ Đã nạp Friction Log JSON nguyên vẹn vào Két sắt!" -ForegroundColor Green

    } catch {
        Write-Warning "`n⚠️ Thoát chế độ săn ma sát (Ctrl+C) hoặc có lỗi xảy ra."
    }
}
