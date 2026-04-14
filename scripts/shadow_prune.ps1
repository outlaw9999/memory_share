$Candidates = @(
    "kit_agent",
    "runtime",
    "examples",
    "plugins",
    "archive",
    "kit/adapters",
    "kit/context",
    "kit/fs",
    "kit/graph",
    "kit/index",
    "kit/interfaces",
    "kit/llm",
    "kit/planning",
    "kit/query",
    "kit/services"
)

Write-Host "Phase 2C: Initiating Shadow Deletion Simulator..."

foreach ($c in $Candidates) {
    if (Test-Path $c) {
        Rename-Item -Path $c -NewName "$($c | Split-Path -Leaf).SHADOW"
        Write-Host "  -> Shadowed: $c"
    } else {
        Write-Host "  -> Skipping: $c (Does not exist)"
    }
}

try {
    Write-Host "`nRunning Deterministic Replay in Shadow Mode..."
    $replay_out = & .\scripts\run_replay.ps1 2>&1
    $replay_out | Out-File -FilePath "shadow_replay_output.txt"

    Write-Host "`nAnalyzing Execution Graph Integrity..."
    $errors = Select-String -Path "shadow_replay_output.txt" -Pattern "(ModuleNotFoundError|ImportError|Exception)"
    
    if ($errors) {
        Write-Host "`n[!] CRITICAL HAZARD DETECTED! Shadow prune broke the runtime:" -ForegroundColor Red
        foreach ($err in $errors) {
            Write-Host "    $err" -ForegroundColor Yellow
        }
    } else {
        Write-Host "`n[+] SHADOW PRUNE SUCCESS: No runtime breakage detected. Modules are certified DEAD." -ForegroundColor Green
    }
} finally {
    Write-Host "`nRestoring Environment..."
    foreach ($c in $Candidates) {
        $shadowPath = if ($c -match "/") {
            $parent = Split-Path $c
            $leaf = Split-Path $c -Leaf
            "$parent\$leaf.SHADOW"
        } else {
            "$c.SHADOW"
        }

        if (Test-Path $shadowPath) {
            Rename-Item -Path $shadowPath -NewName (Split-Path $c -Leaf)
            Write-Host "  -> Restored: $c"
        }
    }
}
Write-Host "Phase 2C Simulation Complete."
