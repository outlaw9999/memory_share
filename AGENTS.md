# AGENTS.md 

## 🎯 MEMORY GATE (Layer 1)

- Search/Recall/Introspect → Kit API only.
- No direct DB/Filesystem access.
- Routing: unknown schema → introspect | friction → kit doctor.

## 🚫 HARD RULES

- No direct filesystem reads outside Kit API.
- No raw SQL/DB bypass.
- No ad-hoc memory inspection scripts.

## 🆘 ESCALATION

fail → kit-vantage verify → kit doctor → retry

## 🛡️ SELF-CORRECTION

- Before risky mutation: kit doctor.
- Workspace: Use ${workspaceFolder} relative paths.
- Isolation: Use .env KIT_PROJECT_ID.
