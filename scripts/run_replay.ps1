$commands = @(
    "init",
    "learn --content 'replay_trace'",
    "search dummy",
    "recall dummy",
    "context dummy",
    "reflect --mode advisory --deep",
    "bake",
    "stats",
    "status",
    "link A B REL",
    "bump",
    "promote",
    "doctor",
    "render",
    "watch --dry-run",
    "preflight",
    "blame dummy",
    "scan",
    "compile",
    "trigger dummy --dry-run",
    "run-skill dummy --dry-run",
    "where",
    "label dummy tag",
    "bake",
    "reflect",
    "search dummy",
    "recall dummy"
)

foreach ($cmd in $commands) {
    Write-Host "Replaying: python kit.py $cmd"
    Invoke-Expression "python kit.py $cmd"
    Start-Sleep -Milliseconds 100
}
Write-Host "Replay loop finished."
