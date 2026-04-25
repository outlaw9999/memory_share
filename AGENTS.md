# AGENTS.md

## 🎯 MEMORY GATE

- Search/Recall/Introspect → Kit API only.
- No direct DB/FS access. No ad-hoc SQL/scripts.

## 🧩 COMMAND ROUTER (CR-C1)

- unknown schema  → `kit introspect --json`
- build check     → `kit build`
- unit tests      → `kit test`
- env/health fix  → `kit doctor`
- migration       → `kit doctor --migrate-memory`
- integrity scan  → `kit verify`
- release gate    → `kit verify-release`

## ⚡ FAST PATH (Dev Only)
- build → `task build` (or `python -m py_compile kit/**/*.py`)
- test  → `task test`  (or `pytest -q tests/`)

## 🛡️ RULES & ESCALATION

- Use `${workspaceFolder}` relative paths.
- Before mutation: `kit doctor`.
- On failure: `kit verify` → `kit doctor` → retry.
