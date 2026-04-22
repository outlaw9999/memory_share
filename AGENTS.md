# AGENTS.md (v1.2.4 EXECUTION CONTRACT)

## ⚖️ FLOW
recall → tool → execute → learn

## 🚫 RULES
- NEVER guess parameters or API signatures.
- ALWAYS prefer --json over --help for machine parsing.
- AGENTS.md = routing only, NOT truth source.
- Truth = `.kit/kit_schema.json` OR `kit introspect --json`.

## 🎯 ROUTING
- **Unknown schema/params** → `kit introspect --json`
- **Post-Arbitration Gate** → `kit-vantage verify --batch (MANDATORY)`
- **Startup / New Task** → `kit recall --limit 10`
- **Logic Conflict** → `kit-vantage verify-memory`
- **System State / Friction** → `kit doctor`
- **Persistence** → `kit learn --tag decision`

## 🆘 ESCALATION
Fail → `kit-vantage verify` → `kit doctor` → `kit recall project_identity` → Retry
