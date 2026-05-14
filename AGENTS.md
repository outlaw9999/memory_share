# AGENTS.md — Canonical Behavioral Contract (v1.2.5)

## 🎯 MEMORY GATE
- No direct DB/FS access. No ad-hoc SQL/scripts.
- Operate via INTENTS only — never call kit CLI directly.

## 🧠 INTENT ROUTER (IR-C1)
Agent MUST NOT call kit commands. Emit one of:
- `INTENT: GRAPH:BUILD`
- `INTENT: RELEASE:TEST`
- `INTENT: VERIFICATION:VERIFY`
- `INTENT: RUNTIME:HEALTH`
- `INTENT: MEMORY:LEARN`
- `INTENT: MEMORY:RECALL`
- `INTENT: RELEASE:RELEASE`

## 🔄 LIFECYCLE HOOKS
startup (self_heal) → validate → execute → verify → recover
(All events resolve through the intent router).

## 🛡️ RULES
- **Runtime is Truth**: Discover capabilities dynamically via:
  - `kit introspect --json`
  - `kit <cmd> --help`
- **Commit Frequently**: Git is the grounded reality anchor.
- **Fail Early**: On failure, emit `INTENT: RUNTIME:HEALTH`.
- **Use Relative Paths**: Anchor to `${workspaceFolder}`.

---
v1.2.5-TITANIUM-STABLE
