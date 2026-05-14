# Kit Post-Commit Hook (v1.2.5) - Windows PowerShell
# Emits LIFECYCLE:POST_COMMIT with captured git diff for memory learning.

$env:KIT_GIT_DIFF = git diff HEAD~1...HEAD 2>$null
$env:KIT_GIT_COMMIT = git rev-parse HEAD 2>$null
$env:KIT_GIT_BRANCH = git rev-parse --abbrev-ref HEAD 2>$null

& kit-runtime runtime --hook post-commit --json 2>&1 | Out-Null
exit 0
